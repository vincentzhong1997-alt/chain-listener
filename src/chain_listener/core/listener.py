"""Main ChainListener class providing the unified API.

This module implements the main ChainListener class that serves as the
primary API for the blockchain listener SDK.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

from ..models.config import ChainListenerConfig, ChainConfig
from ..models.events import ChainType, RawEvent, is_evm_chain_type
from ..exceptions import ChainListenerError, BlockchainAdapterError
from ..adapters.base import BaseAdapter
from .adapter_registry import AdapterRegistry, adapter_registry
from .callback_registry import CallbackRegistry
from .event_processor import EventProcessor
from .state_manager import StateManager
from ..storage import StorageBackend

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ChainListener:
    """Main blockchain listener providing a unified API.

    This class serves as the primary interface for the blockchain listener SDK.
    It manages configuration, adapter registration, event listening, and callback
    execution through a simple, user-friendly API.
    """

    def __init__(
        self,
        config: ChainListenerConfig,
        storage_backend: Optional[StorageBackend] = None,
    ) -> None:
        """Initialize the chain listener.

        Args:
            config: Configuration for the chain listener
            storage_backend: Optional storage backend for persisting state.

        Raises:
            ChainListenerError: If configuration is invalid
        """
        self.config = config
        self._adapter_registry = adapter_registry
        self._callback_registry = CallbackRegistry()
        self._event_processor: Optional[EventProcessor] = None
        self._listening_tasks: Dict[ChainType, asyncio.Task] = {}
        self._is_listening = False
        self._state_manager = StateManager(
            storage_backend=storage_backend,
            key_prefix=self.config.storage.key_prefix,
        )

        # Validate configuration
        self._validate_config()

        # Initialize adapters
        self._initialize_adapters()

        # Initialize event processor
        self._event_processor = EventProcessor(
            config=self.config,
            callback_registry=self._callback_registry,
            adapter_registry=self._adapter_registry,
            state_manager=self._state_manager,
        )

        logger.info(f"ChainListener initialized with {len(config.chains)} chains")

    @classmethod
    def from_config_file(cls, config_path: str) -> 'ChainListener':
        """Create ChainListener from configuration file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            ChainListener: Configured chain listener instance

        Raises:
            ChainListenerError: If configuration file is invalid
        """
        try:
            config = ChainListenerConfig.from_file(config_path)
            return cls(config)
        except Exception as e:
            raise ChainListenerError(f"Failed to load configuration from {config_path}: {e}")

    def _validate_config(self) -> None:
        """Validate the configuration.

        Raises:
            ChainListenerError: If configuration is invalid
        """
        if not self.config.chains:
            raise ChainListenerError("At least one blockchain must be configured")

        # Validate each chain configuration
        for chain_name, chain_config in self.config.chains.items():
            if not chain_config.rpc.urls:
                raise ChainListenerError(f"No RPC URLs configured for chain: {chain_name}")

            if not chain_config.chain_type:
                raise ChainListenerError(f"No chain type specified for chain: {chain_name}")

    def set_storage_backend(self, storage_backend: StorageBackend) -> None:
        """Replace storage backend used for chain state persistence.

        Args:
            storage_backend: New backend instance implementing StorageBackend.

        Raises:
            ChainListenerError: If called while listener is running.
            TypeError: If backend does not implement StorageBackend.
        """
        if not isinstance(storage_backend, StorageBackend):
            raise TypeError("storage_backend must implement StorageBackend")

        if self._is_listening:
            raise ChainListenerError("Cannot change storage backend while listening")

        self._state_manager = StateManager(
            storage_backend=storage_backend,
            key_prefix=self.config.storage.key_prefix,
        )

        if self._event_processor is not None:
            self._event_processor._state_manager = self._state_manager

        logger.info("Storage backend has been updated")

    def _initialize_adapters(self) -> None:
        """Initialize blockchain adapters from configuration.

        Raises:
            ChainListenerError: If adapter initialization fails
        """
        try:
            # Initialize adapters for configured chains
            for chain_name, chain_config in self.config.chains.items():
                try:
                    chain_type = ChainType(chain_config.chain_type)
                    adapter_config = self._build_adapter_config(chain_config)
                    self._adapter_registry.register_adapter(
                        chain_type,
                        adapter_config
                    )
                    logger.info(f"Initialized adapter for {chain_name} ({chain_type})")
                except ValueError as e:
                    raise ChainListenerError(f"Invalid chain type for {chain_name}: {e}")
                except Exception as e:
                    raise ChainListenerError(f"Failed to initialize adapter for {chain_name}: {e}")

        except Exception as e:
            raise ChainListenerError(f"Failed to initialize adapters: {e}")

    def _build_adapter_config(self, chain_config: ChainConfig) -> Dict[str, Any]:
        """Build adapter configuration from chain configuration.

        Follows convention over configuration:
        - Users can override any adapter config via chain_config.adapter_config
        - Sensible defaults are used when no overrides provided
        - No intelligent inference - respects user choices

        Args:
            chain_config: The chain configuration

        Returns:
            Dict[str, Any]: Adapter configuration
        """

        # Use the new standardized RPC configuration
        # URL ordering determines priority (convention over configuration)
        rpc_headers = dict(chain_config.rpc.headers)
        for ep in chain_config.rpc.endpoints or []:
            api_key = ep.get("api_key")
            header_name = ep.get("api_key_header")
            if not api_key:
                continue
            if not header_name and chain_config.chain_type == "tron":
                header_name = "TRON-PRO-API-KEY"
            if header_name:
                rpc_headers[header_name] = api_key

        adapter_config = {
            "name": f"{chain_config.chain_type}_adapter",
            "network": "mainnet",
            "chain_type": chain_config.chain_type,
            "rpc": {
                "endpoints": chain_config.rpc.endpoints,
                "urls": chain_config.rpc.urls,
                "timeout": chain_config.rpc.timeout,
                "retries": chain_config.rpc.retries,
                "headers": rpc_headers,
                "rate_limit": {
                    "requests_per_second": chain_config.rpc.rate_limit.requests_per_second,
                    "burst_size": chain_config.rpc.rate_limit.burst_size
                }
            },
            "confirmation_blocks": chain_config.confirmation_blocks,
            "polling_interval": chain_config.polling_interval,
            "contracts": [
                {
                    "name": contract.name,
                    "address": contract.address,
                    "abi_path": contract.abi_path,
                    "events": contract.events
                }
                for contract in chain_config.contracts
            ]
        }

        return adapter_config

    def on_event(
        self,
        chain_name: str,
        contract_address: str,
        event_name: str,
        callback: Callable,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register an event callback.

        Args:
            chain_name: The name of the blockchain (from config)
            contract_address: The contract address to watch
            event_name: The event name to watch for
            callback: The callback function to execute
            metadata: Optional metadata for the callback

        Raises:
            ChainListenerError: If chain name is not configured
        """
        if chain_name not in self.config.chains:
            raise ChainListenerError(f"Chain '{chain_name}' is not configured")

        chain_config = self.config.chains[chain_name]
        try:
            chain_type = ChainType(chain_config.chain_type)
        except ValueError as exc:
            raise ChainListenerError(
                f"Invalid chain type '{chain_config.chain_type}' for {chain_name}"
            ) from exc

        contract_config = None
        normalized_input_address = contract_address.lower()
        for configured_contract in chain_config.contracts:
            if configured_contract.address.lower() == normalized_input_address:
                contract_config = configured_contract
                break

        if contract_config is None:
            raise ChainListenerError(
                f"Contract '{contract_address}' is not configured for chain '{chain_name}'"
            )

        if event_name not in (contract_config.events or []):
            raise ChainListenerError(
                f"Event '{event_name}' is not configured for contract '{contract_config.name}' on chain '{chain_name}'"
            )

        checksum_address = self._normalize_contract_address(chain_type, contract_address)

        metadata = (metadata or {}).copy()
        metadata.update({
            "chain_name": chain_name,
            "chain_type": chain_type.value,
        })

        self._callback_registry.register_callback(
            contract_address=checksum_address,
            event_name=event_name,
            callback=callback,
            metadata=metadata
        )

        logger.info(f"Registered callback for {event_name} on {contract_address}")

    async def start_listening(self) -> None:
        """Start listening for blockchain events.

        This method connects to all configured blockchains and starts
        listening for events based on the registered callbacks.

        Raises:
            ChainListenerError: If already listening or connection fails
        """
        if self._is_listening:
            raise ChainListenerError("Already listening for events")

        try:
            # Start listening tasks for each chain
            for chain_name, chain_config in self.config.get_enabled_chains().items():
                if chain_config.enabled:
                    chain_type = ChainType(chain_config.chain_type)
                    task = asyncio.create_task(
                        self._listen_to_chain(chain_name, chain_type, chain_config)
                    )
                    self._listening_tasks[chain_type] = task
                    logger.info(f"Started listening to {chain_name}")

            self._is_listening = True
            # State is managed through task lifecycle
            logger.info("ChainListener started successfully")

        except Exception as e:
            # Cleanup on failure
            await self._cleanup_listening_tasks()
            # Reset listening flag since start failed
            self._is_listening = False
            raise ChainListenerError(f"Failed to start listening: {e}")

    async def stop_listening(self) -> None:
        """Stop listening for blockchain events.

        This method stops all listening tasks and disconnects from blockchains.
        """
        if not self._is_listening:
            logger.warning("Not currently listening")
            return

        try:
            # Cancel all listening tasks
            await self._cleanup_listening_tasks()

            # Tasks will be marked as done when cancelled, no need to set flag
            logger.info("ChainListener stopped successfully")

        except Exception as e:
            logger.error(f"Error during stop: {e}")
            # Don't raise exception during cleanup
        finally:
            self._is_listening = False

    async def _cleanup_listening_tasks(self) -> None:
        """Clean up all listening tasks."""
        for chain_type, task in self._listening_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning(f"Error stopping listening task for {chain_type}: {e}")

        self._listening_tasks.clear()

    async def _listen_to_chain(
        self,
        chain_name: str,
        chain_type: ChainType,
        chain_config: ChainConfig
    ) -> None:
        """Listen to events from a specific blockchain.

        Args:
            chain_name: The name of the blockchain
            chain_type: The blockchain type
            chain_config: The chain configuration
        """
        logger.info(f"Starting to listen to {chain_name} ({chain_type})")

        try:
            adapter = self._adapter_registry.get_adapter(chain_type)

            # Determine starting point using persisted progress when available
            last_block = await self._get_last_processed_block(chain_type)

            while self.is_listening:
                try:
                    logger.debug(f"{chain_name} try get latest block")
                    # Get latest block
                    latest_block = await self._get_latest_block(adapter)

                    if latest_block > last_block:
                        logger.debug(f"{chain_name} found new block {latest_block}")

                        batch_size = self._get_block_batch_size(chain_type, chain_config)
                        while last_block < latest_block:
                            start_block = last_block + 1
                            end_block = min(start_block + batch_size - 1, latest_block)

                            events = await self._get_events_from_chain(
                                adapter, chain_type, start_block, end_block
                            )

                            if events:
                                # Process events
                                results = await self._event_processor.process_events(events)

                                # Log processing results
                                success_count = sum(1 for r in results if r.success)
                                if success_count > 0:
                                    logger.info(
                                        f"Processed {success_count} events from {chain_name} (blocks {start_block}-{end_block})"
                                    )

                            last_block = end_block

                            # Wait before next poll
                            await asyncio.sleep(chain_config.polling_interval / 1000.0)
                    else:
                        # No new blocks yet, still respect polling interval.
                        await asyncio.sleep(chain_config.polling_interval / 1000.0)

                except Exception as e:
                    logger.error(f"Error listening to {chain_name}: {e}")
                    await asyncio.sleep(5)  # Wait before retry

        except asyncio.CancelledError as e:
            logger.info(f"Stopped listening to {chain_name}")
            raise e
        except Exception as e:
            logger.error(f"Fatal error listening to {chain_name}: {e}")
            raise e

    def _get_block_batch_size(self, chain_type: ChainType, chain_config: ChainConfig) -> int:
        """Determine the max block batch size per chain type, with optional overrides."""
        # Per-chain sensible defaults; can be tuned as needed.
        if is_evm_chain_type(chain_type):
            batch = 500
        elif chain_type == ChainType.TRON:
            batch = 200
        elif chain_type == ChainType.SOLANA:
            batch = 1000
        else:
            batch = 500

        user_batch = chain_config.rpc.max_block_batch
        if isinstance(user_batch, int) and user_batch > 0:
            batch = user_batch

        return max(batch, 1)

    async def _get_latest_block(self, adapter: BaseAdapter) -> int:
        """Get the latest block number from an adapter.

        Args:
            adapter: The blockchain adapter

        Returns:
            int: Latest block number
        """
        return await adapter.get_latest_block_number()

    async def _get_events_from_chain(
        self,
        adapter: BaseAdapter,
        chain_type: ChainType,
        from_block: int,
        to_block: int
    ) -> List[RawEvent]:
        """Get events from a blockchain.

        Args:
            adapter: The blockchain adapter
            from_block: Starting block number
            to_block: Ending block number

        Returns:
            List[RawEvent]: List of raw events
        """
        events = []

        event_filters = self._build_event_filters(chain_type)
        if not event_filters:
            return events

        contract_addresses = set(event_filters.keys())

        if contract_addresses:
            # Get logs for watched contracts
            # All adapters must implement get_logs as it's an abstract method in BaseAdapter
            # Determine address parameter format
            if len(contract_addresses) == 0:
                address_param = None
            elif len(contract_addresses) == 1:
                address_param = next(iter(contract_addresses))
            else:
                address_param = list(contract_addresses)

            # Get logs with proper address format
            logs = await adapter.get_logs(
                from_block=from_block,
                to_block=to_block,
                address=address_param,
                event_filters=event_filters
            )

            # Convert logs to RawEvent objects
            for log in logs:
                    event = RawEvent(
                        chain_type=adapter.chain_type,
                        block_number=log.get('block_number', from_block),
                        block_hash=log.get('block_hash', ''),
                        transaction_hash=log.get('transaction_hash', ''),
                        log_index=log.get('log_index', 0),
                        contract_address=log.get('address', ''),
                        raw_data=log,
                        timestamp=log.get('timestamp', 0)
                    )
                    events.append(event)

        return events

    async def _get_last_processed_block(self, chain_type: ChainType) -> int:
        """Get the last processed block number for a chain.

        Args:
            chain_type: The blockchain type

        Returns:
            int: Last processed block number
        """
        chain_config = self._get_chain_config_for_type(chain_type)

        stored_block = await self._state_manager.get_latest_block(chain_type)
        if stored_block is not None:
            return stored_block

        if chain_config and chain_config.start_block is not None:
            return max(chain_config.start_block-1, 0)

        adapter = self._adapter_registry.get_adapter(chain_type)
        latest = await self._get_latest_block(adapter)

        confirmations = chain_config.confirmation_blocks if chain_config else 0

        return max(latest - confirmations, 0)

    def _get_chain_config_for_type(self, chain_type: ChainType) -> Optional[ChainConfig]:
        """Find the chain config that matches a specific chain type."""
        for config in self.config.chains.values():
            try:
                if ChainType(config.chain_type) == chain_type:
                    return config
            except ValueError:
                continue

    def _build_event_filters(self, chain_type: ChainType) -> Dict[str, List[str]]:
        """Build mapping of contract addresses to event names for a chain."""
        filters: Dict[str, List[str]] = {}

        for callback_info in self._callback_registry.list_callbacks():
            metadata = callback_info.get("metadata") or {}
            if metadata.get("chain_type") != chain_type.value:
                continue

            contract_address = callback_info["contract_address"]
            event_name = callback_info["event_name"]
            if not contract_address or not event_name:
                continue

            filters.setdefault(contract_address, [])
            if event_name not in filters[contract_address]:
                filters[contract_address].append(event_name)

        return filters

    async def get_system_status(self) -> Dict[str, Any]:
        """Get the current system status.

        Returns:
            Dict[str, Any]: System status information
        """
        status = {
            "is_listening": self.is_listening,
            "configured_chains": list(self.config.chains.keys()),
            "enabled_chains": list(self.config.get_enabled_chains().keys()),
            "adapter_status": self._adapter_registry.get_adapter_status(),
            "callback_stats": self._callback_registry.get_stats(),
        }

        if self._event_processor:
            status["processor_stats"] = self._event_processor.get_stats()

        return status

    async def get_latest_block(self, chain_name: str) -> int:
        """Get the latest block number for a specific chain.

        Args:
            chain_name: The name of the blockchain

        Returns:
            int: Latest block number

        Raises:
            ChainListenerError: If chain is not configured
        """
        if chain_name not in self.config.chains:
            raise ChainListenerError(f"Chain '{chain_name}' is not configured")

        chain_config = self.config.chains[chain_name]
        chain_type = ChainType(chain_config.chain_type)
        adapter = self._adapter_registry.get_adapter(chain_type)

        return await self._get_latest_block(adapter)

    @property
    def is_listening(self) -> bool:
        """Check if currently listening based on task state.

        Returns:
            bool: True if any listening tasks are active, False otherwise
        """
        return self._is_listening

    def _normalize_contract_address(self, chain_type: ChainType, address: str) -> str:
        """Normalize callback contract addresses per-chain."""
        if is_evm_chain_type(chain_type):
            from web3 import Web3

            try:
                checksum = Web3.to_checksum_address(address)
                logger.debug(
                    "Converted address %s to checksum format %s",
                    address,
                    checksum,
                )
                return checksum
            except Exception as exc:
                raise ChainListenerError(
                    f"Invalid address format '{address}': {exc}"
                ) from exc

        return address
