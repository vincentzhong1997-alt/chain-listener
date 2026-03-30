"""Tron blockchain adapter built on top of tronpy."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union, Awaitable, Callable

import aiohttp
from hexbytes import HexBytes
from eth_utils import event_abi_to_log_topic
from tronpy import Tron
from tronpy.providers import HTTPProvider
from web3 import Web3
from web3.datastructures import AttributeDict
from web3._utils.events import get_event_data

from chain_listener.adapters.base import BaseAdapter
from chain_listener.exceptions import BlockchainAdapterError
from chain_listener.models.events import ChainType, RawEvent, DecodedEvent


class TronAdapter(BaseAdapter):
    """Adapter implementation for the Tron blockchain using tronpy."""

    DEFAULT_CONFIG = {
        "block_time": 3,
        "event_page_size": 200,
        "max_event_pages": 10,
    }

    TOPIC_TO_EVENT = {
        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef": "Transfer",
        "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925": "Approval",
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.logger = logging.getLogger(__name__)

        # 重制默认配置
        self.block_time = config.get("block_time", self.DEFAULT_CONFIG["block_time"])
        self.event_page_size = config.get(
            "event_page_size", self.DEFAULT_CONFIG["event_page_size"]
        )
        self.max_event_pages = config.get(
            "max_event_pages", self.DEFAULT_CONFIG["max_event_pages"]
        )

        self.api_key = config.get("api_key") or self.rpc_config.get("api_key")
        if self.chain_type is None:
            self.chain_type = ChainType.TRON

        self._clients: Dict[str, Tron] = {}
        self._timestamp_cache: Dict[int, int] = {}

        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

        self._default_headers: Dict[str, str] = dict(self.rpc_config.get("headers", {}))
        if self.api_key and "TRON-PRO-API-KEY" not in self._default_headers:
            self._default_headers["TRON-PRO-API-KEY"] = self.api_key

        self._abi_codec = Web3().codec
        self._contract_abi_map: Dict[str, List[Dict[str, Any]]] = {}
        self._event_signature_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._load_contract_abis()

    async def connect(self) -> None:
        await self._ensure_session()

    async def disconnect(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

        for client in self._clients.values():
            try:
                client.provider.sess.close()
            except Exception as exc:
                self.logger.warning("Failed to close Tron client session cleanly: %s", exc)
        self._clients.clear()

    def is_connected(self) -> bool:
        return self._session is not None and not self._session.closed

    async def get_latest_block_number(self) -> int:
        async def get_tron_lastest_block_number(client: Tron) -> int:
            return client.get_latest_block_number()
        return await self._execute_with_client(get_tron_lastest_block_number)

    async def get_logs(
        self,
        address: Optional[Union[str, List[str]]] = None,
        from_block: Optional[Union[int, str]] = None,
        to_block: Optional[Union[int, str]] = None,
        event_filters: Optional[Dict[str, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        if address is None:
            raise BlockchainAdapterError(
                "TronAdapter requires a contract address to query logs",
                blockchain=self.name,
                network=self.network,
            )

        if isinstance(address, str):
            contract_addresses = [address]
        else:
            contract_addresses = list(address)

        min_timestamp = await self._block_to_timestamp(from_block)
        max_timestamp = await self._block_to_timestamp(to_block)

        logs: List[Dict[str, Any]] = []
        for contract in contract_addresses:
            contract_filters = (event_filters or {}).get(contract) or []

            if contract_filters:
                for event_name in contract_filters:
                    events = await self._fetch_contract_events(
                        contract,
                        event_name=event_name,
                        min_timestamp=min_timestamp,
                        max_timestamp=max_timestamp,
                    )
                    logs.extend(events)

        return logs

    def decode_event(self, event: RawEvent) -> Union[DecodedEvent, Awaitable[DecodedEvent]]:
        decoded_with_abi = self._decode_event_via_abi(event)
        if decoded_with_abi:
            return decoded_with_abi

        raw = event.raw_data or {}
        parameters = raw.get("result", {})
        event_name = raw.get("event_name") or raw.get("event") or "TronEvent"
        timestamp = raw.get("timestamp") or event.timestamp or 0

        return DecodedEvent(
            chain_type=event.chain_type,
            contract_address=event.contract_address,
            event_name=event_name,
            parameters=parameters,
            block_number=event.block_number,
            transaction_hash=event.transaction_hash,
            log_index=event.log_index,
            timestamp=int(timestamp),
        )

    def _get_or_create_client(self, endpoint: str) -> Tron:
        if endpoint not in self._clients:
            api_key = self.api_key
            if hasattr(self._connection_pool, "get_endpoint_meta"):
                meta = self._connection_pool.get_endpoint_meta(endpoint)
                api_key = meta.get("api_key") or api_key

            provider = HTTPProvider(
                endpoint_uri=endpoint,
                timeout=self.rpc_config.get("timeout", 30),
                api_key=api_key,
            )
            self._clients[endpoint] = Tron(provider=provider)
        return self._clients[endpoint]

    async def _fetch_contract_events(
        self,
        contract_address: str,
        event_name: Optional[str],
        min_timestamp: Optional[int],
        max_timestamp: Optional[int],
    ) -> List[Dict[str, Any]]:
        page = 1
        events: List[Dict[str, Any]] = []

        while page <= self.max_event_pages:
            params: Dict[str, Any] = {
                "only_confirmed": "true",
                "limit": self.event_page_size,
                "order_by": "block_timestamp,asc",
                "page": page,
            }
            if event_name:
                params["event_name"] = event_name
            if min_timestamp is not None:
                params["min_block_timestamp"] = min_timestamp
            if max_timestamp is not None:
                params["max_block_timestamp"] = max_timestamp

            response = await self._get(
                f"v1/contracts/{contract_address}/events",
                params=params,
            )
            data = response.get("data", []) or []
            if not data:
                break

            for entry in data:
                events.append(self._normalize_event(contract_address, entry))

            if len(data) < self.event_page_size:
                break
            page += 1

        return events

    def _normalize_event(self, contract_address: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        timestamp_ms = entry.get("block_timestamp")
        timestamp = int(timestamp_ms / 1000) if isinstance(timestamp_ms, (int, float)) else 0

        topics = entry.get("topic") or entry.get("topics") or []
        normalized_topics = self._normalize_topics(topics)
        data_field = entry.get("data")
        normalized_data = self._normalize_hex_data(data_field)

        return {
            "address": contract_address,
            "contract_address": contract_address,
            "block_number": entry.get("block_number"),
            "block_hash": entry.get("block_hash") or entry.get("transaction_id"),
            "transaction_hash": entry.get("transaction_id"),
            "log_index": entry.get("log_index", entry.get("transaction_index", 0)),
            "timestamp": timestamp,
            "event_name": entry.get("event_name"),
            "result": entry.get("result", {}),
            "topics": normalized_topics,
            "data": normalized_data,
            "raw_event": entry,
        }

    async def _block_to_timestamp(self, block_reference: Optional[Union[int, str]]) -> Optional[int]:
        if block_reference is None:
            return None

        if isinstance(block_reference, str):
            if block_reference == "latest":
                return None
            block_reference = int(block_reference, 0)

        block_number = int(block_reference)

        if block_number in self._timestamp_cache:
            return self._timestamp_cache[block_number]

        def fetch_block(client: Tron) -> Optional[int]:
            block = client.get_block(block_number)
            header = block.get("block_header", {}).get("raw_data", {})
            return header.get("timestamp")

        timestamp = await self._execute_with_client(fetch_block)
        if timestamp is not None:
            self._timestamp_cache[block_number] = int(timestamp)
            return int(timestamp)
        return None

    def _event_name_from_topics(self, topics: Optional[List[str]]) -> Optional[str]:
        if not topics:
            return None

        first = topics[0]
        if not isinstance(first, str):
            return None

        normalized = first.lower()
        return self.TOPIC_TO_EVENT.get(normalized)

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session

        async with self._session_lock:
            if self._session and not self._session.closed:
                return self._session

            timeout = aiohttp.ClientTimeout(total=self.rpc_config.get("timeout", 30))
            self._session = aiohttp.ClientSession(timeout=timeout)
            return self._session

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._api_request("GET", path, params=params)

    async def _post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._api_request("POST", path, json_data=payload)

    async def _api_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        endpoint = self._connection_pool.get_next_connection()
        url = f"{endpoint.rstrip('/')}/{path.lstrip('/')}"
        session = await self._ensure_session()

        async def operation():
            async with session.request(
                method,
                url,
                params=params,
                json=json_data,
                headers=self._default_headers or None,
            ) as response:
                try:
                    data = await response.json(content_type=None)
                except aiohttp.ContentTypeError:
                    text = await response.text()
                    raise BlockchainAdapterError(
                        f"Invalid Tron API response: {text}",
                        blockchain=self.name,
                        network=self.network,
                        details={"url": url, "status": response.status},
                    )

                if response.status >= 400:
                    raise BlockchainAdapterError(
                        f"Tron API error: {data}",
                        blockchain=self.name,
                        network=self.network,
                        details={"url": url, "status": response.status},
                    )
                return data or {}

        try:
            result = await self._execute_with_rate_limit(operation)
            self._connection_pool.mark_success(endpoint)
            return result
        except Exception as exc:
            self._connection_pool.mark_failure(endpoint)
            raise exc

    def _normalize_contract_address(self, address: Optional[str]) -> Optional[str]:
        if not address:
            return None
        if isinstance(address, str) and address.startswith("0x"):
            return address.lower()
        return address

    def _ensure_hex_prefixed(self, value: str) -> str:
        normalized = value.lower()
        return normalized if normalized.startswith("0x") else f"0x{normalized}"

    def _normalize_topics(self, topics: Union[List[Any], str]) -> List[str]:
        if isinstance(topics, str):
            topics = [topics]
        normalized: List[str] = []
        for topic in topics:
            if isinstance(topic, HexBytes):
                normalized.append(topic.hex().lower())
            elif isinstance(topic, (bytes, bytearray)):
                normalized.append(HexBytes(topic).hex().lower())
            elif isinstance(topic, str):
                normalized.append(self._ensure_hex_prefixed(topic))
        return normalized

    def _normalize_hex_data(self, data: Optional[Union[str, bytes]]) -> str:
        if data is None:
            return "0x"
        if isinstance(data, HexBytes):
            return data.hex()
        if isinstance(data, (bytes, bytearray)):
            return HexBytes(data).hex()
        if isinstance(data, str):
            return self._ensure_hex_prefixed(data)
        return "0x"

    def _as_hexbytes(self, value: str) -> HexBytes:
        return HexBytes(self._ensure_hex_prefixed(value))

    def _load_contract_abis(self) -> None:
        for contract in self._contract_configs:
            address = contract.get("address")
            abi_path = contract.get("abi_path")
            if not address or not abi_path:
                continue

            abi = self._load_contract_abi(abi_path)
            if not abi:
                continue

            normalized_address = self._normalize_contract_address(address)
            if not normalized_address:
                continue

            self._contract_abi_map[normalized_address] = abi

            topic_map: Dict[str, Dict[str, Any]] = {}
            for entry in abi:
                if entry.get("type") != "event":
                    continue
                try:
                    topic_bytes = event_abi_to_log_topic(entry)
                    topic = f"0x{topic_bytes.hex().lower()}"
                    topic_map[topic] = entry
                except Exception as exc:
                    self.logger.debug(
                        "Failed to register Tron ABI event %s for %s: %s",
                        entry.get("name"),
                        normalized_address,
                        exc,
                    )

            if topic_map:
                self._event_signature_map[normalized_address] = topic_map

    def _decode_event_via_abi(self, event: RawEvent) -> Optional[DecodedEvent]:
        normalized_address = self._normalize_contract_address(event.contract_address)
        if not normalized_address:
            return None

        topic_map = self._event_signature_map.get(normalized_address)
        if not topic_map:
            return None

        raw_data = event.raw_data or {}
        topics = raw_data.get("topics") or []
        if not topics:
            return None

        topic_key = self._ensure_hex_prefixed(topics[0])
        event_abi = topic_map.get(topic_key.lower())
        if not event_abi:
            return None

        try:
            transaction_index = raw_data.get("transaction_index", raw_data.get("transactionIndex", 0))
            log_entry_dict = {
                "address": normalized_address,
                "topics": [self._as_hexbytes(topic) for topic in topics],
                "data": raw_data.get("data", "0x"),
                "blockNumber": event.block_number,
                "logIndex": event.log_index,
                "transactionIndex": transaction_index if transaction_index is not None else 0,
            }

            if event.transaction_hash:
                log_entry_dict["transactionHash"] = self._as_hexbytes(event.transaction_hash)
            if event.block_hash:
                log_entry_dict["blockHash"] = self._as_hexbytes(event.block_hash)

            log_entry = AttributeDict(log_entry_dict)
            decoded = get_event_data(self._abi_codec, event_abi, log_entry)
        except Exception as exc:
            self.logger.debug(
                "Tron ABI decode failed for %s on %s: %s",
                normalized_address,
                event.transaction_hash,
                exc,
            )
            return None

        parameters = dict(decoded["args"])
        timestamp = raw_data.get("timestamp", event.timestamp)
        event_name = event_abi.get("name") or raw_data.get("event_name") or "TronEvent"

        return DecodedEvent(
            chain_type=event.chain_type,
            contract_address=normalized_address,
            event_name=event_name,
            parameters=parameters,
            block_number=event.block_number,
            transaction_hash=event.transaction_hash,
            log_index=event.log_index,
            timestamp=int(timestamp) if timestamp is not None else 0,
        )
    
    async def get_block_by_number(self, block_number: int) -> Optional[Dict[str, Any]]:
        async def fetch_block(client: Tron) -> Optional[Dict[str, Any]]:
            block = client.get_block(block_number)
            return block

        try:
            block = await self._execute_with_client(fetch_block)
            return block
        except KeyError:
            raise BlockchainAdapterError(
                f"Block {block_number} not found",
                blockchain=self.name,
                network=self.network,
                block_number=block_number
            )
        except Exception as e:
            self.logger.error(f"Error fetching block {block_number}: {e}")
            raise BlockchainAdapterError(
                f"Error fetching block {block_number}: {e}",
                blockchain=self.name,
                network=self.network,
                block_number=block_number
            )
