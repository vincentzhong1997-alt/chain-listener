"""Registry for managing blockchain adapters.

This module provides a centralized registry for managing different
blockchain adapters and their lifecycle.
"""

import logging
import asyncio
from typing import Dict, List, Callable, Optional, Any
from ..models.events import ChainType
from ..adapters.base import BaseAdapter
from ..exceptions import BlockchainAdapterError

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry for managing blockchain adapters.

    This class provides a singleton pattern for managing blockchain
    adapters across the application. It handles adapter registration,
    retrieval, and lifecycle management.
    """

    _instance: Optional['AdapterRegistry'] = None
    _initialized: bool = False

    def __new__(cls) -> 'AdapterRegistry':
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the adapter registry."""
        if not self._initialized:
            self._adapters: Dict[ChainType, BaseAdapter] = {}
            self._adapter_factories: Dict[ChainType, Callable] = {}
            self._adapter_configs: Dict[ChainType, Dict[str, Any]] = {}
            AdapterRegistry._initialized = True
            logger.info("AdapterRegistry initialized")

    def register_adapter(
        self,
        chain_type: ChainType,
        adapter_factory: Callable,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register an adapter factory for a chain type.

        Args:
            chain_type: The blockchain type
            adapter_factory: Factory function to create the adapter
            config: Configuration dictionary for the adapter

        Raises:
            BlockchainAdapterError: If adapter is already registered
        """
        if chain_type in self._adapter_factories:
            raise BlockchainAdapterError(
                f"Adapter for {chain_type} already registered"
            )

        self._adapter_factories[chain_type] = adapter_factory
        self._adapter_configs[chain_type] = config or {}
        logger.info(f"Registered adapter factory for {chain_type}")

    def get_adapter(self, chain_type: ChainType) -> BaseAdapter:
        """Get an adapter instance for the given chain type.

        This method creates the adapter on first use (lazy initialization)
        and returns the cached instance on subsequent calls.

        Args:
            chain_type: The blockchain type

        Returns:
            BaseAdapter: The adapter instance

        Raises:
            BlockchainAdapterError: If adapter is not registered
        """
        if chain_type not in self._adapter_factories:
            raise BlockchainAdapterError(
                f"No adapter registered for {chain_type}"
            )

        # Lazy initialization: create adapter if not exists
        if chain_type not in self._adapters:
            try:
                factory = self._adapter_factories[chain_type]
                config = self._adapter_configs[chain_type]
                adapter = factory(config)
                self._adapters[chain_type] = adapter
                logger.info(f"Created adapter instance for {chain_type}")
            except Exception as e:
                logger.error(f"Failed to create adapter for {chain_type}: {e}")
                raise BlockchainAdapterError(
                    f"Failed to create adapter for {chain_type}: {e}"
                )

        return self._adapters[chain_type]

    def list_supported_chains(self) -> List[ChainType]:
        """Get list of supported chain types.

        Returns:
            List[ChainType]: List of registered chain types
        """
        return list(self._adapter_factories.keys())

    def is_chain_supported(self, chain_type: ChainType) -> bool:
        """Check if a chain type is supported.

        Args:
            chain_type: The blockchain type to check

        Returns:
            bool: True if chain is supported, False otherwise
        """
        return chain_type in self._adapter_factories

    def remove_adapter(self, chain_type: ChainType) -> None:
        """Remove an adapter from the registry.

        This will disconnect the adapter if it's connected and remove
        both the factory and any created instance.

        Args:
            chain_type: The blockchain type to remove
        """
        # Disconnect and remove instance if exists
        if chain_type in self._adapters:
            adapter = self._adapters[chain_type]
            try:
                if hasattr(adapter, 'is_connected') and adapter.is_connected():
                    import asyncio
                    if asyncio.iscoroutinefunction(adapter.disconnect):
                        # If disconnect is async, we can't wait here in sync context
                        # Log warning and continue
                        logger.warning(
                            f"Adapter for {chain_type} is connected. "
                            "Please call disconnect() manually before removing."
                        )
                    else:
                        adapter.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting adapter for {chain_type}: {e}")

            del self._adapters[chain_type]

        # Remove factory and config
        if chain_type in self._adapter_factories:
            del self._adapter_factories[chain_type]
        if chain_type in self._adapter_configs:
            del self._adapter_configs[chain_type]

        logger.info(f"Removed adapter for {chain_type}")

    async def connect_all(self) -> None:
        """Connect all registered adapters.

        For HTTP RPC adapters, connection is optional as they use stateless requests.
        Only adapters with explicit connect() methods will be connected.

        Raises:
            BlockchainAdapterError: If any adapter fails to connect
        """
        errors = {}

        for chain_type in self._adapter_factories.keys():
            try:
                adapter = self.get_adapter(chain_type)
                if hasattr(adapter, 'connect'):
                    if asyncio.iscoroutinefunction(adapter.connect):
                        await adapter.connect()
                    else:
                        adapter.connect()
                    logger.info(f"Connected adapter for {chain_type}")
                else:
                    # Adapter doesn't require explicit connection (e.g., HTTP RPC)
                    logger.info(f"Adapter for {chain_type} doesn't require explicit connection")
            except Exception as e:
                errors[chain_type] = str(e)
                logger.error(f"Failed to connect adapter for {chain_type}: {e}")

        if errors:
            raise BlockchainAdapterError(
                f"Failed to connect some adapters: {errors}"
            )

    async def disconnect_all(self) -> None:
        """Disconnect all adapters."""
        for chain_type, adapter in self._adapters.items():
            try:
                if hasattr(adapter, 'is_connected') and adapter.is_connected():
                    if hasattr(adapter, 'disconnect'):
                        if asyncio.iscoroutinefunction(adapter.disconnect):
                            await adapter.disconnect()
                        else:
                            adapter.disconnect()
                    logger.info(f"Disconnected adapter for {chain_type}")
            except Exception as e:
                logger.warning(f"Error disconnecting adapter for {chain_type}: {e}")

    def get_adapter_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all adapters.

        Returns:
            Dict mapping chain types to their status information
        """
        status = {}

        for chain_type in self._adapter_factories.keys():
            chain_status = {
                "registered": True,
                "initialized": chain_type in self._adapters,
                "connected": False
            }

            if chain_type in self._adapters:
                adapter = self._adapters[chain_type]
                if hasattr(adapter, 'is_connected'):
                    try:
                        chain_status["connected"] = adapter.is_connected()
                    except Exception as e:
                        chain_status["connection_error"] = str(e)

                # Add adapter-specific status if available
                if hasattr(adapter, 'get_status'):
                    try:
                        if asyncio.iscoroutinefunction(adapter.get_status):
                            # Skip async status in sync context
                            chain_status["status_available"] = True
                        else:
                            chain_status.update(adapter.get_status())
                    except Exception as e:
                        chain_status["status_error"] = str(e)

            status[str(chain_type)] = chain_status

        return status

    def clear(self) -> None:
        """Clear all adapters from the registry.

        This is primarily used for testing and reinitialization.
        """
        # Disconnect all adapters first
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, schedule disconnect
                asyncio.create_task(self.disconnect_all())
            else:
                # If no loop, run disconnect_all
                loop.run_until_complete(self.disconnect_all())
        except Exception as e:
            logger.warning(f"Error during disconnect in clear: {e}")

        # Clear all registries
        self._adapters.clear()
        self._adapter_factories.clear()
        self._adapter_configs.clear()

        logger.info("Cleared all adapters from registry")


# Global instance for easy access
adapter_registry = AdapterRegistry()