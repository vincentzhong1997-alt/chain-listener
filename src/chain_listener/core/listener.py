"""Main ChainListener class providing the unified API.

This module implements the main ChainListener class that serves as the
primary API for the blockchain listener SDK.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

from ..models.config import ChainListenerConfig, ChainConfig
from ..models.events import ChainType, RawEvent
from ..exceptions import ChainListenerError, BlockchainAdapterError
from .adapter_registry import AdapterRegistry, adapter_registry
from .callback_registry import CallbackRegistry
from .event_processor import EventProcessor

logger = logging.getLogger(__name__)


class ChainListener:
    """Main blockchain listener providing a unified API.

    This class serves as the primary interface for the blockchain listener SDK.
    It manages configuration, adapter registration, event listening, and callback
    execution through a simple, user-friendly API.
    """

    def __init__(self, config: ChainListenerConfig) -> None:
        """Initialize the chain listener.

        Args:
            config: Configuration for the chain listener

        Raises:
            ChainListenerError: If configuration is invalid
        """
        self.config = config
        self._adapter_registry = adapter_registry
        self._callback_registry = CallbackRegistry()
        self._event_processor: Optional[EventProcessor] = None
        self._listening_tasks: Dict[ChainType, asyncio.Task] = {}

        # Validate configuration
        self._validate_config()

        # Initialize adapters
        self._initialize_adapters()

        # Initialize event processor
        self._event_processor = EventProcessor(
            config=self.config,
            callback_registry=self._callback_registry
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
                        self._get_adapter_factory(chain_type),
                        adapter_config
                    )
                    logger.info(f"Initialized adapter for {chain_name} ({chain_type})")
                except ValueError as e:
                    raise ChainListenerError(f"Invalid chain type for {chain_name}: {e}")
                except Exception as e:
                    raise ChainListenerError(f"Failed to initialize adapter for {chain_name}: {e}")

        except Exception as e:
            raise ChainListenerError(f"Failed to initialize adapters: {e}")

    def _get_adapter_factory(self, chain_type: ChainType) -> Callable:
        """Get the adapter factory for a chain type.

        Args:
            chain_type: The blockchain type

        Returns:
            Callable: Adapter factory function

        Raises:
            ChainListenerError: If chain type is not supported
        """
        # Factories are registered during initialization
        # This method returns the appropriate factory based on chain type
        if chain_type == ChainType.ETHEREUM:
            from ..adapters.ethereum import EthereumAdapter
            return lambda config: EthereumAdapter(config)
        # Note: BSC support removed until BSC adapter is fully implemented
        # elif chain_type == ChainType.BSC:
        #     from ..adapters.bsc import BSCAdapter
        #     return lambda config: BSCAdapter(config)
        else:
            raise ChainListenerError(f"Unsupported chain type: {chain_type}")

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
        # Extract user-provided adapter config overrides
        user_overrides = chain_config.adapter_config or {}

        # Use the new standardized RPC configuration
        # URL ordering determines priority (convention over configuration)
        adapter_config = {
            "name": f"{chain_config.chain_type}_adapter",
            "network": "mainnet",
            "rpc": {
                "urls": chain_config.rpc.urls,
                "timeout": chain_config.rpc.timeout,
                "retries": chain_config.rpc.retries,
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

        # Apply user overrides (deep merge for nested dictionaries)
        for key, value in user_overrides.items():
            if key == "rpc" and isinstance(value, dict) and isinstance(adapter_config.get("rpc"), dict):
                # Deep merge for rpc config
                adapter_config["rpc"].update(value)
            else:
                # Direct replacement for other fields
                adapter_config[key] = value

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

        # Convert address to checksum format for internal consistency
        from web3 import Web3
        try:
            checksum_address = Web3.to_checksum_address(contract_address)
            logger.debug(f"Converted address {contract_address} to checksum format {checksum_address}")
        except Exception as e:
            raise ChainListenerError(f"Invalid address format '{contract_address}': {e}")

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
        if self.is_listening:
            raise ChainListenerError("Already listening for events")

        try:
            # Connect all adapters
            await self._adapter_registry.connect_all()

            # Start listening tasks for each chain
            for chain_name, chain_config in self.config.get_enabled_chains().items():
                if chain_config.enabled:
                    chain_type = ChainType(chain_config.chain_type)
                    task = asyncio.create_task(
                        self._listen_to_chain(chain_name, chain_type, chain_config)
                    )
                    self._listening_tasks[chain_type] = task
                    logger.info(f"Started listening to {chain_name}")

            # State is managed through task lifecycle
            logger.info("ChainListener started successfully")

        except Exception as e:
            # Cleanup on failure
            await self._cleanup_listening_tasks()
            raise ChainListenerError(f"Failed to start listening: {e}")

    async def stop_listening(self) -> None:
        """Stop listening for blockchain events.

        This method stops all listening tasks and disconnects from blockchains.
        """
        if not self.is_listening:
            logger.warning("Not currently listening")
            return

        try:
            # Cancel all listening tasks
            await self._cleanup_listening_tasks()

            # Disconnect all adapters
            await self._adapter_registry.disconnect_all()

            # Tasks will be marked as done when cancelled, no need to set flag
            logger.info("ChainListener stopped successfully")

        except Exception as e:
            logger.error(f"Error during stop: {e}")
            # Don't raise exception during cleanup

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

            # Get last processed block (simplified - in production, use persistent storage)
            last_block = await self._get_last_processed_block(chain_type)

            while self.is_listening:
                try:
                    # Get latest block
                    latest_block = await self._get_latest_block(adapter)

                    if latest_block > last_block:
                        # Get events from last_block+1 to latest_block
                        events = await self._get_events_from_chain(
                            adapter, last_block + 1, latest_block
                        )

                        if events:
                            # Process events
                            results = await self._event_processor.process_events(events)

                            # Log processing results
                            success_count = sum(1 for r in results if r.success)
                            if success_count > 0:
                                logger.info(
                                    f"Processed {success_count} events from {chain_name}"
                                )

                        last_block = latest_block

                    # Wait before next poll
                    await asyncio.sleep(chain_config.polling_interval / 1000.0)

                except Exception as e:
                    logger.error(f"Error listening to {chain_name}: {e}")
                    await asyncio.sleep(5)  # Wait before retry

        except asyncio.CancelledError:
            logger.info(f"Stopped listening to {chain_name}")
        except Exception as e:
            logger.error(f"Fatal error listening to {chain_name}: {e}")

    async def _get_latest_block(self, adapter) -> int:
        """Get the latest block number from an adapter.

        Args:
            adapter: The blockchain adapter

        Returns:
            int: Latest block number
        """
        if hasattr(adapter, 'get_latest_block_number'):
            if asyncio.iscoroutinefunction(adapter.get_latest_block_number):
                return await adapter.get_latest_block_number()
            else:
                return adapter.get_latest_block_number()
        else:
            raise ChainListenerError("Adapter does not support getting latest block")

    async def _get_events_from_chain(
        self,
        adapter,
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

        # Get contracts to watch from callbacks
        contract_addresses = set()
        for callback_info in self._callback_registry.list_callbacks():
            contract_addresses.add(callback_info["contract_address"])

        if contract_addresses:
            # Get logs for watched contracts
            if hasattr(adapter, 'get_logs'):
                # Determine address parameter format
                if len(contract_addresses) == 0:
                    address_param = None
                elif len(contract_addresses) == 1:
                    address_param = contract_addresses.pop()
                else:
                    address_param = list(contract_addresses)

                # Get logs with proper address format
                if asyncio.iscoroutinefunction(adapter.get_logs):
                    logs = await adapter.get_logs(
                        from_block=from_block,
                        to_block=to_block,
                        address=address_param
                    )
                else:
                    logs = adapter.get_logs(
                        from_block=from_block,
                        to_block=to_block,
                        address=address_param
                    )

                # Convert logs to RawEvent objects
                for log in logs:
                    # This is simplified - in production, convert adapter-specific logs to RawEvent
                    event = RawEvent(
                        chain_type=adapter.chain_type if hasattr(adapter, 'chain_type') else ChainType.ETHEREUM,
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

        This is a simplified implementation. In production, this would
        use persistent storage (Redis, database, etc.).

        Args:
            chain_type: The blockchain type

        Returns:
            int: Last processed block number
        """
        # Simplified: start from latest block
        adapter = self._adapter_registry.get_adapter(chain_type)
        latest = await self._get_latest_block(adapter)
        return max(latest - 10, 0)  # Start from 10 blocks ago for testing

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
        return any(
            task is not None and not task.done()
            for task in self._listening_tasks.values()
        )

    def _add_chain_support(self, chain_name: str, config: ChainConfig) -> None:
        """Add support for a new blockchain (internal method).

        Args:
            chain_name: The name of the blockchain
            config: The chain configuration

        Raises:
            ChainListenerError: If already listening or chain already exists
        """
        if self.is_listening:
            raise ChainListenerError("Cannot add chain while listening")

        if chain_name in self.config.chains:
            raise ChainListenerError(f"Chain '{chain_name}' already exists")

        # Add to configuration
        self.config.chains[chain_name] = config

        # Initialize adapter
        try:
            chain_type = ChainType(config.chain_type)
            adapter_config = self._build_adapter_config(config)
            self._adapter_registry.register_adapter(
                chain_type,
                self._get_adapter_factory(chain_type),
                adapter_config
            )
            logger.info(f"Added support for {chain_name}")
        except Exception as e:
            # Rollback configuration change
            del self.config.chains[chain_name]
            raise ChainListenerError(f"Failed to add chain '{chain_name}': {e}")

    async def __aenter__(self) -> 'ChainListener':
        """Async context manager entry."""
        await self.start_listening()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop_listening()