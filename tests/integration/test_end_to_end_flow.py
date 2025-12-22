"""End-to-end integration tests for ChainListener.

This module tests the complete workflow from configuration to event processing.
"""

import pytest
import asyncio
import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any, List
from copy import deepcopy
from unittest.mock import Mock, AsyncMock, patch

from chain_listener import ChainListener, ChainListenerConfig, ChainConfig
from chain_listener.models.events import ChainType, RawEvent, DecodedEvent
from chain_listener.exceptions import ChainListenerError

DEFAULT_RPC_CONFIG = {
    "urls": ["https://eth.llamarpc.com"],
    "timeout": 30,
    "retries": 3,
    "rate_limit": {
        "requests_per_second": 10,
        "burst_size": 20
    }
}


@pytest.fixture
def temp_ethereum_config_file():
    """Create a temporary Ethereum configuration file for testing."""
    config_data = {
        "version": "1.0",
        "global_config": {
            "max_concurrent_processing": 2,
            "event_batch_size": 10,
            "callback_timeout": 30
        },
        "chains": {
            "ethereum": {
                "chain_type": "ethereum",
                "chain_id": 1,
                "confirmation_blocks": 1,
                "polling_interval": 100,  # Fast for testing
                "enabled": True,
                "rpc": deepcopy(DEFAULT_RPC_CONFIG),
                "contracts": [
                    {
                        "name": "TestToken",
                        "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                        "events": ["Transfer", "Approval"]
                    }
                ]
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        yield f.name

    # Cleanup
    Path(f.name).unlink()


class TestEndToEndFlow:
    """End-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_lifecycle_from_config_file(self, temp_ethereum_config_file):
        """Test complete lifecycle: config load → init → start → stop."""

        # Mock all external dependencies
        with patch('web3.Web3') as mock_web3:

            # Setup Web3 mock
            mock_web3_instance = Mock()
            mock_web3_instance.is_connected.return_value = True
            mock_web3_instance.eth.chain_id = 1
            mock_web3_instance.eth.block_number = 12345
            mock_web3.return_value = mock_web3_instance
            mock_web3.to_checksum_address = Mock(side_effect=lambda addr: addr)

            # Load from config file and create listener
            listener = ChainListener.from_config_file(temp_ethereum_config_file)

            # Verify initialization
            assert listener is not None
            assert "ethereum" in listener.config.chains
            assert listener.config.chains["ethereum"].chain_type == "ethereum"
            assert not listener.is_listening

            # Register a callback
            events_received = []

            async def test_callback(event):
                events_received.append(event)

            listener.on_event(
                chain_name="ethereum",
                contract_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                event_name="Transfer",
                callback=test_callback
            )

            # Test lifecycle: start → stop
            await listener.start_listening()
            assert listener.is_listening

            await listener.stop_listening()
            assert not listener.is_listening

            # Verify callback was registered by checking the callback registry stats
            stats = listener._callback_registry.get_stats()
            assert stats["total_callbacks"] == 1
            assert stats["unique_contracts"] == 1
            assert stats["unique_events"] == 1
            assert len(stats["callback_list"]) == 1
            assert stats["callback_list"][0]["callback_name"] == "test_callback"
            assert events_received == []

            # Simulate a processed event and ensure callback fires
            decoded_event = DecodedEvent(
                chain_type=ChainType.ETHEREUM,
                contract_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                event_name="Transfer",
                parameters={"from": "0x1111", "to": "0x2222", "value": 1},
                block_number=12345,
                transaction_hash="0xdef...",
                log_index=0,
                timestamp=1640995200
            )
            mock_adapter = Mock()

            async def fake_decode(_event):
                return decoded_event

            mock_adapter.decode_event = AsyncMock(side_effect=fake_decode)
            listener._adapter_registry.get_adapter = Mock(return_value=mock_adapter)

            raw_event = RawEvent(
                chain_type=ChainType.ETHEREUM,
                block_number=12345,
                block_hash="0xabc...",
                transaction_hash="0xdef...",
                log_index=0,
                contract_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                raw_data={},
                timestamp=1640995200
            )

            results = await listener._event_processor.process_events([raw_event])
            assert results[0].success is True
            assert len(events_received) == 1
            assert events_received[0].event_name == "Transfer"

    @pytest.mark.asyncio
    async def test_multiple_callbacks_registration_and_processing(self):
        """Test registering and processing multiple callbacks."""

        config_data = {
            "chains": {
                "ethereum": {
                    "chain_type": "ethereum",
                    "chain_id": 1,
                    "confirmation_blocks": 1,
                    "polling_interval": 100,
                    "enabled": True,
                    "rpc": deepcopy(DEFAULT_RPC_CONFIG)
                }
            }
        }
        config = ChainListenerConfig(**config_data)

        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())

            listener = ChainListener(config)

            # Register multiple callbacks
            transfer_events = []
            approval_events = []

            async def transfer_callback(event):
                transfer_events.append(event)

            async def approval_callback(event):
                approval_events.append(event)

            listener.on_event("ethereum", "0xabc0000000000000000000000000000000000abc", "Transfer", transfer_callback)
            listener.on_event("ethereum", "0xabc0000000000000000000000000000000000abc", "Approval", approval_callback)
            listener.on_event("ethereum", "0xdef0000000000000000000000000000000000def", "Transfer", transfer_callback)

            # Verify callback registry stats
            stats = listener._callback_registry.get_stats()
            assert stats["total_callbacks"] == 3

    @pytest.mark.asyncio
    async def test_system_status_reporting(self, temp_ethereum_config_file):
        """Test system status reporting functionality."""

        with patch('web3.Web3') as mock_web3:
            mock_web3_instance = Mock()
            mock_web3_instance.is_connected.return_value = True
            mock_web3_instance.eth.chain_id = 1
            mock_web3.return_value = mock_web3_instance

            listener = ChainListener.from_config_file(temp_ethereum_config_file)

            # Mock component status methods
            listener._adapter_registry.get_adapter_status = Mock(return_value={
                "ETHEREUM": {"connected": False, "initialized": True}
            })
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

            # Verify status structure
            assert isinstance(status, dict)
            assert "is_listening" in status
            assert "configured_chains" in status
            assert "enabled_chains" in status
            assert "adapter_status" in status
            assert "callback_stats" in status
            assert "processor_stats" in status

            assert "ethereum" in status["configured_chains"]
            assert status["adapter_status"]["ETHEREUM"]["initialized"] is True

    @pytest.mark.asyncio
    async def test_error_handling_in_workflow(self):
        """Test error handling throughout the workflow."""

        # Test invalid configuration
        with pytest.raises(Exception):  # Should raise ValidationError or ChainListenerError
            ChainListener(ChainListenerConfig(chains={}))

        # Test callback registration for invalid chain
        config_data = {
            "chains": {
                "ethereum": {
                    "chain_type": "ethereum",
                    "chain_id": 1,
                    "rpc": deepcopy(DEFAULT_RPC_CONFIG)
                }
            }
        }
        config = ChainListenerConfig(**config_data)

        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())

            listener = ChainListener(config)

            # Should raise error for invalid chain name
            with pytest.raises(ChainListenerError, match="Chain 'invalid' is not configured"):
                listener.on_event(
                    chain_name="invalid",
                    contract_address="0x1230000000000000000000000000000000000123",
                    event_name="Transfer",
                    callback=Mock()
                )

            # Test double start
            with patch.object(listener._adapter_registry, 'connect_all'):
                await listener.start_listening()
                assert listener._is_listening

            with pytest.raises(ChainListenerError, match="Already listening"):
                await listener.start_listening()

    @pytest.mark.asyncio
    async def test_event_processing_simulation(self):
        """Test event processing with simulated data."""

        config_data = {
            "chains": {
                "ethereum": {
                    "chain_type": "ethereum",
                    "chain_id": 1,
                    "confirmation_blocks": 1,
                    "polling_interval": 100,
                    "enabled": True,
                    "rpc": deepcopy(DEFAULT_RPC_CONFIG)
                }
            }
        }
        config = ChainListenerConfig(**config_data)

        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()

            # Create mock adapter that returns mock events
            mock_adapter = Mock()
            mock_adapter.is_connected.return_value = True
            mock_adapter.get_latest_block_number = AsyncMock(return_value=12345)

            listener = ChainListener(config)

            # Register callback
            processed_events = []

            async def test_callback(event):
                processed_events.append(event)

            listener.on_event("ethereum", "0x1230000000000000000000000000000000000123", "Transfer", test_callback)

            # Create sample raw events
            raw_events = [
                RawEvent(
                    chain_type=ChainType.ETHEREUM,
                    block_number=12345,
                    block_hash="0xabc...",
                    transaction_hash="0xdef...",
                    log_index=0,
                    contract_address="0x1230000000000000000000000000000000000123",
                    raw_data={
                        "from": "0x1110000000000000000000000000000000000111",
                        "to": "0x2220000000000000000000000000000000000222",
                        "value": "1000"
                    },
                    timestamp=1640995200
                )
            ]

            # Process events through event processor
            results = await listener._event_processor.process_events(raw_events)

            # Verify processing results
            assert len(results) == 1
            assert results[0].success is True
            assert results[0].event.chain_type == ChainType.ETHEREUM

    @pytest.mark.asyncio
    async def test_configuration_validation(self):
        """Test configuration validation in various scenarios."""

        # Test valid configuration
        valid_config = {
            "chains": {
                "ethereum": {
                    "chain_type": "ethereum",
                    "chain_id": 1,
                    "rpc": deepcopy(DEFAULT_RPC_CONFIG)
                }
            }
        }

        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()

            listener = ChainListener(ChainListenerConfig(**valid_config))
            assert listener is not None

        # Test configuration with missing required fields
        invalid_configs = [
            {"chains": {}},  # Empty chains
            {
                "chains": {
                    "ethereum": {
                        # Missing chain_type
                        "chain_id": 1,
                        "rpc": deepcopy(DEFAULT_RPC_CONFIG)
                    }
                }
            },
            {
                "chains": {
                    "ethereum": {
                        "chain_type": "ethereum",
                        "chain_id": 1
                        # Missing rpc
                    }
                }
            }
        ]

        for invalid_config in invalid_configs:
            with pytest.raises(Exception):  # Should raise ValidationError or ChainListenerError
                ChainListener(ChainListenerConfig(**invalid_config))
