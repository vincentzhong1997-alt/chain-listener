"""Solana blockchain adapter implementation."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Union

from chain_listener.adapters.base import BaseAdapter
from chain_listener.exceptions import BlockchainAdapterError
from chain_listener.models.events import ChainType, DecodedEvent, RawEvent

try:  # pragma: no cover - optional dependency
    from solana.publickey import PublicKey  # type: ignore
    from solana.rpc.async_api import AsyncClient  # type: ignore

    SOLANA_SDK_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    PublicKey = None  # type: ignore
    AsyncClient = None  # type: ignore
    SOLANA_SDK_AVAILABLE = False

try:  # pragma: no cover - optional dependency
    from anchorpy import Idl  # type: ignore
    from anchorpy.coder import BorshCoder  # type: ignore
    from anchorpy.coder.event import EventParser  # type: ignore

    ANCHORPY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    Idl = None  # type: ignore
    BorshCoder = None  # type: ignore
    EventParser = None  # type: ignore
    ANCHORPY_AVAILABLE = False


class SolanaAdapter(BaseAdapter):
    """Adapter implementation for the Solana blockchain."""

    DEFAULT_CONFIG = {
        "commitment": "confirmed",
        "signature_batch_size": 200,
        "max_signature_batches": 10,
        "transaction_batch_size": 20,
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.logger = logging.getLogger(__name__)

        self.commitment = config.get("commitment", self.DEFAULT_CONFIG["commitment"])
        self.signature_batch_size = int(
            config.get(
                "signature_batch_size", self.DEFAULT_CONFIG["signature_batch_size"]
            )
        )
        self.max_signature_batches = int(
            config.get(
                "max_signature_batches", self.DEFAULT_CONFIG["max_signature_batches"]
            )
        )
        self.transaction_batch_size = int(
            config.get(
                "transaction_batch_size",
                self.DEFAULT_CONFIG["transaction_batch_size"],
            )
        )

        if self.chain_type is None:
            self.chain_type = ChainType.SOLANA

        self._clients: Dict[str, AsyncClient] = {}
        self._connected = False
        self._event_parsers: Dict[str, Any] = {}
        self._prepare_event_parsers()

    async def connect(self) -> None:
        endpoint = self._connection_pool.get_next_connection()
        await self._get_or_create_client(endpoint)
        self._connected = True

    async def disconnect(self) -> None:
        for client in self._clients.values():
            try:
                close = getattr(client, "close", None)
                if close:
                    await close()
            except Exception:
                continue
        self._clients.clear()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and bool(self._clients)

    async def get_latest_block_number(self) -> int:
        response = await self._execute_with_client(
            lambda client: client.get_block_height(commitment=self.commitment)
        )
        return int(self._unwrap_rpc_result(response, default=0))

    async def get_logs(
        self,
        address: Optional[Union[str, List[str]]] = None,
        topics: Optional[List[str]] = None,
        from_block: Optional[Union[int, str]] = None,
        to_block: Optional[Union[int, str]] = None,
        event_filters: Optional[Dict[str, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        if address is None:
            raise BlockchainAdapterError(
                "SolanaAdapter requires a program address",
                blockchain=self.name,
                network=self.network,
            )

        program_ids = [address] if isinstance(address, str) else list(address)
        from_slot = self._normalize_slot(from_block)
        to_slot = self._normalize_slot(to_block)
        topic_filter = set(topics or [])

        logs: List[Dict[str, Any]] = []
        for program_id in program_ids:
            signatures = await self._fetch_signatures_for_program(
                program_id, from_slot, to_slot
            )
            events = await self._build_events_from_signatures(
                program_id, signatures, topic_filter
            )
            if topic_filter:
                events = [
                    event for event in events if event.get("event_name") in topic_filter
                ]
            logs.extend(events)

        return logs

    def decode_event(self, event: RawEvent) -> DecodedEvent:
        raw = event.raw_data or {}
        event_name = raw.get("event_name") or "SolanaEvent"
        parameters = raw.get("event_data") or raw
        timestamp = raw.get("timestamp") or event.timestamp or 0

        return DecodedEvent(
            chain_type=self.chain_type or ChainType.SOLANA,
            contract_address=event.contract_address,
            event_name=event_name,
            parameters=parameters,
            block_number=event.block_number,
            transaction_hash=event.transaction_hash,
            log_index=event.log_index,
            timestamp=int(timestamp),
        )

    async def _execute_with_client(
        self, operation: Callable[[Any], Awaitable[Any]]
    ) -> Any:
        last_error: Optional[Exception] = None
        max_retries = self._connection_pool.max_retries

        for attempt in range(max_retries + 1):
            endpoint = self._connection_pool.get_next_connection()
            client = await self._get_or_create_client(endpoint)

            try:
                result = await self._execute_with_rate_limit(operation, client)
                self._connection_pool.mark_success(endpoint)
                return result
            except Exception as exc:
                last_error = exc
                self._connection_pool.mark_failure(endpoint)
                if attempt < max_retries:
                    continue
                break

        raise BlockchainAdapterError(
            f"Solana RPC operation failed after {max_retries + 1} attempts: {last_error}",
            blockchain=self.name,
            network=self.network,
            details={"error": str(last_error) if last_error else "unknown"},
        )

    async def _get_or_create_client(self, endpoint: str) -> AsyncClient:
        if endpoint in self._clients:
            return self._clients[endpoint]

        self._ensure_solana_sdk()
        timeout = self.rpc_config.get("timeout", 30)
        client = AsyncClient(endpoint, commitment=self.commitment, timeout=timeout)  # type: ignore[arg-type]
        self._clients[endpoint] = client
        return client

    async def _fetch_signatures_for_program(
        self,
        program_id: str,
        from_slot: Optional[int],
        to_slot: Optional[int],
    ) -> List[Dict[str, Any]]:
        self._ensure_solana_sdk()
        pubkey = PublicKey(program_id)  # type: ignore[arg-type]

        before: Optional[str] = None
        signatures: List[Dict[str, Any]] = []
        batch = 0
        reached_start = False

        while batch < self.max_signature_batches and not reached_start:
            response = await self._execute_with_client(
                lambda client: client.get_signatures_for_address(
                    pubkey,
                    before=before,
                    commitment=self.commitment,
                    limit=self.signature_batch_size,
                )
            )
            entries = self._unwrap_rpc_result(response, default=[]) or []
            if not isinstance(entries, list) or not entries:
                break

            batch += 1
            for entry in entries:
                slot = entry.get("slot")
                if slot is None:
                    continue
                if to_slot is not None and slot > to_slot:
                    continue
                if from_slot is not None and slot < from_slot:
                    reached_start = True
                    continue
                signatures.append(entry)

            before = entries[-1].get("signature")
            if not before:
                break

        return signatures

    async def _build_events_from_signatures(
        self,
        program_id: str,
        signatures: List[Dict[str, Any]],
        topic_filter: set,
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not signatures:
            return events

        for chunk in self._chunk(signatures, self.transaction_batch_size):
            for signature_info in chunk:
                signature = signature_info.get("signature")
                if not signature:
                    continue

                response = await self._execute_with_client(
                    lambda client, sig=signature: client.get_transaction(
                        sig,
                        commitment=self.commitment,
                        encoding="jsonParsed",
                        max_supported_transaction_version=0,
                    )
                )
                transaction = self._unwrap_rpc_result(response)
                if not transaction:
                    continue

                events.extend(
                    self._build_events_from_transaction(
                        program_id, signature_info, transaction, topic_filter
                    )
                )

        return events

    def _build_events_from_transaction(
        self,
        program_id: str,
        signature_info: Dict[str, Any],
        transaction: Dict[str, Any],
        topic_filter: set,
    ) -> List[Dict[str, Any]]:
        slot = transaction.get("slot") or signature_info.get("slot") or 0
        block_time = transaction.get("blockTime") or signature_info.get("blockTime") or 0
        meta = transaction.get("meta") or {}
        log_messages = meta.get("logMessages") or []
        block_hash = (
            transaction.get("transaction", {})
            .get("message", {})
            .get("recentBlockhash", "")
        )

        parser = self._event_parsers.get(self._normalize_program_id(program_id))
        parsed_events: List[Dict[str, Any]] = []

        if parser and log_messages:
            try:
                parse_method = getattr(parser, "parse_logs", None) or getattr(
                    parser, "parse", None
                )
                if parse_method:
                    for evt in parse_method(log_messages):
                        name = getattr(evt, "name", None) or evt.get("name")  # type: ignore[union-attr]
                        data = getattr(evt, "data", None) or evt.get("data")  # type: ignore[union-attr]
                        parsed_events.append({"name": name or "SolanaEvent", "data": data})
            except Exception as exc:
                self.logger.warning(
                    "Failed to parse Anchor events for %s: %s", program_id, exc
                )

        if not parsed_events:
            parsed_events.append(
                {
                    "name": "SolanaLog",
                    "data": {"log_messages": log_messages},
                }
            )

        events: List[Dict[str, Any]] = []
        for index, event_info in enumerate(parsed_events):
            event_name = event_info.get("name") or "SolanaEvent"
            if topic_filter and event_name not in topic_filter:
                continue

            events.append(
                {
                    "block_number": slot,
                    "block_hash": block_hash,
                    "transaction_hash": signature_info.get("signature", ""),
                    "log_index": index,
                    "address": program_id,
                    "timestamp": block_time,
                    "event_name": event_name,
                    "event_data": event_info.get("data") or {},
                    "raw": {
                        "signature": signature_info,
                        "transaction": transaction,
                        "log_messages": log_messages,
                    },
                }
            )

        return events

    def _prepare_event_parsers(self) -> None:
        if not (SOLANA_SDK_AVAILABLE and ANCHORPY_AVAILABLE):
            return

        for contract in self._contract_configs:
            program_id = contract.get("address")
            abi_path = contract.get("abi_path")
            if not program_id or not abi_path:
                continue

            idl = self._load_contract_abi(abi_path)
            if not idl:
                continue

            parser = self._create_event_parser(program_id, idl)
            if parser:
                self._event_parsers[self._normalize_program_id(program_id)] = parser

    def _create_event_parser(self, program_id: str, idl: Any) -> Optional[Any]:
        if not (ANCHORPY_AVAILABLE and SOLANA_SDK_AVAILABLE):
            return None

        if BorshCoder is None or EventParser is None or PublicKey is None:
            return None

        try:
            if hasattr(Idl, "from_json"):
                idl_obj = Idl.from_json(idl)  # type: ignore[call-arg]
            elif callable(Idl):
                idl_obj = Idl(idl)  # type: ignore[call-arg]
            else:
                idl_obj = idl

            coder = BorshCoder(idl_obj)  # type: ignore[call-arg]
            return EventParser(PublicKey(program_id), coder)  # type: ignore[arg-type]
        except Exception as exc:
            self.logger.warning(
                "Unable to build Anchor parser for %s: %s", program_id, exc
            )
            return None

    def _normalize_slot(self, block_reference: Optional[Union[int, str]]) -> Optional[int]:
        if block_reference is None:
            return None
        if isinstance(block_reference, int):
            return block_reference
        if isinstance(block_reference, str) and block_reference.isdigit():
            return int(block_reference)
        return None

    def _normalize_program_id(self, program_id: str) -> str:
        return program_id.strip()

    def _ensure_solana_sdk(self) -> None:
        if not SOLANA_SDK_AVAILABLE:
            raise BlockchainAdapterError(
                "solana dependency is required for SolanaAdapter",
                blockchain=self.name,
                network=self.network,
            )

    @staticmethod
    def _unwrap_rpc_result(response: Any, default: Any = None) -> Any:
        if isinstance(response, dict):
            if "result" in response:
                result = response["result"]
                if isinstance(result, dict) and "value" in result:
                    return result["value"]
                return result
            if "value" in response:
                return response["value"]
        return response if response is not None else default

    @staticmethod
    def _chunk(items: Iterable[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
        batch: List[Dict[str, Any]] = []
        for item in items:
            batch.append(item)
            if len(batch) >= size:
                yield batch
                batch = []
        if batch:
            yield batch
