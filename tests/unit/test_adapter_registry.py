"""Tests for AdapterRegistry following TDD principles."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from chain_listener.core.adapter_registry import AdapterRegistry
from chain_listener.models.events import ChainType
from chain_listener.adapters.base import BaseAdapter
from chain_listener.exceptions import BlockchainAdapterError


class MockAdapter(BaseAdapter):
    """Mock adapter for testing purposes."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._connected = False
        self._status = {"mock": "adapter"}

    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def get_status(self) -> Dict[str, Any]:
        return self._status.copy()

    def get_latest_block_number(self) -> int:
        return 12345

    def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
        return {"hash": f"0x{block_number:x}", "number": block_number}

    def get_logs(self, from_block: int, to_block: int, addresses: List[str]) -> List[Dict[str, Any]]:
        return []

    def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        return {"hash": tx_hash}


class MockAsyncAdapter(BaseAdapter):
    """Mock async adapter for testing purposes."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        await asyncio.sleep(0.01)  # Simulate async operation
        self._connected = True

    async def disconnect(self) -> None:
        await asyncio.sleep(0.01)  # Simulate async operation
        self._connected = False

    async def get_latest_block_number(self) -> int:
        await asyncio.sleep(0.01)  # Simulate async operation
        return 12345

    async def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
        await asyncio.sleep(0.01)  # Simulate async operation
        return {"hash": f"0x{block_number:x}", "number": block_number}

    async def get_logs(self, from_block: int, to_block: int, addresses: List[str]) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.01)  # Simulate async operation
        return []

    async def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        await asyncio.sleep(0.01)  # Simulate async operation
        return {"hash": tx_hash}


@pytest.fixture
def mock_adapter_factory():
    """Factory function for creating mock adapters."""
    def factory(config: Dict[str, Any] = None):
        return MockAdapter(config)
    return factory


@pytest.fixture
def mock_async_adapter_factory():
    """Factory function for creating mock async adapters."""
    def factory(config: Dict[str, Any] = None):
        return MockAsyncAdapter(config)
    return factory


@pytest.fixture
def registry():
    """Create a fresh registry instance for each test."""
    # Clear the singleton instance
    AdapterRegistry._instance = None
    AdapterRegistry._initialized = False
    return AdapterRegistry()


class TestAdapterRegistry:
    """Test cases for AdapterRegistry class."""

    def test_singleton_pattern(self, registry):
        """Test that AdapterRegistry follows singleton pattern."""
        # Create another instance
        registry2 = AdapterRegistry()

        # Should be the same instance
        assert registry is registry2
        assert id(registry) == id(registry2)

    def test_initialization(self, registry):
        """Test registry initialization."""
        assert registry._adapters == {}
        assert registry._adapter_factories == {}
        assert registry._adapter_configs == {}
        assert AdapterRegistry._initialized is True

    def test_register_adapter_success(self, registry, mock_adapter_factory):
        """Test successful adapter registration."""
        config = {"test": "config"}

        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory, config)

        assert ChainType.ETHEREUM in registry._adapter_factories
        assert registry._adapter_factories[ChainType.ETHEREUM] == mock_adapter_factory
        assert registry._adapter_configs[ChainType.ETHEREUM] == config

    def test_register_adapter_duplicate(self, registry, mock_adapter_factory):
        """Test registering duplicate adapter raises error."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        with pytest.raises(BlockchainAdapterError, match="already registered"):
            registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

    def test_register_adapter_without_config(self, registry, mock_adapter_factory):
        """Test registering adapter without config."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        assert registry._adapter_configs[ChainType.ETHEREUM] == {}

    def test_get_adapter_unregistered(self, registry):
        """Test getting unregistered adapter raises error."""
        with pytest.raises(BlockchainAdapterError, match="No adapter registered"):
            registry.get_adapter(ChainType.ETHEREUM)

    def test_get_adapter_success(self, registry, mock_adapter_factory):
        """Test successful adapter retrieval."""
        config = {"test": "config"}
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory, config)

        adapter = registry.get_adapter(ChainType.ETHEREUM)

        assert isinstance(adapter, MockAdapter)
        assert adapter.config == config
        assert ChainType.ETHEREUM in registry._adapters

    def test_get_adapter_lazy_initialization(self, registry, mock_adapter_factory):
        """Test that adapter is created on first access (lazy initialization)."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        # Adapter should not exist initially
        assert ChainType.ETHEREUM not in registry._adapters

        # Get adapter should create it
        adapter = registry.get_adapter(ChainType.ETHEREUM)

        # Adapter should now exist
        assert ChainType.ETHEREUM in registry._adapters
        assert registry._adapters[ChainType.ETHEREUM] is adapter

    def test_get_adapter_cached_instance(self, registry, mock_adapter_factory):
        """Test that same adapter instance is returned on subsequent calls."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        adapter1 = registry.get_adapter(ChainType.ETHEREUM)
        adapter2 = registry.get_adapter(ChainType.ETHEREUM)

        assert adapter1 is adapter2

    def test_get_adapter_factory_error(self, registry):
        """Test handling of factory function errors."""
        def failing_factory(config):
            raise ValueError("Factory failed")

        registry.register_adapter(ChainType.ETHEREUM, failing_factory)

        with pytest.raises(BlockchainAdapterError, match="Failed to create adapter"):
            registry.get_adapter(ChainType.ETHEREUM)

    def test_list_supported_chains(self, registry, mock_adapter_factory):
        """Test listing supported chains."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        supported = registry.list_supported_chains()

        assert ChainType.ETHEREUM in supported

    def test_is_chain_supported(self, registry, mock_adapter_factory):
        """Test checking if chain is supported."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        assert registry.is_chain_supported(ChainType.ETHEREUM) is True

    def test_remove_adapter_unregistered(self, registry):
        """Test removing unregistered adapter."""
        # Should not raise error
        registry.remove_adapter(ChainType.ETHEREUM)

    def test_remove_adapter_with_instance(self, registry, mock_adapter_factory):
        """Test removing adapter with created instance."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        # Create adapter instance
        adapter = registry.get_adapter(ChainType.ETHEREUM)
        adapter._connected = True

        # Remove adapter
        registry.remove_adapter(ChainType.ETHEREUM)

        # Should be removed from all registries
        assert ChainType.ETHEREUM not in registry._adapters
        assert ChainType.ETHEREUM not in registry._adapter_factories
        assert ChainType.ETHEREUM not in registry._adapter_configs

    def test_remove_adapter_connected_sync(self, registry, mock_adapter_factory):
        """Test removing connected adapter with sync disconnect."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        adapter = registry.get_adapter(ChainType.ETHEREUM)
        adapter.connect()  # Connect the adapter

        # Remove should disconnect
        with patch.object(adapter, 'disconnect') as mock_disconnect:
            registry.remove_adapter(ChainType.ETHEREUM)
            mock_disconnect.assert_called_once()

    def test_remove_adapter_connected_async(self, registry, mock_async_adapter_factory):
        """Test removing connected adapter with async disconnect."""
        registry.register_adapter(ChainType.ETHEREUM, mock_async_adapter_factory)

        adapter = registry.get_adapter(ChainType.ETHEREUM)

        # Connect the adapter first
        import asyncio
        asyncio.run(adapter.connect())

        # Remove should log warning for async disconnect
        with patch('chain_listener.core.adapter_registry.logger') as mock_logger:
            registry.remove_adapter(ChainType.ETHEREUM)
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_connect_all_success(self, registry, mock_adapter_factory):
        """Test connecting all adapters successfully."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        await registry.connect_all()

        eth_adapter = registry.get_adapter(ChainType.ETHEREUM)

        assert eth_adapter.is_connected() is True

    @pytest.mark.asyncio
    async def test_connect_all_with_async_adapters(self, registry, mock_async_adapter_factory):
        """Test connecting all async adapters."""
        registry.register_adapter(ChainType.ETHEREUM, mock_async_adapter_factory)

        await registry.connect_all()

        eth_adapter = registry.get_adapter(ChainType.ETHEREUM)

        assert eth_adapter.is_connected() is True

    @pytest.mark.asyncio
    async def test_connect_all_partial_failure(self, registry):
        """Test connecting all adapters with some failures."""
        def failing_factory(config):
            adapter = MockAdapter(config)
            adapter.connect = Mock(side_effect=ConnectionError("Connection failed"))
            return adapter

        registry.register_adapter(ChainType.ETHEREUM, failing_factory)

        with pytest.raises(BlockchainAdapterError, match="Failed to connect some adapters"):
            await registry.connect_all()

    @pytest.mark.asyncio
    async def test_disconnect_all(self, registry, mock_adapter_factory):
        """Test disconnecting all adapters."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        # Connect adapters first
        await registry.connect_all()

        # Disconnect all
        await registry.disconnect_all()

        eth_adapter = registry.get_adapter(ChainType.ETHEREUM)

        assert eth_adapter.is_connected() is False

    @pytest.mark.asyncio
    async def test_disconnect_all_async_adapters(self, registry, mock_async_adapter_factory):
        """Test disconnecting all async adapters."""
        registry.register_adapter(ChainType.ETHEREUM, mock_async_adapter_factory)

        # Connect first
        await registry.connect_all()

        # Disconnect
        await registry.disconnect_all()

        adapter = registry.get_adapter(ChainType.ETHEREUM)
        assert adapter.is_connected() is False

    def test_get_adapter_status(self, registry, mock_adapter_factory):
        """Test getting adapter status."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        # Status before adapter creation
        status = registry.get_adapter_status()

        eth_status = status[str(ChainType.ETHEREUM)]
        assert eth_status["registered"] is True
        assert eth_status["initialized"] is False
        assert eth_status["connected"] is False

        # Create adapter
        adapter = registry.get_adapter(ChainType.ETHEREUM)

        # Status after adapter creation
        status = registry.get_adapter_status()
        eth_status = status[str(ChainType.ETHEREUM)]
        assert eth_status["initialized"] is True
        assert eth_status["connected"] is False

    def test_get_adapter_status_with_connected_adapter(self, registry, mock_adapter_factory):
        """Test getting status of connected adapter."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        adapter = registry.get_adapter(ChainType.ETHEREUM)
        adapter.connect()

        status = registry.get_adapter_status()
        eth_status = status[str(ChainType.ETHEREUM)]

        assert eth_status["connected"] is True

    def test_get_adapter_status_with_custom_status(self, registry, mock_adapter_factory):
        """Test getting status with adapter-specific status."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        # Initialize adapter to get custom status
        registry.get_adapter(ChainType.ETHEREUM)

        status = registry.get_adapter_status()
        eth_status = status[str(ChainType.ETHEREUM)]

        assert "mock" in eth_status

    def test_get_adapter_status_connection_error(self, registry, mock_adapter_factory):
        """Test handling adapter connection status errors."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        adapter = registry.get_adapter(ChainType.ETHEREUM)
        adapter.is_connected = Mock(side_effect=Exception("Status check failed"))

        status = registry.get_adapter_status()
        eth_status = status[str(ChainType.ETHEREUM)]

        assert "connection_error" in eth_status

    def test_get_adapter_status_async_status_method(self, registry, mock_async_adapter_factory):
        """Test handling async get_status method."""
        registry.register_adapter(ChainType.ETHEREUM, mock_async_adapter_factory)

        # Add async get_status method
        adapter = registry.get_adapter(ChainType.ETHEREUM)
        adapter.get_status = AsyncMock(return_value={"async": "status"})

        status = registry.get_adapter_status()
        eth_status = status[str(ChainType.ETHEREUM)]

        assert eth_status["status_available"] is True

    def test_clear(self, registry, mock_adapter_factory):
        """Test clearing all adapters."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        # Create some adapters
        registry.get_adapter(ChainType.ETHEREUM)

        # Clear registry
        registry.clear()

        # All should be cleared
        assert len(registry._adapters) == 0
        assert len(registry._adapter_factories) == 0
        assert len(registry._adapter_configs) == 0

    @patch('chain_listener.core.adapter_registry.asyncio')
    def test_clear_with_event_loop(self, mock_asyncio, registry, mock_adapter_factory):
        """Test clearing with running event loop."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        # Mock event loop and create_task
        mock_loop = Mock()
        mock_loop.is_running.return_value = True
        mock_asyncio.get_event_loop.return_value = mock_loop

        registry.clear()

        mock_loop.is_running.assert_called_once()
        mock_asyncio.create_task.assert_called_once()
        # Check that a coroutine object was passed to create_task
        call_args = mock_asyncio.create_task.call_args[0][0]
        import inspect
        assert inspect.iscoroutine(call_args)

    @patch('chain_listener.core.adapter_registry.asyncio')
    def test_clear_without_event_loop(self, mock_asyncio, registry, mock_adapter_factory):
        """Test clearing without running event loop."""
        registry.register_adapter(ChainType.ETHEREUM, mock_adapter_factory)

        # Mock event loop not running
        mock_loop = Mock()
        mock_loop.is_running.return_value = False
        mock_asyncio.get_event_loop.return_value = mock_loop

        registry.clear()

        mock_loop.is_running.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()


class TestGlobalRegistryInstance:
    """Test cases for the global registry instance."""

    def test_global_registry_exists(self):
        """Test that global registry instance exists."""
        from chain_listener.core.adapter_registry import adapter_registry
        assert isinstance(adapter_registry, AdapterRegistry)

    def test_global_registry_is_singleton(self):
        """Test that global registry follows singleton pattern."""
        from chain_listener.core.adapter_registry import adapter_registry

        # Create new instance
        new_registry = AdapterRegistry()

        # Should be the same instance
        assert adapter_registry is new_registry