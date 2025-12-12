"""Tests for EventProcessor following TDD principles."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from chain_listener.core.event_processor import EventProcessor, ProcessResult, ReorgInfo
from chain_listener.core.callback_registry import CallbackRegistry
from chain_listener.models.events import RawEvent, DecodedEvent, ChainType
from chain_listener.models.config import ChainListenerConfig, GlobalConfig, ChainConfig
from chain_listener.exceptions import EventProcessingError


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return ChainListenerConfig(
        chains={
            "ethereum": ChainConfig(
                chain_type=ChainType.ETHEREUM,
                chain_id=1,
                confirmation_blocks=12,
                polling_interval=15000,
                rpc_urls=[{"url": "https://eth.llamarpc.com", "priority": 1}]
            )
        },
        global_config=GlobalConfig(
            max_concurrent_processing=5,
            event_batch_size=100,
            log_level="INFO"
        )
    )


@pytest.fixture
def mock_callback_registry():
    """Create a mock callback registry."""
    return Mock(spec=CallbackRegistry)


@pytest.fixture
def mock_raw_event():
    """Create a mock raw event for testing."""
    return RawEvent(
        chain_type=ChainType.ETHEREUM,
        block_number=12345,
        block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        transaction_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        log_index=0,
        contract_address="0x1234567890123456789012345678901234567890",
        raw_data={
            "event_name": "Transfer",
            "parameters": {
                "from": "0x1111111111111111111111111111111111111111",
                "to": "0x2222222222222222222222222222222222222222",
                "value": 1000
            }
        },
        timestamp=1640995200
    )


@pytest.fixture
def processor(mock_config, mock_callback_registry):
    """Create an event processor instance for testing."""
    return EventProcessor(mock_config, mock_callback_registry)


class TestProcessResult:
    """Test cases for ProcessResult dataclass."""

    def test_process_result_creation(self):
        """Test creating ProcessResult with all fields."""
        event = Mock()
        decoded_event = Mock()
        callback_result = "result"

        result = ProcessResult(
            success=True,
            event=event,
            decoded_event=decoded_event,
            callback_result=callback_result
        )

        assert result.success is True
        assert result.event is event
        assert result.decoded_event is decoded_event
        assert result.callback_result == "result"
        assert result.error is None

    def test_process_result_with_error(self):
        """Test creating ProcessResult with error."""
        event = Mock()

        result = ProcessResult(
            success=False,
            event=event,
            error="Processing failed"
        )

        assert result.success is False
        assert result.event is event
        assert result.error == "Processing failed"
        assert result.decoded_event is None
        assert result.callback_result is None


class TestReorgInfo:
    """Test cases for ReorgInfo dataclass."""

    def test_reorg_info_creation(self):
        """Test creating ReorgInfo with all fields."""
        reorg_info = ReorgInfo(
            detected_at=12345,
            old_block_hash="0x1234567890123456789012345678901234567890",
            new_block_hash="0xabcdef1234567890abcdef1234567890abcdef12",
            block_number=12345,
            depth=5
        )

        assert reorg_info.detected_at == 12345
        assert reorg_info.old_block_hash == "0x1234567890123456789012345678901234567890"
        assert reorg_info.new_block_hash == "0xabcdef1234567890abcdef1234567890abcdef12"
        assert reorg_info.block_number == 12345
        assert reorg_info.depth == 5


class TestEventProcessor:
    """Test cases for EventProcessor class."""

    def test_initialization(self, processor, mock_config, mock_callback_registry):
        """Test processor initialization."""
        assert processor.config == mock_config
        assert processor.callback_registry == mock_callback_registry
        assert processor._processed_events == {}
        assert processor._reorg_detection == {}

    def test_compute_event_hash(self, processor, mock_raw_event):
        """Test event hash computation."""
        hash_value = processor._compute_event_hash(mock_raw_event)
        expected = f"{mock_raw_event.transaction_hash}:{mock_raw_event.log_index}"
        assert hash_value == expected

    def test_compute_event_hash_different_log_index(self, processor, mock_raw_event):
        """Test event hash computation with different log index."""
        event1 = mock_raw_event
        event2 = RawEvent(
            chain_type=event1.chain_type,
            contract_address=event1.contract_address,
            block_number=event1.block_number,
            block_hash=event1.block_hash,
            transaction_hash=event1.transaction_hash,
            log_index=1,  # Different log index
            raw_data=event1.raw_data,
            timestamp=event1.timestamp
        )

        hash1 = processor._compute_event_hash(event1)
        hash2 = processor._compute_event_hash(event2)

        assert hash1 != hash2

    def test_is_event_processed(self, processor):
        """Test checking if event is processed."""
        event_hash = "0x1234567890:0"

        # Initially not processed
        assert processor.is_event_processed(event_hash) is False

        # Mark as processed
        processor._processed_events[event_hash] = 1640995200

        # Now should be processed
        assert processor.is_event_processed(event_hash) is True

    def test_get_processed_events_count(self, processor):
        """Test getting processed events count."""
        # Initially empty
        assert processor.get_processed_events_count() == 0

        # Add some events
        processor._processed_events["hash1"] = 1640995200
        processor._processed_events["hash2"] = 1640995201

        assert processor.get_processed_events_count() == 2

    def test_clear_cache(self, processor):
        """Test clearing processor cache."""
        # Add some data
        processor._processed_events["hash1"] = 1640995200
        processor._reorg_detection[ChainType.ETHEREUM] = {12345: "0x123456"}

        # Clear cache
        processor.clear_cache()

        assert processor._processed_events == {}
        assert processor._reorg_detection == {}

    def test_get_stats(self, processor, mock_config):
        """Test getting processor statistics."""
        # Add some data
        processor._processed_events["hash1"] = 1640995200
        processor._reorg_detection[ChainType.ETHEREUM] = {12345: "0x123456", 12346: "0xabcdef"}

        stats = processor.get_stats()

        assert stats["processed_events_cache_size"] == 1
        assert stats["reorg_cache_entries"]["ChainType.ETHEREUM"] == 2
        assert stats["max_concurrent_processing"] == mock_config.global_config.max_concurrent_processing
        assert stats["event_batch_size"] == mock_config.global_config.event_batch_size

    @pytest.mark.asyncio
    async def test_process_events_empty(self, processor):
        """Test processing empty list of events."""
        results = await processor.process_events([])
        assert results == []

    @pytest.mark.asyncio
    async def test_process_single_event_success(self, processor, mock_raw_event):
        """Test successful processing of single event."""
        # Mock dependencies
        mock_decoded_event = DecodedEvent(
            chain_type=mock_raw_event.chain_type,
            contract_address=mock_raw_event.contract_address,
            event_name="Transfer",
            parameters=mock_raw_event.raw_data["parameters"],
            block_number=mock_raw_event.block_number,
            transaction_hash=mock_raw_event.transaction_hash,
            log_index=mock_raw_event.log_index,
            timestamp=mock_raw_event.timestamp
        )

        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            mock_adapter.decode_event.return_value = mock_decoded_event
            mock_registry.get_adapter.return_value = mock_adapter

            processor.callback_registry.execute_callback = AsyncMock(return_value="callback_result")

            results = await processor.process_events([mock_raw_event])

        assert len(results) == 1
        result = results[0]
        assert result.success is True
        assert result.event is mock_raw_event
        assert result.decoded_event is mock_decoded_event
        assert result.callback_result == "callback_result"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_process_single_event_duplicate(self, processor, mock_raw_event):
        """Test processing duplicate event."""
        # Add event to processed cache
        event_hash = processor._compute_event_hash(mock_raw_event)
        processor._processed_events[event_hash] = mock_raw_event.timestamp

        results = await processor.process_events([mock_raw_event])

        assert len(results) == 1
        result = results[0]
        assert result.success is True
        assert result.event is mock_raw_event
        assert result.decoded_event is None
        assert result.callback_result is None

    @pytest.mark.asyncio
    async def test_process_single_event_no_decode_support(self, processor, mock_raw_event):
        """Test processing event when adapter doesn't support decoding."""
        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            # Remove decode_event attribute
            del mock_adapter.decode_event
            mock_registry.get_adapter.return_value = mock_adapter

            processor.callback_registry.execute_callback = AsyncMock(return_value=None)

            results = await processor.process_events([mock_raw_event])

        assert len(results) == 1
        result = results[0]
        assert result.success is True
        assert result.decoded_event.event_name == "Unknown"
        assert result.decoded_event.parameters == {}

    @pytest.mark.asyncio
    async def test_process_single_event_async_decode(self, processor, mock_raw_event):
        """Test processing event with async decode method."""
        mock_decoded_event = Mock()

        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            mock_adapter.decode_event = AsyncMock(return_value=mock_decoded_event)
            mock_registry.get_adapter.return_value = mock_adapter

            processor.callback_registry.execute_callback = AsyncMock(return_value=None)

            results = await processor.process_events([mock_raw_event])

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].decoded_event is mock_decoded_event

    @pytest.mark.asyncio
    async def test_process_single_event_callback_error(self, processor, mock_raw_event):
        """Test processing event when callback execution fails."""
        mock_decoded_event = Mock()
        mock_decoded_event.event_name = "Transfer"

        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            mock_adapter.decode_event.return_value = mock_decoded_event
            mock_registry.get_adapter.return_value = mock_adapter

            processor.callback_registry.execute_callback = AsyncMock(
                side_effect=Exception("Callback failed")
            )

            results = await processor.process_events([mock_raw_event])

        # Should still succeed despite callback error
        assert len(results) == 1
        result = results[0]
        assert result.success is True
        assert result.error is None  # Callback errors don't fail processing

    @pytest.mark.asyncio
    async def test_process_single_event_processing_error(self, processor, mock_raw_event):
        """Test processing event when processing fails."""
        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_registry.get_adapter.side_effect = Exception("Adapter error")

            results = await processor.process_events([mock_raw_event])

        assert len(results) == 1
        result = results[0]
        assert result.success is False
        assert result.event is mock_raw_event
        assert "Adapter error" in result.error

    @pytest.mark.asyncio
    async def test_process_events_concurrent_processing(self, processor, mock_config):
        """Test that events are processed concurrently."""
        # Create multiple events
        events = []
        for i in range(3):
            event = RawEvent(
                chain_type=ChainType.ETHEREUM,
                block_number=12345 + i,
                block_hash=f"0x{i:064x}",
                transaction_hash=f"0x{i:064x}",
                log_index=0,
                contract_address="0x1234567890123456789012345678901234567890",
                raw_data={"test": f"event_{i}"},
                timestamp=1640995200 + i
            )
            events.append(event)

        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            mock_adapter.decode_event.return_value = Mock()
            mock_registry.get_adapter.return_value = mock_adapter

            processor.callback_registry.execute_callback = AsyncMock(return_value=None)

            # Mock asyncio.sleep to simulate concurrent processing
            original_sleep = asyncio.sleep
            sleep_calls = []

            async def mock_sleep(delay):
                sleep_calls.append(delay)
                if delay > 0:  # Only track actual sleep calls, not semaphore timeouts
                    await original_sleep(0.001)  # Small delay for test timing

            with patch('asyncio.sleep', side_effect=mock_sleep):
                results = await processor.process_events(events)

        assert len(results) == 3
        assert all(result.success for result in results)

    @pytest.mark.asyncio
    async def test_process_events_exception_handling(self, processor, mock_raw_event):
        """Test handling exceptions during event processing."""
        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_registry.get_adapter.side_effect = Exception("Critical error")

            results = await processor.process_events([mock_raw_event])

        assert len(results) == 1
        result = results[0]
        assert result.success is False
        assert result.error == "Critical error"

    @pytest.mark.asyncio
    async def test_cleanup_old_events_not_needed(self, processor, mock_config):
        """Test cleanup when cache is not full."""
        # Add fewer events than threshold
        threshold = mock_config.global_config.event_batch_size * 10
        for i in range(threshold - 1):
            processor._processed_events[f"hash{i}"] = 1640995200 + i

        # Should not trigger cleanup
        with patch.object(processor, '_cleanup_old_events') as mock_cleanup:
            mock_cleanup.return_value = None
            await processor._cleanup_old_events()
            # Cleanup is called but should not remove anything
            assert len(processor._processed_events) == threshold - 1

    @pytest.mark.asyncio
    async def test_cleanup_old_events_needed(self, processor, mock_config):
        """Test cleanup when cache is full."""
        # Add more events than threshold
        threshold = mock_config.global_config.event_batch_size * 10
        for i in range(threshold + 10):
            processor._processed_events[f"hash{i}"] = 1640995200 + i

        original_count = len(processor._processed_events)
        await processor._cleanup_old_events()

        # Should have removed about half
        assert len(processor._processed_events) < original_count
        assert len(processor._processed_events) == (threshold + 10) // 2

    @pytest.mark.asyncio
    async def test_detect_reorg_no_support(self, processor):
        """Test reorg detection when adapter doesn't support it."""
        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            # Remove get_latest_block_number attribute
            del mock_adapter.get_latest_block_number
            mock_registry.get_adapter.return_value = mock_adapter

            result = await processor.detect_reorg(ChainType.ETHEREUM)

        assert result is None

    @pytest.mark.asyncio
    async def test_detect_reorg_initialization(self, processor):
        """Test reorg detection initialization."""
        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            mock_adapter.get_latest_block_number.return_value = 12345
            mock_adapter.get_block_by_number.return_value = {"hash": "0x1234567890"}
            mock_registry.get_adapter.return_value = mock_adapter

            result = await processor.detect_reorg(ChainType.ETHEREUM)

        assert result is None
        assert ChainType.ETHEREUM in processor._reorg_detection
        assert 12345 in processor._reorg_detection[ChainType.ETHEREUM]
        assert processor._reorg_detection[ChainType.ETHEREUM][12345] == "0x1234567890"

    @pytest.mark.asyncio
    async def test_detect_reorg_detection(self, processor):
        """Test successful reorg detection."""
        # Initialize cache with different hash
        processor._reorg_detection[ChainType.ETHEREUM] = {12345: "0xoldhash"}

        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            mock_adapter.get_latest_block_number.return_value = 12345
            mock_adapter.get_block_by_number.return_value = {"hash": "0xnewhash"}
            mock_registry.get_adapter.return_value = mock_adapter

            result = await processor.detect_reorg(ChainType.ETHEREUM)

        assert result is not None
        assert isinstance(result, ReorgInfo)
        assert result.block_number == 12345
        assert result.old_block_hash == "0xoldhash"
        assert result.new_block_hash == "0xnewhash"
        assert result.detected_at == 12345

    @pytest.mark.asyncio
    async def test_detect_reorg_async_methods(self, processor):
        """Test reorg detection with async adapter methods."""
        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            mock_adapter.get_latest_block_number = AsyncMock(return_value=12345)
            mock_adapter.get_block_by_number = AsyncMock(return_value={"hash": "0x1234567890"})
            mock_registry.get_adapter.return_value = mock_adapter

            result = await processor.detect_reorg(ChainType.ETHEREUM)

        assert result is None
        mock_adapter.get_latest_block_number.assert_awaited_once()
        mock_adapter.get_block_by_number.assert_awaited_once_with(12345)

    @pytest.mark.asyncio
    async def test_detect_reorg_error_handling(self, processor):
        """Test error handling in reorg detection."""
        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_registry.get_adapter.side_effect = Exception("Adapter error")

            result = await processor.detect_reorg(ChainType.ETHEREUM)

        assert result is None

    @pytest.mark.asyncio
    async def test_detect_reorg_no_block_hash(self, processor):
        """Test reorg detection when block hash is not available."""
        with patch('chain_listener.core.adapter_registry.adapter_registry') as mock_registry:
            mock_adapter = Mock()
            mock_adapter.get_latest_block_number.return_value = 12345
            mock_adapter.get_block_by_number.return_value = None  # No block data
            mock_registry.get_adapter.return_value = mock_adapter

            result = await processor.detect_reorg(ChainType.ETHEREUM)

        assert result is None

    def test_process_result_dataclass_structure(self):
        """Test ProcessResult dataclass structure."""
        # Test that all expected fields exist
        fields = ProcessResult.__dataclass_fields__
        expected_fields = {'success', 'event', 'decoded_event', 'error', 'callback_result'}
        assert set(fields.keys()) == expected_fields

    def test_reorg_info_dataclass_structure(self):
        """Test ReorgInfo dataclass structure."""
        # Test that all expected fields exist
        fields = ReorgInfo.__dataclass_fields__
        expected_fields = {'detected_at', 'old_block_hash', 'new_block_hash', 'block_number', 'depth'}
        assert set(fields.keys()) == expected_fields