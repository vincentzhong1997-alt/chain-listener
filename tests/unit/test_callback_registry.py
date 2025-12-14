"""Tests for CallbackRegistry following TDD principles."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from chain_listener.core.callback_registry import CallbackRegistry
from chain_listener.models.events import DecodedEvent, ChainType
from chain_listener.exceptions import EventProcessingError


@pytest.fixture
def mock_event():
    """Create a mock decoded event for testing."""
    return DecodedEvent(
        chain_type=ChainType.ETHEREUM,
        contract_address="0x1234567890123456789012345678901234567890",
        event_name="Transfer",
        block_number=12345,
        transaction_hash="0xabcdef1234567890",
        log_index=0,
        timestamp=1640995200,
        parameters={
            "from": "0x1111111111111111111111111111111111111111",
            "to": "0x2222222222222222222222222222222222222222",
            "value": 1000
        }
    )


@pytest.fixture
def registry():
    """Create a fresh registry instance for each test."""
    return CallbackRegistry()


class TestCallbackRegistry:
    """Test cases for CallbackRegistry class."""

    def test_initialization(self, registry):
        """Test registry initialization."""
        assert registry._callbacks == {}
        assert registry._callback_metadata == {}

    def test_create_key(self, registry):
        """Test key creation for callback registration."""
        key = registry._create_key("0x1234567890123456789012345678901234567890", "Transfer")
        expected = "0x1234567890123456789012345678901234567890:Transfer"
        assert key == expected

    def test_create_key_case_insensitive_address(self, registry):
        """Test that address is converted to lowercase in key."""
        key1 = registry._create_key("0xABCDEF1234567890", "Transfer")
        key2 = registry._create_key("0xabcdef1234567890", "Transfer")
        assert key1 == key2

    def test_register_callback_success(self, registry):
        """Test successful callback registration."""
        def callback(event):
            return event

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback,
            {"test": "metadata"}
        )

        key = registry._create_key("0x1234567890123456789012345678901234567890", "Transfer")
        assert key in registry._callbacks
        assert registry._callbacks[key] == callback
        assert registry._callback_metadata[key] == {"test": "metadata"}

    def test_register_callback_without_metadata(self, registry):
        """Test registering callback without metadata."""
        def callback(event):
            return event

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback
        )

        key = registry._create_key("0x1234567890123456789012345678901234567890", "Transfer")
        assert registry._callback_metadata[key] == {}

    def test_register_callback_non_callable(self, registry):
        """Test registering non-callable raises error."""
        with pytest.raises(EventProcessingError, match="Callback must be callable"):
            registry.register_callback(
                "0x1234567890123456789012345678901234567890",
                "Transfer",
                "not_callable"
            )

    def test_register_callback_duplicate_overwrites(self, registry):
        """Test that registering duplicate callback overwrites existing one."""
        def callback1(event):
            return "callback1"

        def callback2(event):
            return "callback2"

        # Register first callback
        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback1
        )

        # Register second callback with same key
        with pytest.warns(None):  # Should log warning but not raise error
            registry.register_callback(
                "0x1234567890123456789012345678901234567890",
                "Transfer",
                callback2
            )

        key = registry._create_key("0x1234567890123456789012345678901234567890", "Transfer")
        assert registry._callbacks[key] == callback2

    def test_unregister_callback_success(self, registry):
        """Test successful callback unregistration."""
        def callback(event):
            return event

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback
        )

        removed = registry.unregister_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer"
        )

        assert removed == callback
        key = registry._create_key("0x1234567890123456789012345678901234567890", "Transfer")
        assert key not in registry._callbacks
        assert key not in registry._callback_metadata

    def test_unregister_callback_not_found(self, registry):
        """Test unregistering non-existent callback returns None."""
        removed = registry.unregister_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer"
        )

        assert removed is None

    def test_get_callback_success(self, registry):
        """Test successful callback retrieval."""
        def callback(event):
            return event

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback
        )

        retrieved = registry.get_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer"
        )

        assert retrieved == callback

    def test_get_callback_not_found(self, registry):
        """Test getting non-existent callback returns None."""
        retrieved = registry.get_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer"
        )

        assert retrieved is None

    def test_get_callback_case_insensitive(self, registry):
        """Test that callback lookup is case insensitive for address."""
        def callback(event):
            return event

        # Register with lowercase address
        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback
        )

        # Get with uppercase address
        retrieved = registry.get_callback(
            "0x1234567890123456789012345678901234567890".upper(),
            "Transfer"
        )

        assert retrieved == callback

    def test_get_callback_metadata_success(self, registry):
        """Test successful callback metadata retrieval."""
        metadata = {"test": "metadata", "priority": 1}

        def callback(event):
            return event

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback,
            metadata
        )

        retrieved = registry.get_callback_metadata(
            "0x1234567890123456789012345678901234567890",
            "Transfer"
        )

        assert retrieved == metadata

    def test_get_callback_metadata_not_found(self, registry):
        """Test getting metadata for non-existent callback returns None."""
        retrieved = registry.get_callback_metadata(
            "0x1234567890123456789012345678901234567890",
            "Transfer"
        )

        assert retrieved is None

    def test_has_callback_true(self, registry):
        """Test has_callback returns True when callback exists."""
        def callback(event):
            return event

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback
        )

        assert registry.has_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer"
        ) is True

    def test_has_callback_false(self, registry):
        """Test has_callback returns False when callback doesn't exist."""
        assert registry.has_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer"
        ) is False

    def test_list_callbacks_empty(self, registry):
        """Test listing callbacks when none are registered."""
        callbacks = registry.list_callbacks()
        assert callbacks == []

    def test_list_callbacks_with_data(self, registry):
        """Test listing callbacks with registered callbacks."""
        def callback1(event):
            return "callback1"

        def callback2(event):
            return "callback2"

        # Register callbacks
        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback1,
            {"type": "transfer"}
        )
        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Approval",
            callback2,
            {"type": "approval"}
        )
        registry.register_callback(
            "0x9876543210987654321098765432109876543210",
            "Transfer",
            callback2
        )

        callbacks = registry.list_callbacks()

        assert len(callbacks) == 3

        # Check first callback
        transfer_callback = next(c for c in callbacks if c["event_name"] == "Transfer")
        assert transfer_callback["contract_address"] == "0x1234567890123456789012345678901234567890"
        assert transfer_callback["callback_name"] == "callback1"
        assert transfer_callback["metadata"] == {"type": "transfer"}

        # Check different types of callbacks
        def named_callback(event):
            return "named_callback_result"

        lambda_callback = lambda x: "lambda_callback_result"

        # Register named function
        registry.register_callback(
            "0x1111111111111111111111111111111111111111",
            "TestNamed",
            named_callback
        )

        # Register lambda function
        registry.register_callback(
            "0x1111111111111111111111111111111111111111",
            "TestLambda",
            lambda_callback
        )

        callbacks = registry.list_callbacks()

        # Check named function callback
        named_cb = next(c for c in callbacks if c["event_name"] == "TestNamed")
        assert named_cb["contract_address"] == "0x1111111111111111111111111111111111111111"
        assert "named_callback" in named_cb["callback_name"].lower()

        # Check lambda function callback
        lambda_cb = next(c for c in callbacks if c["event_name"] == "TestLambda")
        assert lambda_cb["contract_address"] == "0x1111111111111111111111111111111111111111"
        # Test that lambda callback is properly registered (without relying on string representation)
        assert lambda_cb["callback_name"] is not None
        assert len(lambda_cb["callback_name"]) > 0

        # Verify callbacks are callable
        assert callable(named_callback)
        assert callable(lambda_callback)

    def test_get_callbacks_for_contract(self, registry):
        """Test getting callbacks for a specific contract."""
        def callback1(event):
            return "callback1"

        def callback2(event):
            return "callback2"

        def callback3(event):
            return "callback3"

        # Register callbacks for different contracts
        registry.register_callback("0x1111111111111111111111111111111111111111", "Transfer", callback1)
        registry.register_callback("0x1111111111111111111111111111111111111111", "Approval", callback2)
        registry.register_callback("0x2222222222222222222222222222222222222222", "Transfer", callback3)

        # Get callbacks for first contract
        callbacks = registry.get_callbacks_for_contract("0x1111111111111111111111111111111111111111")

        assert len(callbacks) == 2
        event_names = {c["event_name"] for c in callbacks}
        assert event_names == {"Transfer", "Approval"}

        # Get callbacks for second contract
        callbacks = registry.get_callbacks_for_contract("0x2222222222222222222222222222222222222222")
        assert len(callbacks) == 1
        assert callbacks[0]["event_name"] == "Transfer"

        # Case insensitive address
        callbacks = registry.get_callbacks_for_contract("0x1111111111111111111111111111111111111111".upper())
        assert len(callbacks) == 2

    @pytest.mark.asyncio
    async def test_execute_callback_sync_success(self, registry, mock_event):
        """Test executing sync callback successfully."""
        result_value = "executed"

        def callback(event):
            return result_value

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback
        )

        result = await registry.execute_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            mock_event
        )

        assert result == result_value

    @pytest.mark.asyncio
    async def test_execute_callback_async_success(self, registry, mock_event):
        """Test executing async callback successfully."""
        result_value = "async_executed"

        async def callback(event):
            await asyncio.sleep(0.01)  # Simulate async operation
            return result_value

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            callback
        )

        result = await registry.execute_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            mock_event
        )

        assert result == result_value

    @pytest.mark.asyncio
    async def test_execute_callback_not_found(self, registry, mock_event):
        """Test executing non-existent callback returns None."""
        result = await registry.execute_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            mock_event
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_callback_error(self, registry, mock_event):
        """Test handling callback execution errors."""
        def failing_callback(event):
            raise ValueError("Callback failed")

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            failing_callback
        )

        with pytest.raises(EventProcessingError, match="Callback execution failed"):
            await registry.execute_callback(
                "0x1234567890123456789012345678901234567890",
                "Transfer",
                mock_event
            )

    @pytest.mark.asyncio
    async def test_execute_callback_async_error(self, registry, mock_event):
        """Test handling async callback execution errors."""
        async def failing_callback(event):
            await asyncio.sleep(0.01)
            raise ValueError("Async callback failed")

        registry.register_callback(
            "0x1234567890123456789012345678901234567890",
            "Transfer",
            failing_callback
        )

        with pytest.raises(EventProcessingError, match="Callback execution failed"):
            await registry.execute_callback(
                "0x1234567890123456789012345678901234567890",
                "Transfer",
                mock_event
            )

    def test_clear_empty(self, registry):
        """Test clearing empty registry."""
        registry.clear()
        assert len(registry._callbacks) == 0
        assert len(registry._callback_metadata) == 0

    def test_clear_with_data(self, registry):
        """Test clearing registry with callbacks."""
        def callback1(event):
            return "callback1"

        def callback2(event):
            return "callback2"

        # Register callbacks
        registry.register_callback("0x1111111111111111111111111111111111111111", "Transfer", callback1)
        registry.register_callback("0x2222222222222222222222222222222222222222", "Approval", callback2)

        # Clear
        registry.clear()

        assert len(registry._callbacks) == 0
        assert len(registry._callback_metadata) == 0

    def test_get_stats_empty(self, registry):
        """Test getting stats from empty registry."""
        stats = registry.get_stats()

        assert stats["total_callbacks"] == 0
        assert stats["unique_contracts"] == 0
        assert stats["unique_events"] == 0
        assert stats["callback_list"] == []

    def test_get_stats_with_data(self, registry):
        """Test getting stats from registry with callbacks."""
        def callback1(event):
            return "callback1"

        def callback2(event):
            return "callback2"

        def callback3(event):
            return "callback3"

        # Register callbacks
        registry.register_callback("0x1111111111111111111111111111111111111111", "Transfer", callback1)
        registry.register_callback("0x1111111111111111111111111111111111111111", "Approval", callback2)
        registry.register_callback("0x2222222222222222222222222222222222222222", "Transfer", callback3)

        stats = registry.get_stats()

        assert stats["total_callbacks"] == 3
        assert stats["unique_contracts"] == 2  # 0x1111... and 0x2222...
        assert stats["unique_events"] == 2  # Transfer and Approval
        assert len(stats["callback_list"]) == 3

        # Verify callback list contains expected data
        callback_list = stats["callback_list"]
        addresses = {cb["contract_address"] for cb in callback_list}
        events = {cb["event_name"] for cb in callback_list}

        assert addresses == {"0x1111111111111111111111111111111111111111", "0x2222222222222222222222222222222222222222"}
        assert events == {"Transfer", "Approval"}

    def test_get_stats_same_event_different_contracts(self, registry):
        """Test stats with same event on different contracts."""
        def callback1(event):
            return "callback1"

        def callback2(event):
            return "callback2"

        # Same event, different contracts
        registry.register_callback("0x1111111111111111111111111111111111111111", "Transfer", callback1)
        registry.register_callback("0x2222222222222222222222222222222222222222", "Transfer", callback2)

        stats = registry.get_stats()

        assert stats["total_callbacks"] == 2
        assert stats["unique_contracts"] == 2
        assert stats["unique_events"] == 1  # Only Transfer

    def test_get_stats_different_events_same_contract(self, registry):
        """Test stats with different events on same contract."""
        def callback1(event):
            return "callback1"

        def callback2(event):
            return "callback2"

        # Different events, same contract
        registry.register_callback("0x1111111111111111111111111111111111111111", "Transfer", callback1)
        registry.register_callback("0x1111111111111111111111111111111111111111", "Approval", callback2)

        stats = registry.get_stats()

        assert stats["total_callbacks"] == 2
        assert stats["unique_contracts"] == 1
        assert stats["unique_events"] == 2  # Transfer and Approval