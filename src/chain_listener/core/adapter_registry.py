"""Registry for managing blockchain adapters.

This module provides a centralized registry for managing different
blockchain adapters and their lifecycle.
"""

import logging
import asyncio
from typing import Dict, List, Callable, Optional, Any, Type
from ..models.events import ChainType
from ..adapters.base import BaseAdapter
from ..adapters.ethereum import EthereumAdapter
from ..adapters.solana import SolanaAdapter
from ..adapters.tron import TronAdapter
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
            self._adapter_classes: Dict[ChainType, Type[BaseAdapter]] = {}
            self._adapter_configs: Dict[ChainType, Dict[str, Any]] = {}
            AdapterRegistry._initialized = True
            logger.info("AdapterRegistry initialized")

    def register_adapter_type(
        self,
        chain_type: ChainType,
        adapter_class: Type[BaseAdapter]
    ) -> None:
        """Register an adapter class for a chain type without instantiation.

        This method only registers the adapter class type without storing
        configuration or creating instances. Use register_adapter_with_config
        to add configuration and enable instance creation.

        Args:
            chain_type: The blockchain type
            adapter_class: BaseAdapter subclass to register

        Raises:
            BlockchainAdapterError: If adapter type is already registered or invalid
        """
        if chain_type in self._adapter_classes:
            raise BlockchainAdapterError(
                f"Adapter type for {chain_type} already registered"
            )

        # Validate that adapter_class is a subclass of BaseAdapter
        if not issubclass(adapter_class, BaseAdapter):
            raise BlockchainAdapterError(
                f"Adapter class must be a subclass of BaseAdapter"
            )

        self._adapter_classes[chain_type] = adapter_class
        # Don't store config for type-only registration
        logger.info(f"Registered adapter type {adapter_class.__name__} for {chain_type}")

    def register_adapter(
        self,
        chain_type: ChainType,
        config: Optional[Dict[str, Any]] = None
    ) -> BaseAdapter:
        """Register and create an adapter instance for a chain type.

        Args:
            chain_type: The blockchain type (must be registered first)
            config: Configuration dictionary for the adapter

        Returns:
            BaseAdapter: The created adapter instance

        Raises:
            BlockchainAdapterError: If adapter type is not registered or instance already exists
        """
        if chain_type in self._adapters:
            return self._adapters[chain_type]

        if chain_type not in self._adapter_classes:
            raise BlockchainAdapterError(
                f"Adapter type for {chain_type} not registered. Use register_adapter_type first."
            ) 

        # Create instance immediately (no lazy loading)
        try:
            adapter_class = self._adapter_classes[chain_type]
            adapter = adapter_class(config or {})
            self._adapters[chain_type] = adapter
            self._adapter_configs[chain_type] = config or {}
            logger.info(f"Created and registered adapter instance {adapter_class.__name__} for {chain_type}")
            return adapter
        except Exception as e:
            logger.error(f"Failed to create adapter for {chain_type}: {e}")
            raise BlockchainAdapterError(
                f"Failed to create adapter for {chain_type}: {e}"
            )

    def get_adapter(self, chain_type: ChainType) -> BaseAdapter:
        """Get an adapter instance for the given chain type.

        This method returns a previously created instance.
        Use register_adapter() to create instances first.

        Args:
            chain_type: The blockchain type

        Returns:
            BaseAdapter: The adapter instance

        Raises:
            BlockchainAdapterError: If adapter instance is not registered
        """
        if chain_type not in self._adapters:
            raise BlockchainAdapterError(
                f"No adapter instance registered for {chain_type}. "
                f"Use register_adapter() to create an instance first."
            )

        return self._adapters[chain_type]

    def get_adapter_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all adapters.

        Returns:
            Dict mapping chain types to their status information
        """
        status = {}

        for chain_type in self._adapter_classes.keys():
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


# Global instance for easy access
adapter_registry = AdapterRegistry()

# Register built-in adapters so they are available out of the box.
adapter_registry.register_adapter_type(ChainType.ETHEREUM, EthereumAdapter)
adapter_registry.register_adapter_type(ChainType.SOLANA, SolanaAdapter)
adapter_registry.register_adapter_type(ChainType.TRON, TronAdapter)
