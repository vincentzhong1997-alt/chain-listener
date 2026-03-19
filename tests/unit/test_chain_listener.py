"""Tests for ChainListener main API.

This module tests the ChainListener class and its integration
with other components.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from web3 import Web3

from chain_listener.core.listener import ChainListener
from chain_listener.models.config import ChainListenerConfig
from chain_listener.models.events import ChainType, RawEvent, DecodedEvent
from chain_listener.exceptions import ChainListenerError


class TestChainListener:
    """Test cases for ChainListener class."""

    @pytest.fixture
    def sample_config(self) -> ChainListenerConfig:
        """Create a sample configuration for testing."""
        config_data = {
            "chains": {
                "ethereum": {
                    "chain_type": "ethereum",
                    "chain_id": 1,
                    "confirmation_blocks": 12,
                    "polling_interval": 15000,
                    "rpc": {
                        "urls": ["https://eth.llamarpc.com"],
                        "timeout": 30,
                        "retries": 3,
                        "rate_limit": {
                            "requests_per_second": 5,
                            "burst_size": 10,
                        },
                    },
                    "contracts": [
                        {
                            "name": "WBTC",
                            "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                            "events": ["Transfer", "Burn"]
                        }
                    ]
                }
            },
            "global_config": {
                "max_concurrent_processing": 10,
                "event_batch_size": 100,
                "log_level": "INFO"
            }
        }
        return ChainListenerConfig(**config_data)

    @pytest.fixture
    def chain_listener(self, sample_config: ChainListenerConfig) -> ChainListener:
        """Create a ChainListener instance for testing."""
        # Mock adapter registration to avoid actual blockchain connections
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.connect_all = AsyncMock()
            mock_registry.disconnect_all = AsyncMock()
            mock_registry.get_adapter = Mock(return_value=Mock())
            mock_registry.get_adapter_status = Mock(return_value={})

            return ChainListener(sample_config)

    def test_chain_listener_initialization(self, chain_listener: ChainListener):
        """Test that ChainListener can be initialized with valid config."""
        assert chain_listener.config is not None
        assert chain_listener._callback_registry is not None
        assert chain_listener._event_processor is not None
        assert chain_listener._is_listening is False

    def test_chain_listener_from_config_file(self):
        """Test creating ChainListener from config file."""
        config_data = {
            "chains": {
                "ethereum": {
                    "chain_type": "ethereum",
                    "rpc": {"endpoints": [{"url": "https://eth.llamarpc.com"}]}
                }
            }
        }

        with patch('chain_listener.models.config.ChainListenerConfig.from_file') as mock_from_file:
            mock_from_file.return_value = ChainListenerConfig(**config_data)

            with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
                mock_registry.register_adapter = Mock()

                listener = ChainListener.from_config_file("test_config.yaml")

                assert listener is not None
                mock_from_file.assert_called_once_with("test_config.yaml")

    def test_invalid_config_raises_error(self):
        """Test that invalid configuration raises ChainListenerError."""
        # Empty config should raise Pydantic ValidationError at config creation time
        config_data = {"chains": {}}

        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()

            # Pydantic V2 validates at creation time, so we expect ValidationError
            with pytest.raises(Exception) as exc_info:
                ChainListener(ChainListenerConfig(**config_data))

            # Verify it's the expected validation error
            assert "too_short" in str(exc_info.value) or "Dictionary should have at least 1 item" in str(exc_info.value)

    def test_on_event_callback_registration(self, chain_listener: ChainListener):
        """Test registering event callbacks."""
        callback = Mock()

        chain_listener.on_event(
            chain_name="ethereum",
            contract_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
            event_name="Transfer",
            callback=callback
        )

        # Verify callback was registered
        registered_callback = chain_listener._callback_registry.get_callback(
            Web3.to_checksum_address("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"),
            "Transfer"
        )
        assert registered_callback == callback

    def test_on_event_invalid_chain_raises_error(self, chain_listener: ChainListener):
        """Test that registering callback for invalid chain raises error."""
        callback = Mock()

        with pytest.raises(ChainListenerError, match="Chain 'invalid' is not configured"):
            chain_listener.on_event(
                chain_name="invalid",
                contract_address="0x1234567890123456789012345678901234567890",
                event_name="Transfer",
                callback=callback
            )

    def test_on_event_unknown_contract_raises_error(self, chain_listener: ChainListener):
        """Test registering callback for contract not in config fails."""
        callback = Mock()

        with pytest.raises(ChainListenerError, match="is not configured for chain"):
            chain_listener.on_event(
                chain_name="ethereum",
                contract_address="0x0000000000000000000000000000000000000000",
                event_name="Transfer",
                callback=callback
            )

    def test_on_event_unknown_event_raises_error(self, chain_listener: ChainListener):
        """Test registering callback for event not declared fails."""
        callback = Mock()

        with pytest.raises(ChainListenerError, match="Event 'Approve' is not configured"):
            chain_listener.on_event(
                chain_name="ethereum",
                contract_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                event_name="Approve",
                callback=callback
            )

    @pytest.mark.asyncio
    async def test_start_listening_when_already_listening_raises_error(self, chain_listener: ChainListener):
        """Test that starting to listen when already listening raises error."""
        chain_listener._is_listening = True

        with pytest.raises(ChainListenerError, match="Already listening for events"):
            await chain_listener.start_listening()

    @pytest.mark.asyncio
    async def test_get_system_status(self, chain_listener: ChainListener):
        """Test getting system status."""
        chain_listener._adapter_registry.get_adapter_status = Mock(return_value={})
        chain_listener._callback_registry.get_stats = Mock(return_value={})
        chain_listener._event_processor.get_stats = Mock(return_value={})

        status = await chain_listener.get_system_status()

        assert isinstance(status, dict)
        assert "is_listening" in status
        assert "configured_chains" in status
        assert "enabled_chains" in status

    @pytest.mark.asyncio
    async def test_get_events_filters_by_registered_event(self, chain_listener: ChainListener):
        """Listener should only keep events that match registered callbacks."""
        target_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

        callback = Mock()
        chain_listener.on_event(
            chain_name="ethereum",
            contract_address=target_address,
            event_name="Transfer",
            callback=callback,
        )

        adapter = Mock()
        adapter.chain_type = ChainType.ETHEREUM
        adapter.get_logs = AsyncMock(return_value=[
            {
                "address": target_address,
                "block_number": 100,
                "block_hash": "0xabc",
                "transaction_hash": "0x1",
                "log_index": 0,
                "timestamp": 1,
                "event_name": "Transfer",
            },
            {
                "address": target_address,
                "block_number": 101,
                "block_hash": "0xdef",
                "transaction_hash": "0x2",
                "log_index": 1,
                "timestamp": 2,
                "event_name": "Approval",
            },
        ])

        _ = await chain_listener._get_events_from_chain(adapter, ChainType.ETHEREUM, 1, 200)

        adapter.get_logs.assert_awaited_once()
        _, kwargs = adapter.get_logs.await_args
        expected_address = Web3.to_checksum_address(target_address)
        assert kwargs["event_filters"] == {expected_address: ["Transfer"]}

    @pytest.mark.asyncio
    async def test_get_latest_block(self, chain_listener: ChainListener):
        """Test getting latest block number."""
        mock_adapter = Mock()
        mock_adapter.get_latest_block_number = AsyncMock(return_value=12345)
        chain_listener._adapter_registry.get_adapter = Mock(return_value=mock_adapter)

        block_number = await chain_listener.get_latest_block("ethereum")

        assert block_number == 12345
        mock_adapter.get_latest_block_number.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_block_invalid_chain_raises_error(self, chain_listener: ChainListener):
        """Test that getting latest block for invalid chain raises error."""
        with pytest.raises(ChainListenerError, match="Chain 'invalid' is not configured"):
            await chain_listener.get_latest_block("invalid")

    @pytest.mark.asyncio
    async def test_context_manager_not_supported(self, chain_listener: ChainListener):
        """ChainListener should not be used as an async context manager."""
        with pytest.raises(TypeError):
            async with chain_listener:
                pass


class TestChainListenerIntegration:
    """Integration tests for ChainListener with real components."""

    @pytest.fixture
    def simple_config(self) -> ChainListenerConfig:
        """Create a simple configuration for integration tests."""
        config_data = {
            "chains": {
                "ethereum": {
                    "chain_type": "ethereum",
                    "chain_id": 1,
                    "confirmation_blocks": 1,
                    "polling_interval": 1000,
                    "rpc": {
                        "endpoints": [{"url": "https://eth.llamarpc.com"}]
                    },
                    "contracts": [
                        {
                            "name": "TokenA",
                            "address": "0x1234567890123456789012345678901234567890",
                            "events": ["Transfer", "Approval"],
                        },
                        {
                            "name": "TokenB",
                            "address": "0x9999999999999999999999999999999999999999",
                            "events": ["Transfer"],
                        },
                    ],
                }
            },
            "global_config": {
                "max_concurrent_processing": 2,
                "event_batch_size": 10,
                "log_level": "DEBUG"
            }
        }
        return ChainListenerConfig(**config_data)

    def test_callback_registry_integration(self, simple_config: ChainListenerConfig):
        """Test integration with CallbackRegistry."""
        with patch('chain_listener.core.listener.adapter_registry'):
            listener = ChainListener(simple_config)

            # Register multiple callbacks
            callback1 = Mock()
            callback2 = Mock()

            listener.on_event(
                "ethereum", "0x1234567890123456789012345678901234567890", "Transfer", callback1
            )
            listener.on_event(
                "ethereum", "0x1234567890123456789012345678901234567890", "Approval", callback2
            )
            listener.on_event(
                "ethereum", "0x9999999999999999999999999999999999999999", "Transfer", callback2
            )

            # Check registry stats
            stats = listener._callback_registry.get_stats()
            assert stats["total_callbacks"] == 3
            assert stats["unique_contracts"] == 2
            assert stats["unique_events"] == 2

    @pytest.mark.asyncio
    async def test_event_processor_integration(self, simple_config: ChainListenerConfig):
        """Test integration with EventProcessor."""
        with patch('chain_listener.core.listener.adapter_registry'):
            listener = ChainListener(simple_config)

            # Create sample raw events
            raw_events = [
                RawEvent(
                    chain_type=ChainType.ETHEREUM,
                    block_number=12345,
                    block_hash="0xabc...",
                    transaction_hash="0xdef...",
                    log_index=0,
                    contract_address="0x1234567890123456789012345678901234567890",
                    raw_data={},
                    timestamp=1640995200
                )
            ]

            # Mock adapter decoding
            mock_adapter = Mock()
                mock_adapter.decode_event = AsyncMock(return_value=DecodedEvent(
                    chain_type=ChainType.ETHEREUM,
                    contract_address="0x1234567890123456789012345678901234567890",
                    event_name="Transfer",
                    parameters={"from": "0x111...", "to": "0x222...", "value": "1000"},
                    block_number=12345,
                transaction_hash="0xdef...",
                log_index=0,
                timestamp=1640995200
            ))

            listener._event_processor._adapter_registry.get_adapter.return_value = mock_adapter
            results = await listener._event_processor.process_events(raw_events)

            assert len(results) == 1
            assert results[0].success is True
            assert results[0].decoded_event.event_name == "Transfer"

    def test_adapter_registry_integration(self, simple_config: ChainListenerConfig):
        """Test integration with AdapterRegistry."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()
            mock_registry.get_adapter_status = Mock(return_value={"ethereum": {"connected": False}})

            listener = ChainListener(simple_config)

            # Check that adapters were registered
            assert mock_registry.register_adapter.call_count == 1

            # Get system status
            asyncio.run(listener.get_system_status())
            mock_registry.get_adapter_status.assert_called()
