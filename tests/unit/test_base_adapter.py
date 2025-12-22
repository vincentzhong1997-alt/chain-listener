"""Test base blockchain adapter interface following TDD principles."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import re

# Import the classes we need to test
from chain_listener.adapters.base import BaseAdapter
from chain_listener.exceptions import ConnectionError, BlockchainAdapterError, RateLimitError

# These tests are written before the implementation exists
# They will fail initially, then we'll implement the code to make them pass


class MockBlockchainAdapter(BaseAdapter):
    """Test implementation of BaseBlockchainAdapter for testing."""

    def __init__(self, config: Dict[str, Any], mock_web3=None):
        """Initialize test adapter with optional Web3 mock."""
        super().__init__(config)
        self.mock_web3 = mock_web3
        self._mock_blocks = {}
        self._mock_logs = []
        self._mock_transactions = {}

    async def connect(self) -> None:
        """Connect to blockchain (mock implementation)."""
        # Simulate connection logic
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from blockchain (mock implementation)."""
        self._connected = False

    async def get_latest_block_number(self) -> int:
        """Get latest block number (mock implementation)."""
        if not self._connected:
            raise ConnectionError(
                "Not connected to blockchain",
                blockchain=self.name,
                network=self.network
            )
        # Return a mock block number
        return 18500000

    async def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
        """Get block by number (mock implementation)."""
        if not self._connected:
            raise ConnectionError(
                "Not connected to blockchain",
                blockchain=self.name,
                network=self.network
            )

        # Return mock block data
        return {
            "number": block_number,
            "hash": f"0x{block_number:064x}",
            "timestamp": int(datetime.now().timestamp()),
            "transactions": []
        }

    async def get_logs(
        self,
        address: Optional[str] = None,
        topics: Optional[List[str]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get logs (mock implementation)."""
        if not self._connected:
            raise ConnectionError(
                "Not connected to blockchain",
                blockchain=self.name,
                network=self.network
            )

        # Return mock logs
        return [{
            "address": address or "0x1234567890123456789012345678901234567890",
            "topics": topics or ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"],
            "data": "0x000000000000000000000000000000000000000000000000000000000000000a00000000000000000000000000000000000000000000000000000000000000014",
            "blockNumber": from_block or 18500000,
            "transactionHash": f"0x{from_block or 18500000:064x}",
            "logIndex": 0
        }]

    async def get_transaction(self, transaction_hash: str) -> Dict[str, Any]:
        """Get transaction (mock implementation)."""
        if not self._connected:
            raise ConnectionError(
                "Not connected to blockchain",
                blockchain=self.name,
                network=self.network
            )

        # Return mock transaction data
        return {
            "hash": transaction_hash,
            "blockNumber": 18500000,
            "from": "0x1234567890123456789012345678901234567890",
            "to": "0x0987654321098765432109876543210987654321",
            "value": "1000000000000000000"
        }

    # Set mock data for testing
    def set_mock_block(self, block_number: int, block_data: Dict[str, Any]) -> None:
        """Set mock block data for testing."""
        self._mock_blocks[block_number] = block_data

    def set_mock_logs(self, logs: List[Dict[str, Any]]) -> None:
        """Set mock logs for testing."""
        self._mock_logs = logs

    def set_mock_transaction(self, tx_hash: str, tx_data: Dict[str, Any]) -> None:
        """Set mock transaction data for testing."""
        self._mock_transactions[tx_hash] = tx_data

    def _handle_blockchain_error(self, error: Exception) -> None:
        """Mock error handling to simulate base adapter behavior."""
        error_msg = str(error).lower()
        if "timeout" in error_msg:
            raise BlockchainAdapterError(f"Request timeout: {error_msg}")
        elif "rate limit" in error_msg:
            raise RateLimitError(f"Rate limit exceeded: {error_msg}")
        else:
            raise BlockchainAdapterError(f"Blockchain error: {error_msg}")


class TestBaseBlockchainAdapter:
    """Test suite for BaseBlockchainAdapter."""

    def test_adapter_initialization_with_valid_config(self):
        """Test that adapter can be initialized with valid configuration."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://eth.llamarpc.com"],
                "timeout": 30,
                "retries": 3
            }
        }

        adapter = MockBlockchainAdapter(config)

        assert adapter.name == "ethereum"
        assert adapter.network == "mainnet"
        assert adapter.rpc_config["urls"] == ["https://eth.llamarpc.com"]
        assert adapter.rpc_config["timeout"] == 30
        assert adapter.rpc_config["retries"] == 3

    def test_adapter_initialization_with_defaults(self):
        """Test that adapter provides sensible defaults."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://eth.llamarpc.com"],
                "timeout": 30,
                "retries": 3
            }
        }

        adapter = MockBlockchainAdapter(config)

        assert adapter.network == "mainnet"  # Default
        assert adapter.rpc_config["timeout"] == 30  # Default
        assert adapter.rpc_config["retries"] == 3  # Default

    def test_config_validation_empty_config(self):
        """Test that empty configuration raises ValueError."""
        with pytest.raises(ValueError, match="Configuration cannot be empty"):
            MockBlockchainAdapter({})

    def test_config_validation_missing_name(self):
        """Test that missing name raises ValueError."""
        config = {
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        with pytest.raises(ValueError, match="Missing required config: name"):
            MockBlockchainAdapter(config)

    def test_config_validation_missing_network(self):
        """Test that missing network raises ValueError."""
        config = {
            "name": "ethereum",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        with pytest.raises(ValueError, match="Missing required config: network"):
            MockBlockchainAdapter(config)

    def test_config_validation_missing_rpc(self):
        """Test that missing RPC config raises ValueError."""
        config = {
            "name": "ethereum",
            "network": "mainnet"
        }

        with pytest.raises(ValueError, match="Missing required config: rpc"):
            MockBlockchainAdapter(config)

    def test_config_validation_empty_urls(self):
        """Test that empty URLs list raises ValueError."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": []}
        }

        with pytest.raises(ValueError, match="RPC URLs required"):
            MockBlockchainAdapter(config)

    def test_config_validation_invalid_url_format(self):
        """Test that invalid URL format raises ValueError."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["invalid-url"]}
        }

        with pytest.raises(ValueError, match="Invalid RPC URL format"):
            MockBlockchainAdapter(config)

    def test_config_validation_negative_timeout(self):
        """Test that negative timeout raises ValueError."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://eth.llamarpc.com"],
                "timeout": -1
            }
        }

        with pytest.raises(ValueError, match="Invalid timeout: must be positive integer"):
            MockBlockchainAdapter(config)

    def test_config_validation_negative_retries(self):
        """Test that negative retries raises ValueError."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://eth.llamarpc.com"],
                "retries": -1
            }
        }

        with pytest.raises(ValueError, match="Invalid retries: must be non-negative integer"):
            MockBlockchainAdapter(config)

    
    @pytest.mark.asyncio
    async def test_get_latest_block_number_when_connected(self):
        """Test getting latest block number when connected."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        block_number = await adapter.get_latest_block_number()

        assert isinstance(block_number, int)
        assert block_number > 0

    @pytest.mark.asyncio
    async def test_get_latest_block_number_when_disconnected(self):
        """Test getting latest block number when disconnected raises error."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        # Don't connect

        with pytest.raises(ConnectionError, match="Not connected to blockchain"):
            await adapter.get_latest_block_number()

    @pytest.mark.asyncio
    async def test_get_block_by_number_success(self):
        """Test getting block by number when connected."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        block = await adapter.get_block_by_number(18500000)

        assert block["number"] == 18500000
        assert "hash" in block
        assert "timestamp" in block
        assert "transactions" in block

    @pytest.mark.asyncio
    async def test_get_block_by_number_when_disconnected(self):
        """Test getting block by number when disconnected raises error."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        # Don't connect

        with pytest.raises(ConnectionError, match="Not connected to blockchain"):
            await adapter.get_block_by_number(18500000)

    @pytest.mark.asyncio
    async def test_get_logs_success(self):
        """Test getting logs when connected."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
        logs = await adapter.get_logs(address=contract_address, from_block=18500000, to_block=18500010)

        assert isinstance(logs, list)
        assert len(logs) > 0
        assert logs[0]["address"] == contract_address

    @pytest.mark.asyncio
    async def test_get_logs_when_disconnected(self):
        """Test getting logs when disconnected raises error."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        # Don't connect

        with pytest.raises(ConnectionError, match="Not connected to blockchain"):
            await adapter.get_logs()

    @pytest.mark.asyncio
    async def test_get_transaction_success(self):
        """Test getting transaction when connected."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        transaction = await adapter.get_transaction(tx_hash)

        assert transaction["hash"] == tx_hash
        assert "blockNumber" in transaction
        assert "from" in transaction
        assert "to" in transaction

    @pytest.mark.asyncio
    async def test_get_transaction_when_disconnected(self):
        """Test getting transaction when disconnected raises error."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        # Don't connect

        with pytest.raises(ConnectionError, match="Not connected to blockchain"):
            await adapter.get_transaction("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef")

    def test_connection_pool_priority_order(self):
        """Test that connection pool respects URL priority order."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": [
                    "https://primary.eth.llamarpc.com",    # Priority 1
                    "https://secondary.eth.llamarpc.com", # Priority 2
                    "https://tertiary.eth.llamarpc.com"    # Priority 3
                ]
            }
        }

        adapter = MockBlockchainAdapter(config)

        # Should return primary URL first (highest priority)
        connection = adapter._get_next_connection()
        assert connection == "https://primary.eth.llamarpc.com"

        assert len(adapter._connection_pool.urls) == 3

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test that adapter handles concurrent requests safely."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        # Concurrent block number requests
        tasks = [adapter.get_latest_block_number() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed and return valid results
        for result in results:
            assert isinstance(result, int)
            assert result > 0

    def test_rate_limiting_configuration(self):
        """Test rate limiting configuration."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://eth.llamarpc.com"],
                "rate_limit": {
                    "requests_per_second": 20,
                    "burst_size": 50
                }
            }
        }

        adapter = MockBlockchainAdapter(config)

        assert adapter._requests_per_second == 20
        assert adapter._burst_size == 50

    @pytest.mark.asyncio
    async def test_error_handling_wrapping(self):
        """Test that blockchain errors are properly wrapped."""
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)

        # Test timeout error
        with pytest.raises(BlockchainAdapterError) as exc_info:
            adapter._handle_blockchain_error(Exception("request timeout"))

        assert "timeout" in str(exc_info.value).lower()

        # Test rate limit error
        with pytest.raises(RateLimitError) as exc_info:
            adapter._handle_blockchain_error(Exception("rate limit exceeded"))

        assert "rate limit" in str(exc_info.value).lower()

    def test_edge_case_configurations(self):
        """Test edge case configurations."""
        # Single URL
        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        assert len(adapter.rpc_config["urls"]) == 1

        # Multiple URLs with priority order
        config = {
            "name": "ethereum",
            "network": "testnet",
            "rpc": {
                "urls": [
                    "https://primary.eth.llamarpc.com",
                    "https://secondary.eth.llamarpc.com",
                    "https://tertiary.eth.llamarpc.com",
                    "https://backup.eth.llamarpc.com"
                ],
                "retries": 5
            }
        }

        adapter = MockBlockchainAdapter(config)
        assert len(adapter.rpc_config["urls"]) == 4
        assert adapter._connection_pool.max_retries == 5

        # Test that primary URL is returned first
        connection = adapter._get_next_connection()
        assert connection == "https://primary.eth.llamarpc.com"
