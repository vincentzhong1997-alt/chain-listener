"""Core integration tests for ChainListener components.

This module focuses on testing the integration between core components
without complex external dependencies.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from chain_listener.core.listener import ChainListener
from chain_listener.core.adapter_registry import AdapterRegistry
from chain_listener.core.callback_registry import CallbackRegistry
from chain_listener.core.event_processor import EventProcessor
from chain_listener.models.config import ChainListenerConfig, ChainConfig
from chain_listener.models.events import ChainType, RawEvent, DecodedEvent


class TestCoreComponentIntegration:
    """Integration tests for core components."""

    @pytest.fixture
    def simple_config(self) -> ChainListenerConfig:
        """Create a simple configuration for integration testing."""
        return ChainListenerConfig(
            chains={
                "ethereum": ChainConfig(
                    chain_type="ethereum",
                    chain_id=1,
                    confirmation_blocks=1,
                    polling_interval=1000,
                    rpc_urls=[{
                        "url": "https://eth.llamarpc.com",
                        "priority": 1
                    }],
                    contracts=[]
                )
            }
        )

    def test_callback_registry_integration(self, simple_config):
        """Test integration between ChainListener and CallbackRegistry."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())

            listener = ChainListener(simple_config)

            # Register multiple callbacks
            callback1 = Mock()
            callback2 = Mock()

            listener.on_event("ethereum", "0x123...", "Transfer", callback1)
            listener.on_event("ethereum", "0x123...", "Approval", callback2)
            listener.on_event("ethereum", "0x456...", "Transfer", callback2)

            # Check registry stats
            stats = listener._callback_registry.get_stats()
            assert stats["total_callbacks"] == 3
            assert stats["unique_contracts"] == 2
            assert stats["unique_events"] == 2

    @pytest.mark.asyncio
    async def test_event_processor_integration(self, simple_config):
        """Test integration between ChainListener and EventProcessor."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())

            listener = ChainListener(simple_config)

            # Create sample raw events
            raw_events = [
                RawEvent(
                    chain_type=ChainType.ETHEREUM,
                    block_number=12345,
                    block_hash="0xabc...",
                    transaction_hash="0xdef...",
                    log_index=0,
                    contract_address="0x123...",
                    raw_data={},
                    timestamp=1640995200
                )
            ]

            # Mock adapter decoding
            mock_adapter = Mock()
            mock_adapter.decode_event = AsyncMock(return_value=DecodedEvent(
                chain_type=ChainType.ETHEREUM,
                contract_address="0x123...",
                event_name="Transfer",
                parameters={"from": "0x111...", "to": "0x222...", "value": "1000"},
                block_number=12345,
                transaction_hash="0xdef...",
                log_index=0,
                timestamp=1640995200
            ))

            with patch.object(listener._event_processor, '_get_adapter', return_value=mock_adapter):
                # Process events
                results = await listener._event_processor.process_events(raw_events)

                assert len(results) == 1
                assert results[0].success is True
                assert results[0].decoded_event.event_name == "Transfer"

    def test_adapter_registry_integration(self, simple_config):
        """Test integration between ChainListener and AdapterRegistry."""
        with patch('chain_listener.core.listener.AdapterRegistry') as MockRegistry:
            mock_registry_instance = MockRegistry.return_value
            mock_registry_instance.register_adapter = Mock()
            mock_registry_instance.get_adapter_status = Mock(return_value={"ethereum": {"connected": False}})

            listener = ChainListener(simple_config)

            # Check that adapter registry was initialized
            assert listener._adapter_registry is not None
            assert mock_registry_instance.register_adapter.called

    @pytest.mark.asyncio
    async def test_lifecycle_management_integration(self, simple_config):
        """Test start/stop lifecycle integration."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())
            mock_registry.get_adapter_status = Mock(return_value={})

            listener = ChainListener(simple_config)

            # Test start listening
            await listener.start_listening()
            assert listener._is_listening
            mock_registry.connect_all.assert_called_once()

            # Test stop listening
            await listener.stop_listening()
            assert not listener._is_listening
            mock_registry.disconnect_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_status_integration(self, simple_config):
        """Test system status reporting integration."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())
            mock_registry.get_adapter_status = Mock(return_value={"ethereum": {"connected": False}})

            listener = ChainListener(simple_config)

            # Mock component status methods
            listener._callback_registry.get_stats = Mock(return_value={
                "total_callbacks": 2,
                "unique_contracts": 1,
                "unique_events": 2
            })
            listener._event_processor.get_stats = Mock(return_value={
                "processed_events": 0,
                "error_count": 0
            })

            # Get system status
            status = await listener.get_system_status()

            # Verify status structure and content
            assert isinstance(status, dict)
            assert "is_listening" in status
            assert "configured_chains" in status
            assert "adapter_status" in status
            assert "callback_stats" in status
            assert "processor_stats" in status
            assert "ethereum" in status["configured_chains"]
            assert status["callback_stats"]["total_callbacks"] == 2

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, simple_config):
        """Test error handling integration between components."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())

            listener = ChainListener(simple_config)

            # Test callback registration for invalid chain
            with pytest.raises(Exception):
                listener.on_event(
                    chain_name="invalid_chain",
                    contract_address="0x123...",
                    event_name="Transfer",
                    callback=Mock()
                )

            # Test double start
            listener._is_listening = True
            with pytest.raises(Exception, match="Already listening"):
                await listener.start_listening()

    @pytest.mark.asyncio
    async def test_event_deduplication_integration(self, simple_config):
        """Test event deduplication in integration."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())

            listener = ChainListener(simple_config)

            # Create duplicate events
            duplicate_events = [
                RawEvent(
                    chain_type=ChainType.ETHEREUM,
                    block_number=12345,
                    block_hash="0xabc...",
                    transaction_hash="0xdef...",
                    log_index=0,
                    contract_address="0x123...",
                    raw_data={},
                    timestamp=1640995200
                ),
                RawEvent(
                    chain_type=ChainType.ETHEREUM,
                    block_number=12345,
                    block_hash="0xabc...",
                    transaction_hash="0xdef...",
                    log_index=0,
                    contract_address="0x123...",
                    raw_data={},
                    timestamp=1640995200
                )
            ]

            # Mock adapter for decoding
            mock_adapter = Mock()
            mock_adapter.decode_event = AsyncMock(return_value=DecodedEvent(
                chain_type=ChainType.ETHEREUM,
                contract_address="0x123...",
                event_name="Transfer",
                parameters={},
                block_number=12345,
                transaction_hash="0xdef...",
                log_index=0,
                timestamp=1640995200
            ))

            with patch.object(listener._event_processor, '_get_adapter', return_value=mock_adapter):
                # Process duplicate events
                results = await listener._event_processor.process_events(duplicate_events)

                # Should only process one due to deduplication
                success_results = [r for r in results if r.success]
                assert len(success_results) == 1

    @pytest.mark.asyncio
    async def test_callback_execution_integration(self, simple_config):
        """Test callback execution in integration."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())

            listener = ChainListener(simple_config)

            # Register callback that tracks execution
            callback_calls = []

            async def test_callback(event):
                callback_calls.append(event)
                return f"Processed: {event.transaction_hash}"

            listener.on_event("ethereum", "0x123...", "Transfer", test_callback)

            # Create event
            raw_event = RawEvent(
                chain_type=ChainType.ETHEREUM,
                block_number=12345,
                block_hash="0xabc...",
                transaction_hash="0xdef...",
                log_index=0,
                contract_address="0x123...",
                raw_data={},
                timestamp=1640995200
            )

            # Mock adapter and callback execution
            mock_adapter = Mock()
            mock_adapter.decode_event = AsyncMock(return_value=DecodedEvent(
                chain_type=ChainType.ETHEREUM,
                contract_address="0x123...",
                event_name="Transfer",
                parameters={},
                block_number=12345,
                transaction_hash="0xdef...",
                log_index=0,
                timestamp=1640995200
            ))

            with patch.object(listener._event_processor, '_get_adapter', return_value=mock_adapter):
                # Process event
                results = await listener._event_processor.process_events([raw_event])

                # Verify processing results
                assert len(results) == 1
                assert results[0].success is True

                # Verify callback was actually called with correct event data
                assert len(callback_calls) == 1
                assert callback_calls[0].chain_type == ChainType.ETHEREUM
                assert callback_calls[0].contract_address == "0x123..."
                assert callback_calls[0].event_name == "Transfer"
                assert callback_calls[0].block_number == 12345
                assert callback_calls[0].transaction_hash == "0xdef..."