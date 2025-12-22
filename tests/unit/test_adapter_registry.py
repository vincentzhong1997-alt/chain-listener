"""Tests for AdapterRegistry following TDD principles."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List, Optional

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

    def decode_event(self, event):
        """Pass-through decode helper for tests."""
        return event


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

    async def get_logs(
        self,
        address: Optional = None,
        topics: Optional = None,
        from_block: Optional = None,
        to_block: Optional = None
    ) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.01)  # Simulate async operation
        return []

    async def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        await asyncio.sleep(0.01)  # Simulate async operation
        return {"hash": tx_hash}

    def decode_event(self, event):
        """Pass-through decode helper for tests."""
        return event




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
        assert registry._adapter_classes == {}
        assert registry._adapter_configs == {}
        assert AdapterRegistry._initialized is True

    def test_register_adapter_success(self, registry):
        """Test successful adapter registration."""
        config = {"test": "config"}

        # First register the adapter type
        registry.register_adapter_type(ChainType.ETHEREUM, MockAdapter)
        # Then register an instance with config
        adapter = registry.register_adapter(ChainType.ETHEREUM, config)

        assert ChainType.ETHEREUM in registry._adapter_classes
        assert registry._adapter_classes[ChainType.ETHEREUM] == MockAdapter
        assert registry._adapter_configs[ChainType.ETHEREUM] == config
        assert isinstance(adapter, MockAdapter)
        assert adapter.config == config

    def test_register_adapter_duplicate(self, registry):
        """Test registering duplicate adapter raises error."""
        registry.register_adapter_type(ChainType.ETHEREUM, MockAdapter)

        with pytest.raises(BlockchainAdapterError, match="already registered"):
            registry.register_adapter_type(ChainType.ETHEREUM, MockAdapter)

    def test_register_adapter_without_config(self, registry):
        """Test registering adapter without config."""
        registry.register_adapter_type(ChainType.ETHEREUM, MockAdapter)
        adapter = registry.register_adapter(ChainType.ETHEREUM)

        assert registry._adapter_configs[ChainType.ETHEREUM] == {}
        assert isinstance(adapter, MockAdapter)

    def test_get_adapter_unregistered(self, registry):
        """Test getting unregistered adapter raises error."""
        with pytest.raises(BlockchainAdapterError, match="No adapter registered"):
            registry.get_adapter(ChainType.ETHEREUM)

    def test_get_adapter_success(self, registry):
        """Test successful adapter retrieval."""
        config = {"test": "config"}
        registry.register_adapter_type(ChainType.ETHEREUM, MockAdapter)
        registry.register_adapter(ChainType.ETHEREUM, config)

        adapter = registry.get_adapter(ChainType.ETHEREUM)

        assert isinstance(adapter, MockAdapter)
        assert adapter.config == config
        assert ChainType.ETHEREUM in registry._adapters

    def test_get_adapter_lazy_initialization(self, registry):
        """Test that adapter is created on first access (lazy initialization)."""
        registry.register_adapter_type(ChainType.ETHEREUM, MockAdapter)

        # Adapter should not exist initially
        assert ChainType.ETHEREUM not in registry._adapters

        # Get adapter should create it
        adapter = registry.get_adapter(ChainType.ETHEREUM)

        # Adapter should now exist
        assert ChainType.ETHEREUM in registry._adapters
        assert registry._adapters[ChainType.ETHEREUM] is adapter

    def test_get_adapter_cached_instance(self, registry):
        """Test that same adapter instance is returned on subsequent calls."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

        adapter1 = registry.get_adapter(ChainType.ETHEREUM)
        adapter2 = registry.get_adapter(ChainType.ETHEREUM)

        assert adapter1 is adapter2

    def test_get_adapter_factory_error(self, registry):
        """Test handling of adapter class errors."""
        class FailingAdapter(BaseAdapter):
            def __init__(self, config):
                raise ValueError("Adapter creation failed")

            def is_connected(self) -> bool:
                return False

            async def connect(self) -> None:
                pass

            async def disconnect(self) -> None:
                pass

            async def get_latest_block_number(self) -> int:
                return 0

            async def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
                return {}

            async def get_logs(
        self,
        address: Optional = None,
        topics: Optional = None,
        from_block: Optional = None,
        to_block: Optional = None
    ) -> List[Dict[str, Any]]:
                return []

            async def get_transaction(self, transaction_hash: str) -> Dict[str, Any]:
                return {}

            def decode_event(self, event):
                return event

        registry.register_adapter(ChainType.ETHEREUM, FailingAdapter)

        with pytest.raises(BlockchainAdapterError, match="Failed to create adapter"):
            registry.get_adapter(ChainType.ETHEREUM)

    def test_list_supported_chains(self, registry):
        """Test listing supported chains."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

        supported = registry.list_supported_chains()

        assert ChainType.ETHEREUM in supported

    def test_is_chain_supported(self, registry):
        """Test checking if chain is supported."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

        assert registry.is_chain_supported(ChainType.ETHEREUM) is True

    @pytest.mark.asyncio
    async def test_connect_all_success(self, registry):
        """Test connecting all adapters successfully."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

        await registry.connect_all()

        eth_adapter = registry.get_adapter(ChainType.ETHEREUM)

        assert eth_adapter.is_connected() is True

    @pytest.mark.asyncio
    async def test_connect_all_with_async_adapters(self, registry):
        """Test connecting all async adapters."""
        registry.register_adapter(ChainType.ETHEREUM, MockAsyncAdapter)

        await registry.connect_all()

        eth_adapter = registry.get_adapter(ChainType.ETHEREUM)

        assert eth_adapter.is_connected() is True

    @pytest.mark.asyncio
    async def test_connect_all_partial_failure(self, registry):
        """Test connecting all adapters with some failures."""
        class FailingConnectAdapter(BaseAdapter):
            def __init__(self, config):
                self.config = config or {}
                self._connected = False

            def is_connected(self) -> bool:
                return self._connected

            async def connect(self) -> None:
                raise ConnectionError("Connection failed")

            async def disconnect(self) -> None:
                self._connected = False

            async def get_latest_block_number(self) -> int:
                return 12345

            async def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
                return {"hash": f"0x{block_number:x}", "number": block_number}

            async def get_logs(
        self,
        address: Optional = None,
        topics: Optional = None,
        from_block: Optional = None,
        to_block: Optional = None
    ) -> List[Dict[str, Any]]:
                return []

            async def get_transaction(self, transaction_hash: str) -> Dict[str, Any]:
                return {}

            def decode_event(self, event):
                return event

        registry.register_adapter(ChainType.ETHEREUM, FailingConnectAdapter)

        with pytest.raises(BlockchainAdapterError, match="Failed to connect some adapters"):
            await registry.connect_all()

    @pytest.mark.asyncio
    async def test_disconnect_all(self, registry):
        """Test disconnecting all adapters."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

        # Connect adapters first
        await registry.connect_all()

        # Disconnect all
        await registry.disconnect_all()

        eth_adapter = registry.get_adapter(ChainType.ETHEREUM)

        assert eth_adapter.is_connected() is False

    @pytest.mark.asyncio
    async def test_disconnect_all_async_adapters(self, registry):
        """Test disconnecting all async adapters."""
        registry.register_adapter(ChainType.ETHEREUM, MockAsyncAdapter)

        # Connect first
        await registry.connect_all()

        # Disconnect
        await registry.disconnect_all()

        adapter = registry.get_adapter(ChainType.ETHEREUM)
        assert adapter.is_connected() is False

    def test_get_adapter_status(self, registry):
        """Test getting adapter status."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

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

    def test_get_adapter_status_with_connected_adapter(self, registry):
        """Test getting status of connected adapter."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

        adapter = registry.get_adapter(ChainType.ETHEREUM)
        adapter.connect()

        status = registry.get_adapter_status()
        eth_status = status[str(ChainType.ETHEREUM)]

        assert eth_status["connected"] is True

    def test_get_adapter_status_with_custom_status(self, registry):
        """Test getting status with adapter-specific status."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

        # Initialize adapter to get custom status
        registry.get_adapter(ChainType.ETHEREUM)

        status = registry.get_adapter_status()
        eth_status = status[str(ChainType.ETHEREUM)]

        assert "mock" in eth_status

    def test_get_adapter_status_connection_error(self, registry):
        """Test handling adapter connection status errors."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

        adapter = registry.get_adapter(ChainType.ETHEREUM)
        adapter.is_connected = Mock(side_effect=Exception("Status check failed"))

        status = registry.get_adapter_status()
        eth_status = status[str(ChainType.ETHEREUM)]

        assert "connection_error" in eth_status

    def test_get_adapter_status_async_status_method(self, registry):
        """Test handling async get_status method."""
        registry.register_adapter(ChainType.ETHEREUM, MockAsyncAdapter)

        # Add async get_status method
        adapter = registry.get_adapter(ChainType.ETHEREUM)
        adapter.get_status = AsyncMock(return_value={"async": "status"})

        status = registry.get_adapter_status()
        eth_status = status[str(ChainType.ETHEREUM)]

        assert eth_status["status_available"] is True

    def test_clear(self, registry):
        """Test clearing all adapters."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

        # Create some adapters
        registry.get_adapter(ChainType.ETHEREUM)

        # Clear registry
        registry.clear()

        # All should be cleared
        assert len(registry._adapters) == 0
        assert len(registry._adapter_classes) == 0
        assert len(registry._adapter_configs) == 0

    @patch('chain_listener.core.adapter_registry.asyncio')
    def test_clear_with_event_loop(self, mock_asyncio, registry):
        """Test clearing with running event loop."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

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
    def test_clear_without_event_loop(self, mock_asyncio, registry):
        """Test clearing without running event loop."""
        registry.register_adapter(ChainType.ETHEREUM, MockAdapter)

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
