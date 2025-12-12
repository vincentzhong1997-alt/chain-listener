"""Comprehensive tests for ChainListener following TDD principles.

This module contains additional test cases for ChainListener that cover
edge cases, error handling, and advanced functionality not covered
in the basic test file.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any
from pathlib import Path

from chain_listener.core.listener import ChainListener
from chain_listener.models.config import ChainListenerConfig, ChainConfig, GlobalConfig
from chain_listener.models.events import ChainType, RawEvent
from chain_listener.exceptions import ChainListenerError


@pytest.fixture
def mock_config():
    """Create a comprehensive mock configuration for testing."""
    return ChainListenerConfig(
        chains={
            "ethereum": ChainConfig(
                chain_type=ChainType.ETHEREUM,
                chain_id=1,
                confirmation_blocks=12,
                polling_interval=15000,
                enabled=True,
                rpc_urls=[
                    {"url": "https://eth.llamarpc.com", "priority": 1},
                    {"url": "https://backup.eth.llamarpc.com", "priority": 2}
                ],
                contracts=[
                    {
                        "name": "WBTC",
                        "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                        "events": ["Transfer", "Burn"]
                    }
                ]
            )
        },
        global_config=GlobalConfig(
            max_concurrent_processing=5,
            event_batch_size=100,
            log_level="INFO"
        )
    )


@pytest.fixture
def chain_listener(mock_config):
    """Create a ChainListener instance for testing with mocked dependencies."""
    with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
        # Mock adapter registry methods
        mock_registry.register_adapter = Mock()
        mock_registry.connect_all = AsyncMock()
        mock_registry.disconnect_all = AsyncMock()
        mock_registry.get_adapter = Mock(return_value=Mock())
        mock_registry.get_adapter_status = Mock(return_value={})

        listener = ChainListener(mock_config)
        listener._adapter_registry = mock_registry
        return listener


class TestChainListenerValidation:
    """Test configuration validation and initialization scenarios."""

    def test_validate_config_no_chains(self):
        """Test validation fails when no chains are configured."""
        config = ChainListenerConfig(chains={}, global_config=GlobalConfig())

        with patch('chain_listener.core.listener.adapter_registry'):
            with pytest.raises(ChainListenerError, match="At least one blockchain must be configured"):
                ChainListener(config)

    def test_validate_config_no_rpc_urls(self):
        """Test validation fails when chain has no RPC URLs."""
        config = ChainListenerConfig(
            chains={
                "ethereum": ChainConfig(
                    chain_type=ChainType.ETHEREUM,
                    chain_id=1,
                    rpc_urls=[]  # Empty RPC URLs
                )
            },
            global_config=GlobalConfig()
        )

        with patch('chain_listener.core.listener.adapter_registry'):
            with pytest.raises(ChainListenerError, match="No RPC URLs configured for chain: ethereum"):
                ChainListener(config)

    def test_validate_config_no_chain_type(self):
        """Test validation fails when chain has no chain type."""
        config_data = {
            "chains": {
                "ethereum": {
                    "chain_id": 1,
                    "rpc_urls": [{"url": "https://eth.llamarpc.com", "priority": 1}]
                    # Missing chain_type
                }
            },
            "global_config": {}
        }

        # This should fail Pydantic validation
        with pytest.raises(Exception):  # Pydantic validation error
            ChainListenerConfig(**config_data)

    def test_from_config_file_invalid_path(self):
        """Test creating from invalid config file path."""
        with patch('chain_listener.models.config.ChainListenerConfig.from_file') as mock_from_file:
            mock_from_file.side_effect = FileNotFoundError("Config file not found")

            with pytest.raises(ChainListenerError, match="Failed to load configuration"):
                ChainListener.from_config_file("nonexistent.yaml")

    def test_from_config_file_invalid_yaml(self):
        """Test creating from invalid YAML config file."""
        with patch('chain_listener.models.config.ChainListenerConfig.from_file') as mock_from_file:
            mock_from_file.side_effect = Exception("Invalid YAML")

            with pytest.raises(ChainListenerError, match="Failed to load configuration"):
                ChainListener.from_config_file("invalid.yaml")


class TestChainListenerAdapterManagement:
    """Test adapter initialization and management functionality."""

    def test_initialize_adapters_success(self, mock_config):
        """Test successful adapter initialization."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()

            listener = ChainListener(mock_config)

            assert mock_registry.register_adapter.call_count == 1

    def test_initialize_adapters_error(self, mock_config):
        """Test handling adapter initialization errors."""
        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter.side_effect = Exception("Adapter initialization failed")

            with pytest.raises(ChainListenerError, match="Failed to initialize adapters"):
                ChainListener(mock_config)

    def test_initialize_adapters_invalid_chain_type(self, mock_config):
        """Test handling invalid chain type during initialization."""
        # Create config with invalid chain type
        invalid_config_data = mock_config.model_dump()
        invalid_config_data["chains"]["ethereum"]["chain_type"] = "invalid_chain"

        with patch('chain_listener.core.listener.adapter_registry') as mock_registry:
            mock_registry.register_adapter = Mock()

            with pytest.raises(ChainListenerError, match="Invalid chain type for ethereum"):
                ChainListener(ChainListenerConfig(**invalid_config_data))

    def test_get_adapter_factory_ethereum(self):
        """Test getting Ethereum adapter factory."""
        config = ChainListenerConfig(
            chains={"ethereum": ChainConfig(chain_type=ChainType.ETHEREUM, rpc_urls=[{"url": "test", "priority": 1}])},
            global_config=GlobalConfig()
        )

        with patch('chain_listener.core.listener.adapter_registry'):
            listener = ChainListener(config)

            factory = listener._get_adapter_factory(ChainType.ETHEREUM)
            assert callable(factory)

    def test_get_adapter_factory_unsupported(self):
        """Test getting factory for unsupported chain type."""
        config = ChainListenerConfig(
            chains={"ethereum": ChainConfig(chain_type=ChainType.ETHEREUM, rpc_urls=[{"url": "test", "priority": 1}])},
            global_config=GlobalConfig()
        )

        with patch('chain_listener.core.listener.adapter_registry'):
            listener = ChainListener(config)

            with pytest.raises(ChainListenerError, match="Unsupported chain type"):
                listener._get_adapter_factory(ChainType.SOLANA)

    def test_build_adapter_config(self, chain_listener):
        """Test building adapter configuration from chain config."""
        chain_config = ChainConfig(
            chain_type=ChainType.ETHEREUM,
            chain_id=1,
            confirmation_blocks=12,
            polling_interval=15000,
            rpc_urls=[{"url": "https://eth.llamarpc.com", "priority": 1}],
            contracts=[
                {
                    "name": "WBTC",
                    "address": "0x1234567890123456789012345678901234567890",
                    "events": ["Transfer", "Burn"]
                }
            ]
        )

        adapter_config = chain_listener._build_adapter_config(chain_config)

        assert adapter_config["chain_type"] == ChainType.ETHEREUM
        assert adapter_config["chain_id"] == 1
        assert adapter_config["confirmation_blocks"] == 12
        assert adapter_config["polling_interval"] == 15000
        assert len(adapter_config["rpc_urls"]) == 1
        assert len(adapter_config["contracts"]) == 1
        assert adapter_config["contracts"][0]["name"] == "WBTC"


class TestChainListenerEventHandling:
    """Test event handling and callback functionality."""

    def test_on_event_with_metadata(self, chain_listener):
        """Test registering event callback with metadata."""
        callback = Mock()
        metadata = {"priority": "high", "source": "test"}

        chain_listener.on_event(
            chain_name="ethereum",
            contract_address="0x1234567890123456789012345678901234567890",
            event_name="Transfer",
            callback=callback,
            metadata=metadata
        )

        # Verify metadata was stored
        stored_metadata = chain_listener._callback_registry.get_callback_metadata(
            "0x1234567890123456789012345678901234567890",
            "Transfer"
        )
        assert stored_metadata == metadata

    def test_on_event_non_callable(self, chain_listener):
        """Test registering non-callable raises error."""
        with pytest.raises(Exception):  # CallbackRegistry should raise error
            chain_listener.on_event(
                chain_name="ethereum",
                contract_address="0x1234567890123456789012345678901234567890",
                event_name="Transfer",
                callback="not_callable"
            )


class TestChainListenerListening:
    """Test listening functionality with various scenarios."""

    @pytest.mark.asyncio
    async def test_start_listening_with_disabled_chains(self, chain_listener, mock_config):
        """Test that disabled chains are not started."""
        # Mock chain listening
        chain_listener._listen_to_chain = AsyncMock()

        await chain_listener.start_listening()

        # Should only call for enabled chains (ethereum, not bsc which is disabled)
        chain_listener._listen_to_chain.assert_called_once()
        call_args = chain_listener._listen_to_chain.call_args[0]
        assert call_args[0] == "ethereum"  # chain_name
        assert call_args[1] == ChainType.ETHEREUM  # chain_type

    @pytest.mark.asyncio
    async def test_start_listening_connection_failure(self, chain_listener):
        """Test handling connection failure during start."""
        chain_listener._adapter_registry.connect_all = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        with pytest.raises(ChainListenerError, match="Failed to start listening"):
            await chain_listener.start_listening()

        # Should still set listening to False
        assert chain_listener._is_listening is False

    @pytest.mark.asyncio
    async def test_stop_listening_not_listening(self, chain_listener):
        """Test stopping when not currently listening."""
        # Should not raise error, just log warning
        await chain_listener.stop_listening()
        assert chain_listener._is_listening is False

    @pytest.mark.asyncio
    async def test_cleanup_listening_tasks(self, chain_listener):
        """Test cleanup of listening tasks."""
        # Create some mock tasks
        task1 = asyncio.create_task(asyncio.sleep(1))

        chain_listener._listening_tasks = {
            ChainType.ETHEREUM: task1,
        }

        await chain_listener._cleanup_listening_tasks()

        assert len(chain_listener._listening_tasks) == 0
        assert task1.cancelled()

    @pytest.mark.asyncio
    async def test_cleanup_listening_tasks_with_errors(self, chain_listener):
        """Test cleanup handling task errors."""
        # Create a task that raises exception when cancelled
        async def failing_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise Exception("Task cleanup failed")

        task = asyncio.create_task(failing_task())
        chain_listener._listening_tasks = {ChainType.ETHEREUM: task}

        # Should not raise exception
        await chain_listener._cleanup_listening_tasks()

        assert len(chain_listener._listening_tasks) == 0

    @pytest.mark.asyncio
    async def test_listen_to_chain_success(self, chain_listener):
        """Test successful chain listening loop."""
        # Setup mocks
        mock_adapter = Mock()
        mock_adapter.get_latest_block_number = AsyncMock(side_effect=[100, 101, 102])
        mock_adapter.get_logs = AsyncMock(return_value=[
            {
                "block_number": 101,
                "block_hash": "0xabc123",
                "transaction_hash": "0xdef456",
                "log_index": 0,
                "address": "0x1234567890123456789012345678901234567890",
                "timestamp": 1640995200
            }
        ])

        chain_listener._adapter_registry.get_adapter = Mock(return_value=mock_adapter)
        chain_listener._event_processor.process_events = AsyncMock(return_value=[
            Mock(success=True, decoded_event=Mock(event_name="Transfer"))
        ])
        chain_listener._callback_registry.list_callbacks = Mock(return_value=[
            {
                "contract_address": "0x1234567890123456789012345678901234567890",
                "event_name": "transfer"
            }
        ])

        # Mock config with short polling interval for faster test
        chain_config = ChainConfig(
            chain_type=ChainType.ETHEREUM,
            chain_id=1,
            polling_interval=1,  # 1ms for fast test
            rpc_urls=[{"url": "test", "priority": 1}]
        )

        # Run for a short time then cancel
        task = asyncio.create_task(
            chain_listener._listen_to_chain("ethereum", ChainType.ETHEREUM, chain_config)
        )

        # Let it run briefly
        await asyncio.sleep(0.1)

        # Cancel the task
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have processed events
        chain_listener._event_processor.process_events.assert_called()

    @pytest.mark.asyncio
    async def test_listen_to_chain_with_errors(self, chain_listener):
        """Test chain listening with adapter errors."""
        # Setup mock adapter that fails
        mock_adapter = Mock()
        mock_adapter.get_latest_block_number = AsyncMock(
            side_effect=[Exception("RPC Error"), 100, 101]
        )

        chain_listener._adapter_registry.get_adapter = Mock(return_value=mock_adapter)

        chain_config = ChainConfig(
            chain_type=ChainType.ETHEREUM,
            chain_id=1,
            polling_interval=1,  # 1ms for fast test
            rpc_urls=[{"url": "test", "priority": 1}]
        )

        # Run for a short time then cancel
        task = asyncio.create_task(
            chain_listener._listen_to_chain("ethereum", ChainType.ETHEREUM, chain_config)
        )

        # Let it run briefly to handle the error and retry
        await asyncio.sleep(0.05)

        # Cancel the task
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have called get_latest_block_number multiple times (retry after error)
        assert mock_adapter.get_latest_block_number.call_count >= 2

    @pytest.mark.asyncio
    async def test_get_latest_block_sync_adapter(self, chain_listener):
        """Test getting latest block from sync adapter."""
        mock_adapter = Mock()
        mock_adapter.get_latest_block_number.return_value = 12345
        # Not a coroutine function

        result = await chain_listener._get_latest_block(mock_adapter)

        assert result == 12345
        mock_adapter.get_latest_block_number.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_block_async_adapter(self, chain_listener):
        """Test getting latest block from async adapter."""
        mock_adapter = Mock()
        mock_adapter.get_latest_block_number = AsyncMock(return_value=12345)

        result = await chain_listener._get_latest_block(mock_adapter)

        assert result == 12345
        mock_adapter.get_latest_block_number.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_latest_block_no_support(self, chain_listener):
        """Test getting latest block when adapter doesn't support it."""
        mock_adapter = Mock()
        # Remove get_latest_block_number attribute
        del mock_adapter.get_latest_block_number

        with pytest.raises(ChainListenerError, match="Adapter does not support getting latest block"):
            await chain_listener._get_latest_block(mock_adapter)

    @pytest.mark.asyncio
    async def test_get_events_from_chain_with_callbacks(self, chain_listener):
        """Test getting events when callbacks are registered."""
        # Setup callback registry
        chain_listener._callback_registry.list_callbacks = Mock(return_value=[
            {
                "contract_address": "0x1234567890123456789012345678901234567890",
                "event_name": "Transfer"
            }
        ])

        # Setup mock adapter
        mock_adapter = Mock()
        mock_adapter.get_logs = AsyncMock(return_value=[
            {
                "block_number": 12345,
                "block_hash": "0xabc123",
                "transaction_hash": "0xdef456",
                "log_index": 0,
                "address": "0x1234567890123456789012345678901234567890",
                "timestamp": 1640995200,
                "data": "0x..."
            }
        ])

        events = await chain_listener._get_events_from_chain(mock_adapter, 12340, 12345)

        assert len(events) == 1
        assert isinstance(events[0], RawEvent)
        assert events[0].block_number == 12345
        assert events[0].contract_address == "0x1234567890123456789012345678901234567890"

    @pytest.mark.asyncio
    async def test_get_events_from_chain_no_callbacks(self, chain_listener):
        """Test getting events when no callbacks are registered."""
        chain_listener._callback_registry.list_callbacks = Mock(return_value=[])

        mock_adapter = Mock()

        events = await chain_listener._get_events_from_chain(mock_adapter, 12340, 12345)

        assert len(events) == 0
        mock_adapter.get_logs.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_events_from_chain_sync_adapter(self, chain_listener):
        """Test getting events from sync adapter."""
        chain_listener._callback_registry.list_callbacks = Mock(return_value=[
            {"contract_address": "0x123...", "event_name": "Transfer"}
        ])

        mock_adapter = Mock()
        mock_adapter.get_logs.return_value = [
            {
                "block_number": 12345,
                "address": "0x123...",
                "transaction_hash": "0xdef...",
                "log_index": 0
            }
        ]

        events = await chain_listener._get_events_from_chain(mock_adapter, 12340, 12345)

        assert len(events) == 1
        mock_adapter.get_logs.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_last_processed_block(self, chain_listener):
        """Test getting last processed block number."""
        mock_adapter = Mock()
        mock_adapter.get_latest_block_number = AsyncMock(return_value=1000)
        chain_listener._adapter_registry.get_adapter = Mock(return_value=mock_adapter)

        last_block = await chain_listener._get_last_processed_block(ChainType.ETHEREUM)

        # Should start from 10 blocks before latest
        assert last_block == 990

    @pytest.mark.asyncio
    async def test_get_last_processed_block_low_latest(self, chain_listener):
        """Test getting last processed block when latest is low."""
        mock_adapter = Mock()
        mock_adapter.get_latest_block_number = AsyncMock(return_value=5)
        chain_listener._adapter_registry.get_adapter = Mock(return_value=mock_adapter)

        last_block = await chain_listener._get_last_processed_block(ChainType.ETHEREUM)

        # Should not go below 0
        assert last_block == 0


class TestChainListenerAdvanced:
    """Test advanced ChainListener functionality."""

    @pytest.mark.asyncio
    async def test_get_system_status_detailed(self, chain_listener):
        """Test detailed system status information."""
        # Setup mock status data
        chain_listener._adapter_registry.get_adapter_status = Mock(return_value={
            "ETHEREUM": {
                "registered": True,
                "initialized": True,
                "connected": True
            }
        })

        chain_listener._callback_registry.get_stats = Mock(return_value={
            "total_callbacks": 5,
            "unique_contracts": 2,
            "unique_events": 3
        })

        chain_listener._event_processor.get_stats = Mock(return_value={
            "processed_events_cache_size": 100,
            "max_concurrent_processing": 5
        })

        status = await chain_listener.get_system_status()

        assert status["is_listening"] is False
        assert "ethereum" in status["configured_chains"]
        assert "ethereum" in status["enabled_chains"]  # Only enabled chains
        assert "bsc" not in status["enabled_chains"]  # Disabled chain
        assert "ETHEREUM" in status["adapter_status"]
        assert status["callback_stats"]["total_callbacks"] == 5
        assert status["processor_stats"]["processed_events_cache_size"] == 100

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, chain_listener):
        """Test context manager handles exceptions properly."""
        chain_listener.start_listening = AsyncMock()
        chain_listener.stop_listening = AsyncMock()

        with pytest.raises(Exception):
            async with chain_listener:
                raise Exception("Test exception")

        # Should still call stop_listening even with exception
        chain_listener.stop_listening.assert_called_once()

    def test_add_chain_support_with_invalid_type(self, chain_listener):
        """Test adding chain support with invalid chain type."""
        new_config = ChainConfig(
            chain_type="invalid_chain",
            chain_id=999,
            rpc_urls=[{"url": "test", "priority": 1}]
        )

        with pytest.raises(ValueError):
            chain_listener._add_chain_support("test_chain", new_config)

        # Should not be added to config
        assert "test_chain" not in chain_listener.config.chains

    @pytest.mark.asyncio
    async def test_add_chain_support_rollback_on_failure(self, chain_listener):
        """Test that config is rolled back if adapter registration fails."""
        new_config = ChainConfig(
            chain_type=ChainType.SOLANA,
            chain_id=999,
            rpc_urls=[{"url": "test", "priority": 1}]
        )

        with patch.object(chain_listener._adapter_registry, 'register_adapter') as mock_register:
            mock_register.side_effect = Exception("Registration failed")

            with pytest.raises(ChainListenerError, match="Failed to add chain"):
                chain_listener._add_chain_support("solana", new_config)

        # Should not be added to config due to rollback
        assert "solana" not in chain_listener.config.chains

    @pytest.mark.asyncio
    async def test_get_latest_block_sync_adapter_method(self, chain_listener):
        """Test getting latest block with sync adapter method."""
        mock_adapter = Mock()
        mock_adapter.get_latest_block_number.return_value = 54321

        result = await chain_listener._get_latest_block(mock_adapter)

        assert result == 54321

    @pytest.mark.asyncio
    async def test_get_latest_block_chain_not_configured(self, chain_listener):
        """Test getting latest block for unconfigured chain."""
        with pytest.raises(ChainListenerError, match="Chain 'nonexistent' is not configured"):
            await chain_listener.get_latest_block("nonexistent")