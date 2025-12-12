"""Ethereum blockchain adapter implementation.

This module provides the Ethereum-specific implementation of the blockchain adapter,
using Web3.py for interaction with Ethereum nodes. It supports both mainnet and
testnet networks, with comprehensive error handling and retry logic.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator, Union, Callable
from datetime import datetime, timezone

from web3 import Web3
from web3.exceptions import (
    BlockNotFound,
    TimeExhausted,
    TransactionNotFound,
    ValidationError as Web3ValidationError
)

from chain_listener.adapters.base import BaseAdapter, PriorityConnectionPool
from chain_listener.exceptions import (
    BlockchainAdapterError,
    ConnectionError as ChainConnectionError,
    BlockNotFoundError,
    TransactionError,
    SubscriptionError,
    RateLimitError
)


class EthereumAdapter(BaseAdapter):
    """Ethereum-specific blockchain adapter.

    Provides comprehensive Ethereum blockchain interaction capabilities including
    block queries, log filtering, transaction retrieval, and event streaming.
    """

    # Default configuration
    DEFAULT_CONFIG = {
        "block_time": 12
    }

    def __init__(self, config: Dict[str, Any]):
        """Initialize Ethereum adapter.

        Args:
            config: Ethereum-specific configuration

        Raises:
            ValueError: If network or configuration is invalid
        """
        # Custom initialization (don't call super().__init__ to avoid old config validation)
        self._validate_config(config)

        # Set basic properties (with defaults for optional fields)
        self.name = config.get("name", "ethereum_adapter")
        self.network = config.get("network", "mainnet")
        self.rpc_config = config.get("rpc", {})

        # Validate Ethereum-specific configuration
        self._validate_ethereum_config(config)

        # Set properties (allow user override)
        self.block_time = config.get("block_time", self.DEFAULT_CONFIG["block_time"])

        # Priority connection management
        rpc_endpoints = config.get("rpc_endpoints", [])
        max_retries = self.rpc_config.get("retries", 3)
        self._connection_pool = PriorityConnectionPool(rpc_endpoints, max_retries)

        # Web3 instances cache (one per endpoint)
        self._web3_instances: Dict[str, Web3] = {}

        # Contract cache for event subscriptions
        self._contract_cache: Dict[str, Any] = {}

        # Event filter cache
        self._filter_cache: Dict[str, Any] = {}

        # Rate limiting and logging
        from ..adapters.base import RateLimiter
        rate_limit_config = self.rpc_config.get("rate_limit", {})
        self._rate_limiter = RateLimiter(
            requests_per_second=rate_limit_config.get("requests_per_second", 10),
            burst_size=rate_limit_config.get("burst_size", 20)
        )

        # Request tracking
        self._request_count = 0
        self._error_count = 0

        self.logger = logging.getLogger(__name__)

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate adapter configuration for the new format.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        if not config:
            raise ValueError("Configuration cannot be empty")
        if "rpc_endpoints" not in config:
            raise ValueError("Missing required config: rpc_endpoints")
        if not config["rpc_endpoints"]:
            raise ValueError("RPC URLs required")

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
            url = self._connection_pool.get_best_endpoint()

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

    def _validate_ethereum_config(self, config: Dict[str, Any]) -> None:
        """Validate Ethereum-specific configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate RPC URLs for Ethereum
        rpc_config = config.get("rpc", {})
        urls = rpc_config.get("urls", [])

        for url in urls:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid Ethereum RPC URL: {url}")

    
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
        to_block: Optional[int] = None
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
        def get_logs_operation(w3):
            # Build filter parameters
            filter_params = {}
            if address:
                filter_params["address"] = address
            if topics:
                filter_params["topics"] = topics
            if from_block is not None:
                filter_params["fromBlock"] = from_block
            if to_block is not None:
                filter_params["toBlock"] = to_block

            return w3.eth.get_logs(filter_params)

        logs = await self._execute_with_priority_routing(get_logs_operation)
        return [self._convert_log_to_standard_format(log) for log in logs]

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

    async def subscribe_to_contract_events(
        self,
        address: str,
        events: List[str]
    ) -> str:
        """Subscribe to events from a specific Ethereum contract.

        Args:
            address: Contract address to subscribe to
            events: List of event names to subscribe to

        Returns:
            Subscription ID for managing the subscription

        Raises:
            SubscriptionError: If subscription fails
        """
        # Direct execution - HTTP RPC doesn't need connection management

        try:
            # Get or create contract instance
            contract = await self._get_contract_instance(address)

            # Create filters for each event
            filters = []
            for event_name in events:
                if hasattr(contract.events, event_name):
                    event = getattr(contract.events, event_name)
                    filter_obj = await self._execute_with_rate_limit(
                        event.create_filter
                    )
                    filters.append(filter_obj)
                else:
                    # Skip unknown events but continue
                    continue

            # Store subscription
            subscription_id = await super().subscribe_to_contract_events(address, events)

            # Store filters for this subscription
            self._filter_cache[subscription_id] = filters

            return subscription_id

        except Exception as e:
            self._handle_blockchain_error(e)

    async def _get_contract_instance(self, address: str) -> Any:
        """Get or create contract instance.

        Args:
            address: Contract address

        Returns:
            Web3 contract instance
        """
        if address not in self._contract_cache:
            # Create generic contract instance (ABI can be added later)
            contract = await self._execute_with_rate_limit(
                self._w3.eth.contract,
                address=address
            )
            self._contract_cache[address] = contract

        return self._contract_cache[address]

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

    async def batch_get_logs(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Get logs for multiple requests in batch from Ethereum.

        Args:
            requests: List of log request dictionaries

        Returns:
            List of log lists, one for each request

        Raises:
            BlockchainAdapterError: If any request fails
        """
        # Direct execution - HTTP RPC doesn't need connection management

        # Use base implementation with rate limiting
        return await super().batch_get_logs(requests)

    def get_metadata(self) -> Dict[str, Any]:
        """Get Ethereum adapter metadata and capabilities.

        Returns:
            Metadata dictionary with Ethereum-specific info
        """
        base_metadata = super().get_metadata()

        # Add Ethereum-specific metadata
        base_metadata.update({
            "chain_id": self.chain_id,
            "block_time": self.block_time,
            "supports": {
                **base_metadata["supports"],
                "contract_events": True,
                "event_filters": True,
                "transaction_receipts": True,
                "gas_tracking": True,
                "nonce_tracking": True
            },
            "features": {
                "eip1559": True,  # EIP-1559 transaction type support
                "smart_contracts": True,
                "erc20": True,
                "erc721": True,
                "erc1155": True
            }
        })

        return base_metadata

    def get_health_status(self) -> Dict[str, Any]:
        """Get Ethereum adapter health status.

        Returns:
            Health status dictionary with Ethereum-specific metrics
        """
        base_health = super().get_health_status()

        if self._w3 and self._w3.is_connected():
            try:
                # Add Ethereum-specific health checks
                sync_status = self._w3.eth.syncing

                if isinstance(sync_status, dict) and sync_status:
                    base_health.update({
                        "syncing": True,
                        "sync_status": {
                            "starting_block": sync_status.get("startingBlock"),
                            "current_block": sync_status.get("currentBlock"),
                            "highest_block": sync_status.get("highestBlock")
                        }
                    })
                else:
                    base_health["syncing"] = False

                # Add network info
                base_health.update({
                    "connected_chain_id": self._w3.eth.chain_id,
                    "latest_block": self._w3.eth.block_number,
                    "cached_contracts": len(self._contract_cache),
                    "active_filters": len(self._filter_cache)
                })

            except Exception:
                # Don't fail health check due to network issues
                pass

        return base_health

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