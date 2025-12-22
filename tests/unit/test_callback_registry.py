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