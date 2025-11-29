"""Ethereum blockchain adapter implementation.

This module provides the Ethereum-specific implementation of the blockchain adapter,
using Web3.py for interaction with Ethereum nodes. It supports both mainnet and
testnet networks, with comprehensive error handling and retry logic.
"""

import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timezone

from web3 import Web3
from web3.exceptions import (
    BlockNotFound,
    TimeExhausted,
    TransactionNotFound,
    ValidationError as Web3ValidationError
)

from chain_listener.adapters.base import BaseBlockchainAdapter
from chain_listener.exceptions import (
    BlockchainAdapterError,
    ConnectionError as ChainConnectionError,
    BlockNotFoundError,
    TransactionError,
    SubscriptionError,
    RateLimitError
)


class EthereumAdapter(BaseBlockchainAdapter):
    """Ethereum-specific blockchain adapter.

    Provides comprehensive Ethereum blockchain interaction capabilities including
    block queries, log filtering, transaction retrieval, and event streaming.
    Supports mainnet, Goerli, Sepolia, and Holesky testnets.
    """

    # Network configurations
    NETWORK_CONFIGS = {
        "mainnet": {
            "chain_id": 1,
            "block_time": 12,
            "name": "Ethereum Mainnet"
        },
        "goerli": {
            "chain_id": 5,
            "block_time": 15,
            "name": "Goerli Testnet"
        },
        "sepolia": {
            "chain_id": 11155111,
            "block_time": 12,
            "name": "Sepolia Testnet"
        },
        "holesky": {
            "chain_id": 17000,
            "block_time": 12,
            "name": "Holesky Testnet"
        }
    }

    def __init__(self, config: Dict[str, Any]):
        """Initialize Ethereum adapter.

        Args:
            config: Ethereum-specific configuration

        Raises:
            ValueError: If network or configuration is invalid
        """
        super().__init__(config)

        # Validate Ethereum-specific configuration
        self._validate_ethereum_config(config)

        # Set network-specific properties
        network_config = self.NETWORK_CONFIGS[self.network]
        self.chain_id = network_config["chain_id"]
        self.block_time = network_config["block_time"]

        # Web3 instance (initialized in connect)
        self._w3: Optional[Web3] = None

        # Contract cache for event subscriptions
        self._contract_cache: Dict[str, Any] = {}

        # Event filter cache
        self._filter_cache: Dict[str, Any] = {}

    def _validate_ethereum_config(self, config: Dict[str, Any]) -> None:
        """Validate Ethereum-specific configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        network = config.get("network", "mainnet")

        if network not in self.NETWORK_CONFIGS:
            valid_networks = ", ".join(self.NETWORK_CONFIGS.keys())
            raise ValueError(
                f"Invalid Ethereum network: {network}. "
                f"Valid networks are: {valid_networks}"
            )

        # Validate RPC URLs for Ethereum
        rpc_config = config.get("rpc", {})
        urls = rpc_config.get("urls", [])

        for url in urls:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid Ethereum RPC URL: {url}")

    async def connect(self) -> None:
        """Connect to Ethereum network.

        Raises:
            ConnectionError: If connection fails
        """
        async with self._connection_lock:
            if self._connected:
                return

            # Get RPC endpoint from connection pool
            rpc_url = self._get_next_connection()

            try:
                # Create Web3 instance
                self._w3 = Web3(Web3.HTTPProvider(
                    rpc_url,
                    request_kwargs={
                        "timeout": self.rpc_config.get("timeout", 30)
                    }
                ))

                # Test connection
                if not self._w3.is_connected():
                    raise ChainConnectionError(
                        "Failed to connect to Ethereum node",
                        blockchain=self.name,
                        network=self.network,
                        endpoint=rpc_url
                    )

                # Verify chain ID matches expected network
                chain_id = self._w3.eth.chain_id
                if chain_id != self.chain_id:
                    raise ChainConnectionError(
                        f"Chain ID mismatch: expected {self.chain_id}, got {chain_id}",
                        blockchain=self.name,
                        network=self.network
                    )

                self._connected = True
                self._connection_pool.mark_success(rpc_url)

            except Exception as e:
                self._connection_pool.mark_failed(rpc_url)
                self._handle_blockchain_error(e)

    async def disconnect(self) -> None:
        """Disconnect from Ethereum network."""
        async with self._connection_lock:
            self._connected = False
            self._w3 = None
            self._contract_cache.clear()
            self._filter_cache.clear()

    async def get_latest_block_number(self) -> int:
        """Get the latest block number from Ethereum.

        Returns:
            Latest block number

        Raises:
            BlockchainAdapterError: If request fails
        """
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to Ethereum network",
                blockchain=self.name,
                network=self.network
            )

        try:
            return await self._execute_with_rate_limit(
                self._w3.eth.block_number
            )
        except Exception as e:
            self._handle_blockchain_error(e)

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
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to Ethereum network",
                blockchain=self.name,
                network=self.network
            )

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
        address: Optional[str] = None,
        topics: Optional[List[str]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get logs matching criteria from Ethereum.

        Args:
            address: Contract address to filter by
            topics: Event topics to filter by
            from_block: Starting block number
            to_block: Ending block number

        Returns:
            List of log entries

        Raises:
            BlockchainAdapterError: If request fails
        """
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to Ethereum network",
                blockchain=self.name,
                network=self.network
            )

        try:
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

            logs = await self._execute_with_rate_limit(
                self._w3.eth.get_logs,
                filter_params
            )

            # Convert to standardized format
            return [self._convert_log_to_standard_format(log) for log in logs]

        except Exception as e:
            self._handle_blockchain_error(e)

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
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to Ethereum network",
                blockchain=self.name,
                network=self.network
            )

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
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to Ethereum network",
                blockchain=self.name,
                network=self.network
            )

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
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to Ethereum network",
                blockchain=self.name,
                network=self.network
            )

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
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to Ethereum network",
                blockchain=self.name,
                network=self.network
            )

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
            "network_name": self.NETWORK_CONFIGS[self.network]["name"],
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

        if self._connected and self._w3:
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
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to Ethereum network",
                blockchain=self.name,
                network=self.network
            )

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
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to Ethereum network",
                blockchain=self.name,
                network=self.network
            )

        try:
            balance = await self._execute_with_rate_limit(
                self._w3.eth.get_balance,
                address
            )
            return int(balance)

        except Exception as e:
            self._handle_blockchain_error(e)