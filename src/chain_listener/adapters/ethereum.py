"""Ethereum blockchain adapter implementation.

This module provides the Ethereum-specific implementation of the blockchain adapter,
using Web3.py for interaction with Ethereum nodes. It supports both mainnet and
testnet networks, with comprehensive error handling and retry logic.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator, Union, Callable, Set

from hexbytes import HexBytes
from eth_utils import event_abi_to_log_topic
from web3 import Web3
from web3.datastructures import AttributeDict
from web3.exceptions import (
    BlockNotFound,
    TransactionNotFound
)
from web3._utils.events import get_event_data

from chain_listener.adapters.base import BaseAdapter, PriorityConnectionPool
from chain_listener.models.events import RawEvent, DecodedEvent
from chain_listener.exceptions import (
    BlockchainAdapterError,
    ConnectionError as ChainConnectionError,
    BlockNotFoundError,
    TransactionError,
    RateLimitError
)


class EthereumAdapter(BaseAdapter):
    """Ethereum-specific blockchain adapter.

    Provides comprehensive Ethereum blockchain interaction capabilities including
    block queries, log filtering, transaction retrieval, and event streaming.
    """

    # Default configuration
    DEFAULT_CONFIG = {
        "block_time": 12,
        # Conservative block-range chunk size; can be overridden via adapter_config
        "max_block_range": 10,
    }

    def __init__(self, config: Dict[str, Any]):
        """Initialize Ethereum adapter.

        Args:
            config: Ethereum-specific configuration

        Raises:
            ValueError: If network or configuration is invalid
        """
        # Call parent initialization for standard functionality
        super().__init__(config)

        # Set properties (allow user override)
        self.block_time = config.get("block_time", self.DEFAULT_CONFIG["block_time"])
        max_range_config = config.get(
            "max_block_range",
            self.DEFAULT_CONFIG["max_block_range"]
        )
        try:
            self.max_block_range = max(1, int(max_range_config))
        except (TypeError, ValueError):
            self.max_block_range = self.DEFAULT_CONFIG["max_block_range"]
            logging.getLogger(__name__).warning(
                "Invalid max_block_range '%s', falling back to default %s",
                max_range_config,
                self.max_block_range,
            )

        # Web3 instances cache (one per endpoint)
        self._web3_instances: Dict[str, Web3] = {}

        # Contract cache for event subscriptions
        self._contract_cache: Dict[str, Any] = {}

        # Event filter cache
        self._filter_cache: Dict[str, Any] = {}

        self.logger = logging.getLogger(__name__)
        self._w3 = None

        # ABI decoding helpers
        self._abi_codec = Web3().codec
        self._contract_abi_map: Dict[str, List[Dict[str, Any]]] = {}
        self._event_signature_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._event_name_topic_map: Dict[str, Dict[str, str]] = {}
        self._load_contract_abis()

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate adapter configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        # Call parent validation for standard config validation
        super()._validate_config(config)

    def _get_or_create_web3_instance(self, url: str) -> Web3:
        """获取或创建 Web3 实例（带缓存）"""
        if url not in self._web3_instances:
            self._web3_instances[url] = Web3(Web3.HTTPProvider(
                url,
                request_kwargs={
                    "timeout": self.rpc_config.get("timeout", 30)
                }
            ))
        return self._web3_instances[url]

    async def _execute_with_priority_routing(self, operation: Callable, *args, **kwargs) -> Any:
        """使用优先级路由执行操作"""
        last_exception = None

        # 尝试所有端点，最多 max_retries 次
        max_retries = self._connection_pool.max_retries
        for attempt in range(max_retries + 1):
            # 获取当前最佳端点
            url = self._connection_pool.get_next_connection()

            # 获取 Web3 实例
            w3 = self._get_or_create_web3_instance(url)

            try:
                # 执行操作
                result = await self._execute_with_rate_limit(
                    lambda: operation(w3, *args, **kwargs)
                )

                # 标记成功
                self._connection_pool.mark_success(url)
                return result

            except Exception as e:
                last_exception = e
                # 标记失败
                self._connection_pool.mark_failure(url)

                # 如果不是最后一次尝试，记录日志并继续
                if attempt < max_retries:
                    self.logger.warning(
                        f"RPC endpoint {url} failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    continue

        # 所有重试都失败了
        raise BlockchainAdapterError(
            f"All RPC endpoints failed after {max_retries} retries: {last_exception}"
        )

    
    async def connect(self) -> None:
        """Connect to Ethereum network.

        For HTTP RPC, connection is stateless and handled per-request.
        This method is a no-op but kept for interface compatibility.
        """
        # No-op for HTTP RPC - connection handled per-request
        pass

    async def disconnect(self) -> None:
        """Disconnect from Ethereum network.

        For HTTP RPC, this just clears cached instances.
        No actual connection to close since HTTP is stateless.
        """
        self._w3 = None
        self._contract_cache.clear()
        self._filter_cache.clear()

    def is_connected(self) -> bool:
        """Check if adapter is connected to Ethereum network.

        Returns:
            True if connected, False otherwise
        """
        return self._w3 is not None and self._w3.is_connected()

    
    async def get_latest_block_number(self) -> int:
        """Get the latest block number from Ethereum.

        Returns:
            Latest block number

        Raises:
            BlockchainAdapterError: If request fails
        """
        return await self._execute_with_priority_routing(
            lambda w3: w3.eth.block_number
        )

    async def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
        """Get block information by number from Ethereum.

        Args:
            block_number: Block number to retrieve

        Returns:
            Block information dictionary

        Raises:
            BlockNotFoundError: If block is not found
            BlockchainAdapterError: If request fails
        """
        # Direct execution - HTTP RPC doesn't need connection management

        try:
            block = await self._execute_with_rate_limit(
                self._w3.eth.get_block,
                block_number
            )

            if block is None:
                raise BlockNotFoundError(
                    f"Block {block_number} not found",
                    blockchain=self.name,
                    network=self.network,
                    block_number=block_number
                )

            # Convert to standardized format
            return {
                "number": block.number,
                "hash": block.hash.hex() if block.hash else None,
                "parent_hash": block.parentHash.hex() if block.parentHash else None,
                "timestamp": block.timestamp,
                "transactions": [tx.hex() for tx in block.transactions],
                "transaction_count": len(block.transactions),
                "gas_limit": block.gasLimit,
                "gas_used": block.gasUsed,
                "miner": block.miner.hex() if block.miner else None,
                "difficulty": block.difficulty,
                "total_difficulty": block.totalDifficulty,
                "size": block.size,
                "uncles": [uncle.hex() for uncle in block.uncles] if block.uncles else [],
                "extra_data": block.extraData.hex() if block.extraData else None,
                "logs_bloom": block.logsBloom.hex() if block.logsBloom else None,
                "mix_hash": block.mixHash.hex() if block.mixHash else None,
                "nonce": block.nonce.hex() if block.nonce else None,
                "receipts_root": block.receiptsRoot.hex() if block.receiptsRoot else None,
                "sha3_uncles": block.sha3Uncles.hex() if block.sha3Uncles else None,
                "state_root": block.stateRoot.hex() if block.stateRoot else None,
                "transactions_root": block.transactionsRoot.hex() if block.transactionsRoot else None
            }

        except BlockNotFound:
            raise BlockNotFoundError(
                f"Block {block_number} not found",
                blockchain=self.name,
                network=self.network,
                block_number=block_number
            )
        except Exception as e:
            self._handle_blockchain_error(e)

    async def get_logs(
        self,
        address: Optional[Union[str, List[str]]] = None,
        topics: Optional[List[str]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        event_filters: Optional[Dict[str, List[str]]] = None
    ) -> List[Dict[str, Any]]:
        """Get logs matching criteria from Ethereum.

        Args:
            address: Contract address to filter by (single address or list of addresses)
            topics: Event topics to filter by
            from_block: Starting block number
            to_block: Ending block number

        Returns:
            List of log entries

        Raises:
            BlockchainAdapterError: If request fails
        """
        topic_filter = self._build_topic_filters(event_filters)

        def _format_block_param(value: Optional[Union[int, str]]) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, str):
                return value
            if isinstance(value, int):
                if value < 0:
                    raise ValueError("Block number cannot be negative")
                return hex(value)
            raise TypeError(f"Unsupported block parameter type: {type(value)}")

        block_ranges = self._build_block_ranges(from_block, to_block)
        all_logs: List[Dict[str, Any]] = []

        for chunk_from, chunk_to in block_ranges:

            def get_logs_operation(w3, chunk_from=chunk_from, chunk_to=chunk_to):
                # Build filter parameters
                filter_params = {}
                if address:
                    filter_params["address"] = address
                if topic_filter:
                    filter_params["topics"] = topic_filter
                elif topics:
                    filter_params["topics"] = topics
                formatted_from = _format_block_param(chunk_from)
                formatted_to = _format_block_param(chunk_to)
                if formatted_from is not None:
                    filter_params["fromBlock"] = formatted_from
                if formatted_to is not None:
                    filter_params["toBlock"] = formatted_to

                self.logger.debug(
                    "Fetching logs with params: address=%s, from=%s, to=%s, topics=%s",
                    filter_params.get("address"),
                    filter_params.get("fromBlock"),
                    filter_params.get("toBlock"),
                    filter_params.get("topics"),
                )

                return w3.eth.get_logs(filter_params)

            logs = await self._execute_with_priority_routing(get_logs_operation)
            all_logs.extend(
                self._convert_log_to_standard_format(log)
                for log in logs
            )

        return all_logs

    def _build_topic_filters(
        self, event_filters: Optional[Dict[str, List[str]]]
    ) -> Optional[List[List[str]]]:
        if not event_filters:
            return None

        topics: Set[str] = set()

        for address, events in event_filters.items():
            normalized_address = self._normalize_contract_address(address)
            name_map = self._event_name_topic_map.get(normalized_address)
            if not name_map:
                raise BlockchainAdapterError(
                    f"No ABI topics are available for contract {address}"
                )

            for event_name in events or []:
                topic = name_map.get(event_name)
                if not topic:
                    raise BlockchainAdapterError(
                        f"Event '{event_name}' is not defined in ABI for contract {address}"
                    )
                topics.add(topic)

        if not topics:
            return None

        return [list(topics)]

    def _build_block_ranges(
        self,
        from_block: Optional[Union[int, str]],
        to_block: Optional[Union[int, str]]
    ) -> List[tuple]:
        """Split the requested range into max_block_range-sized chunks."""
        if (
            isinstance(from_block, int)
            and isinstance(to_block, int)
            and to_block >= from_block
        ):
            ranges: List[tuple] = []
            current = from_block
            while current <= to_block:
                chunk_end = min(current + self.max_block_range - 1, to_block)
                ranges.append((current, chunk_end))
                current = chunk_end + 1
            return ranges

        # Non-integer or open-ended ranges can't be chunked safely
        return [(from_block, to_block)]

    def _convert_log_to_standard_format(self, log: Any) -> Dict[str, Any]:
        """Convert Web3 log to standard format.

        Args:
            log: Web3 log object

        Returns:
            Standardized log dictionary
        """
        return {
            "address": log.address,
            "topics": [topic.hex() for topic in log.topics],
            "data": log.data.hex() if log.data else "0x",
            "block_number": log.blockNumber,
            "block_hash": log.blockHash.hex() if log.blockHash else None,
            "transaction_hash": log.transactionHash.hex() if log.transactionHash else None,
            "transaction_index": log.transactionIndex,
            "log_index": log.logIndex,
            "removed": log.removed
        }

    async def get_transaction(self, transaction_hash: str) -> Dict[str, Any]:
        """Get transaction information by hash from Ethereum.

        Args:
            transaction_hash: Transaction hash

        Returns:
            Transaction information dictionary

        Raises:
            TransactionError: If transaction is not found
            BlockchainAdapterError: If request fails
        """
        # Direct execution - HTTP RPC doesn't need connection management

        try:
            tx = await self._execute_with_rate_limit(
                self._w3.eth.get_transaction,
                transaction_hash
            )

            if tx is None:
                raise TransactionError(
                    f"Transaction {transaction_hash} not found",
                    blockchain=self.name,
                    network=self.network,
                    transaction_hash=transaction_hash
                )

            # Convert to standardized format
            return {
                "hash": tx.hash.hex(),
                "block_number": tx.blockNumber,
                "block_hash": tx.blockHash.hex() if tx.blockHash else None,
                "transaction_index": tx.transactionIndex,
                "from_address": tx["from"],
                "to_address": tx.to,
                "value": str(tx.value),
                "gas": tx.gas,
                "gas_price": str(tx.gasPrice) if tx.gasPrice else None,
                "max_fee_per_gas": str(tx.maxFeePerGas) if hasattr(tx, 'maxFeePerGas') and tx.maxFeePerGas else None,
                "max_priority_fee_per_gas": str(tx.maxPriorityFeePerGas) if hasattr(tx, 'maxPriorityFeePerGas') and tx.maxPriorityFeePerGas else None,
                "input": tx.input.hex() if tx.input else "0x",
                "nonce": tx.nonce,
                "type": tx.type if hasattr(tx, 'type') else 0,
                "chain_id": tx.chainId if hasattr(tx, 'chainId') else self.chain_id,
                "v": tx.v,
                "r": tx.r,
                "s": tx.s,
                "y_parity": tx.yParity if hasattr(tx, 'yParity') else None
            }

        except TransactionNotFound:
            raise TransactionError(
                f"Transaction {transaction_hash} not found",
                blockchain=self.name,
                network=self.network,
                transaction_hash=transaction_hash
            )
        except Exception as e:
            self._handle_blockchain_error(e)

    async def get_events_stream(
        self,
        address: Optional[str] = None,
        topics: Optional[List[str]] = None,
        from_block: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream Ethereum events in real-time.

        Args:
            address: Contract address to filter by
            topics: Event topics to filter by
            from_block: Starting block number

        Yields:
            Event dictionaries as they occur

        Raises:
            BlockchainAdapterError: If streaming fails
        """
        # Direct execution - HTTP RPC doesn't need connection management

        current_block = from_block or await self.get_latest_block_number()

        while True:
            try:
                # Get latest block number
                latest_block = await self.get_latest_block_number()

                if latest_block > current_block:
                    # Get new logs
                    logs = await self.get_logs(
                        address=address,
                        topics=topics,
                        from_block=current_block + 1,
                        to_block=latest_block
                    )

                    for log in logs:
                        yield log

                    current_block = latest_block

                # Wait for next block (Ethereum average block time)
                await asyncio.sleep(self.block_time / 2)

            except Exception as e:
                self._handle_blockchain_error(e)
                # Wait before retrying
                await asyncio.sleep(self.block_time)

    async def get_transaction_receipt(self, transaction_hash: str) -> Dict[str, Any]:
        """Get transaction receipt by hash from Ethereum.

        Args:
            transaction_hash: Transaction hash

        Returns:
            Transaction receipt dictionary

        Raises:
            TransactionError: If transaction is not found
            BlockchainAdapterError: If request fails
        """
        # Direct execution - HTTP RPC doesn't need connection management

        try:
            receipt = await self._execute_with_rate_limit(
                self._w3.eth.get_transaction_receipt,
                transaction_hash
            )

            if receipt is None:
                raise TransactionError(
                    f"Transaction receipt {transaction_hash} not found",
                    blockchain=self.name,
                    network=self.network,
                    transaction_hash=transaction_hash
                )

            # Convert to standardized format
            return {
                "transaction_hash": receipt.transactionHash.hex(),
                "transaction_index": receipt.transactionIndex,
                "block_number": receipt.blockNumber,
                "block_hash": receipt.blockHash.hex() if receipt.blockHash else None,
                "gas_used": receipt.gasUsed,
                "cumulative_gas_used": receipt.cumulativeGasUsed,
                "contract_address": receipt.contractAddress,
                "logs": [self._convert_log_to_standard_format(log) for log in receipt.logs],
                "status": receipt.status == 1 if receipt.status is not None else None,
                "effective_gas_price": str(receipt.effectiveGasPrice) if receipt.effectiveGasPrice else None,
                "type": receipt.type if hasattr(receipt, 'type') else 0
            }

        except Exception as e:
            self._handle_blockchain_error(e)

    async def get_balance(self, address: str) -> int:
        """Get ETH balance for an address.

        Args:
            address: Ethereum address

        Returns:
            Balance in wei

        Raises:
            BlockchainAdapterError: If request fails
        """
        # Direct execution - HTTP RPC doesn't need connection management

        try:
            balance = await self._execute_with_rate_limit(
                self._w3.eth.get_balance,
                address
            )
            return int(balance)

        except Exception as e:
            self._handle_blockchain_error(e)

    def _normalize_contract_address(self, address: Optional[str]) -> Optional[str]:
        if not address:
            return None
        try:
            return Web3.to_checksum_address(address)
        except Exception:
            return address.lower()

    def _normalize_topic(self, topic: Union[str, bytes, HexBytes]) -> str:
        if isinstance(topic, HexBytes):
            return topic.hex().lower()
        if isinstance(topic, (bytes, bytearray)):
            return HexBytes(topic).hex().lower()
        if isinstance(topic, str):
            normalized = topic if topic.startswith("0x") else f"0x{topic}"
            return normalized.lower()
        raise TypeError(f"Unsupported topic type: {type(topic)}")

    def _as_hexbytes(self, value: Union[str, bytes, HexBytes]) -> HexBytes:
        if isinstance(value, HexBytes):
            return value
        if isinstance(value, (bytes, bytearray)):
            return HexBytes(value)
        if isinstance(value, str):
            normalized = value if value.startswith("0x") else f"0x{value}"
            return HexBytes(normalized)
        raise TypeError(f"Unsupported hex value: {type(value)}")

    def _load_contract_abis(self) -> None:
        """Load ABI definitions for configured contracts."""
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
            name_map = self._event_name_topic_map.setdefault(normalized_address, {})
            for entry in abi:
                if entry.get("type") != "event":
                    continue
                try:
                    topic_bytes = event_abi_to_log_topic(entry)
                    topic = f"0x{topic_bytes.hex().lower()}"
                    topic_map[topic] = entry
                    event_name = entry.get("name")
                    if event_name:
                        if event_name in name_map and name_map[event_name] != topic:
                            self.logger.warning(
                                "Duplicate event definition detected for %s on %s; using first seen signature",
                                event_name,
                                normalized_address,
                            )
                            continue
                        name_map[event_name] = topic
                except Exception as exc:
                    self.logger.debug(
                        "Failed to register ABI event %s for %s: %s",
                        entry.get("name"),
                        normalized_address,
                        exc,
                    )

            if topic_map:
                self._event_signature_map[normalized_address] = topic_map

    def _decode_event_via_abi(self, event: RawEvent) -> Optional[DecodedEvent]:
        raw_data = event.raw_data or {}
        topics = raw_data.get("topics") or []
        if not topics:
            return None

        normalized_address = self._normalize_contract_address(event.contract_address)
        if not normalized_address:
            return None

        topic_map = self._event_signature_map.get(normalized_address)
        if not topic_map:
            return None

        try:
            topic_key = self._normalize_topic(topics[0])
        except Exception:
            return None

        event_abi = topic_map.get(topic_key)
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
                "ABI decode failed for %s on %s: %s",
                normalized_address,
                event.transaction_hash,
                exc,
            )
            return None

        parameters = dict(decoded["args"])
        timestamp = raw_data.get("timestamp", event.timestamp)
        event_name = event_abi.get("name") or raw_data.get("event_name") or raw_data.get("name") or "Unknown"

        return DecodedEvent(
            chain_type=event.chain_type,
            contract_address=normalized_address,
            event_name=event_name,
            parameters=parameters,
            block_number=event.block_number,
            transaction_hash=event.transaction_hash,
            log_index=event.log_index,
            timestamp=timestamp,
        )

    def decode_event(self, event: RawEvent) -> DecodedEvent:
        """Decode a raw Ethereum event using available metadata."""
        decoded_with_abi = self._decode_event_via_abi(event)
        if decoded_with_abi:
            return decoded_with_abi

        raw_data = event.raw_data or {}
        event_name = raw_data.get("event_name") or raw_data.get("name") or "Unknown"

        # Prefer parsed parameters from raw data if provided
        parameters = raw_data.get("parameters") or raw_data.get("args") or {}

        timestamp = raw_data.get("timestamp", event.timestamp)
        return DecodedEvent(
            chain_type=event.chain_type,
            contract_address=event.contract_address,
            event_name=event_name,
            parameters=parameters,
            block_number=event.block_number,
            transaction_hash=event.transaction_hash,
            log_index=event.log_index,
            timestamp=timestamp
        )
