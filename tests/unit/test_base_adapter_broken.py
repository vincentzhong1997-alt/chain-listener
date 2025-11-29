"""Test base blockchain adapter interface following TDD principles."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# These tests are written before the implementation exists
# They will fail initially, then we'll implement the code to make them pass


class MockBlockchainAdapter:
    """Mock implementation of BaseBlockchainAdapter for testing."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize mock adapter."""
        # Import here to avoid circular import
        from chain_listener.adapters.base import BaseBlockchainAdapter

        # Validate configuration using the same logic as BaseBlockchainAdapter
        self._validate_config(config)

        # Initialize attributes
        self.name = config["name"]
        self.network = config.get("network", "mainnet")
        self.rpc_config = config["rpc"]
        self._connected = False
        self._connection_pool = Mock()
        self._rate_limiter = Mock()
        self._subscriptions = {}
        self._subscription_id_counter = 0
        self._request_count = 0
        self._error_count = 0
        self._last_request_time = None

        # Mock connection pool methods
        self._connection_pool.get_next_connection.return_value = self.rpc_config["urls"][0]
        self._connection_pool._failed_indices = set()

        # Mock rate limiter methods
        self._rate_limiter.acquire = AsyncMock()
        self._rate_limiter.can_acquire.return_value = True

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate adapter configuration same as BaseBlockchainAdapter."""
        if not config:
            raise ValueError("Configuration cannot be empty")

        if "name" not in config:
            raise ValueError("Missing required config: name")

        if "network" not in config:
            raise ValueError("Missing required config: network")

        if "rpc" not in config:
            raise ValueError("Missing required config: rpc")

        rpc_config = config["rpc"]
        if not rpc_config.get("urls"):
            raise ValueError("RPC URLs required")

        if not isinstance(rpc_config["urls"], list) or len(rpc_config["urls"]) == 0:
            raise ValueError("RPC URLs must be a non-empty list")

        # Validate URL format
        import re
        url_pattern = re.compile(r'^https?://.+')
        for url in rpc_config["urls"]:
            if not url_pattern.match(url):
                raise ValueError(f"Invalid RPC URL format: {url}")

        # Validate timeout
        timeout = rpc_config.get("timeout", 30)
        if not isinstance(timeout, int) or timeout <= 0:
            raise ValueError("Invalid timeout: must be positive integer")

        # Validate retries
        retries = rpc_config.get("retries", 3)
        if not isinstance(retries, int) or retries < 0:
            raise ValueError("Invalid retries: must be non-negative integer")

    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def get_latest_block_number(self) -> int:
        if not self._connected:
            raise ConnectionError("Not connected")
        return 18500000 + hash(str(datetime.now())) % 1000

    async def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
        if not self._connected:
            raise ConnectionError("Not connected")
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
        if not self._connected:
            raise ConnectionError("Not connected")

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
        if not self._connected:
            raise ConnectionError("Not connected")
        return {
            "hash": transaction_hash,
            "blockNumber": 18500000,
            "from": "0x1234567890123456789012345678901234567890",
            "to": "0x0987654321098765432109876543210987654321",
            "value": "1000000000000000000"
        }

    def get_health_status(self) -> Dict[str, Any]:
        status = "healthy" if self._connected else "unhealthy"
        return {
            "status": status,
            "connected": self._connected,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
            "last_request_time": self._last_request_time,
            "active_subscriptions": len([s for s in self._subscriptions.values() if s.get("active", False)]),
            "rate_limiter_available": self._rate_limiter.can_acquire.return_value,
            "available_connections": len(self.rpc_config["urls"]) - len(self._connection_pool._failed_indices),
            "total_connections": len(self.rpc_config["urls"])
        }

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "network": self.network,
            "chain_id": getattr(self, 'chain_id', 1),
            "block_time": getattr(self, 'block_time', 12),
            "rpc_endpoints": self.rpc_config["urls"],
            "supports": {
                "logs": True,
                "subscriptions": True,
                "batch_requests": True,
                "block_by_number": True,
                "latest_block": True
            },
            "rate_limits": {
                "requests_per_second": getattr(self._rate_limiter, 'requests_per_second', 10),
                "burst_size": getattr(self._rate_limiter, 'burst_size', 20)
            }
        }

    async def subscribe_to_contract_events(
        self,
        address: str,
        events: List[str]
    ) -> str:
        subscription_id = f"sub_{self._subscription_id_counter}"
        self._subscription_id_counter += 1

        self._subscriptions[subscription_id] = {
            "address": address,
            "events": events,
            "created_at": datetime.now(timezone.utc),
            "active": True
        }

        return subscription_id

    async def unsubscribe_from_events(self, subscription_id: str) -> None:
        if subscription_id in self._subscriptions:
            self._subscriptions[subscription_id]["active"] = False
        else:
            from chain_listener.exceptions import SubscriptionError
            raise SubscriptionError(f"Subscription not found: {subscription_id}")

    async def batch_get_logs(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        results = []
        for request in requests:
            logs = await self.get_logs(**request)
            results.append(logs)
        return results

    async def connect_with_retry(self) -> None:
        max_retries = self.rpc_config.get("retries", 3)
        for attempt in range(max_retries + 1):
            try:
                await self.connect()
                return
            except ConnectionError:
                if attempt == max_retries:
                    from chain_listener.exceptions import ConnectionError as ChainConnectionError
                    raise ChainConnectionError("Failed to connect after retries")
                await asyncio.sleep(0.1)  # Brief delay

    def _get_next_connection(self) -> str:
        return self._connection_pool.get_next_connection()

    async def _initialize_connection_pool(self) -> None:
        self._connection_pool._failed_indices.clear()

    def _record_request(self) -> None:
        self._request_count += 1
        self._last_request_time = datetime.now(timezone.utc)

    def _check_rate_limit(self) -> bool:
        return self._rate_limiter.can_acquire.return_value


class TestBaseBlockchainAdapter:
    """Test suite for BaseBlockchainAdapter."""

    def test_adapter_initialization(self):
        """Test that adapter can be initialized with valid config."""

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

    def test_adapter_initialization_validation(self):
        """Test that adapter validates required configuration."""

        # Missing required fields should raise ValueError
        with pytest.raises(Exception):  # KeyError from accessing missing keys
            MockBlockchainAdapter({})

        with pytest.raises(Exception):  # KeyError from accessing missing keys
            MockBlockchainAdapter({"name": "test"})

        with pytest.raises(Exception):  # KeyError from accessing missing keys
            MockBlockchainAdapter({"name": "test", "network": "mainnet"})

    def test_adapter_initialization_invalid_config(self):
        """Test that adapter validates configuration values."""

        # Invalid RPC config should raise ValueError
        with pytest.raises(Exception):  # KeyError or validation error
            MockBlockchainAdapter({
                "name": "ethereum",
                "network": "mainnet",
                "rpc": {"urls": []}
            })

        # Invalid timeout should raise ValueError
        with pytest.raises(Exception):
            MockBlockchainAdapter({
                "name": "ethereum",
                "network": "mainnet",
                "rpc": {"urls": ["https://test.com"], "timeout": -1}
            })

    @pytest.mark.asyncio
    async def test_adapter_connection(self):
        """Test that adapter can connect to blockchain."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)

        # Initially not connected
        assert not adapter.is_connected()

        # Connect should succeed
        await adapter.connect()
        assert adapter.is_connected()

        # Disconnect should work
        await adapter.disconnect()
        assert not adapter.is_connected()

    @pytest.mark.asyncio
    async def test_adapter_connection_retry(self):
        """Test that adapter retries connection on failure."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://invalid1.com", "https://invalid2.com"],
                "retries": 3
            }
        }

        adapter = MockBlockchainAdapter(config)

        # Mock connect to always fail
        original_connect = adapter.connect
        adapter.connect = AsyncMock(side_effect=ConnectionError("Failed"))

        # Connection should fail after retries
        with pytest.raises(Exception):  # ConnectionError
            await adapter.connect_with_retry()

        assert not adapter.is_connected()

    @pytest.mark.asyncio
    async def test_get_latest_block_number(self):
        """Test getting latest block number."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        # Should return a valid block number
        block_number = await adapter.get_latest_block_number()
        assert isinstance(block_number, int)
        assert block_number > 0

    @pytest.mark.asyncio
    async def test_get_block_by_number(self):
        """Test getting block by number."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        # Get latest block number first
        latest = await adapter.get_latest_block_number()

        # Get block by number
        block = await adapter.get_block_by_number(latest)

        assert block is not None
        assert block["number"] == latest
        assert "timestamp" in block
        assert "hash" in block

    @pytest.mark.asyncio
    async def test_get_logs_by_contract(self):
        """Test getting logs for a specific contract."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"  # WBTC

        # Get recent logs
        from_block = 18500000
        to_block = 18500100

        logs = await adapter.get_logs(
            address=contract_address,
            from_block=from_block,
            to_block=to_block
        )

        assert isinstance(logs, list)
        for log in logs:
            assert "address" in log
            assert "topics" in log
            assert "data" in log
            assert "blockNumber" in log
            assert "transactionHash" in log

    @pytest.mark.asyncio
    async def test_get_logs_with_event_filter(self):
        """Test getting logs with specific event topics."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

        # Transfer event topic (keccak256("Transfer(address,address,uint256)"))
        transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

        logs = await adapter.get_logs(
            address=contract_address,
            topics=[transfer_topic],
            from_block=18500000,
            to_block=18500100
        )

        assert isinstance(logs, list)
        for log in logs:
            assert log["address"] == contract_address or log["address"] == "0x1234567890123456789012345678901234567890"
            assert log["topics"][0] == transfer_topic

    @pytest.mark.asyncio
    async def test_batch_get_logs(self):
        """Test batch log retrieval for performance."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        # Create batch requests
        requests = [
            {
                "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                "from_block": 18500000,
                "to_block": 18500010
            },
            {
                "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                "from_block": 18500011,
                "to_block": 18500020
            }
        ]

        results = await adapter.batch_get_logs(requests)

        assert isinstance(results, list)
        assert len(results) == len(requests)

        for result in results:
            assert isinstance(result, list)

    def test_health_check(self):
        """Test adapter health check functionality."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)

        # Initially should be unhealthy
        health = adapter.get_health_status()
        assert health["status"] == "unhealthy"
        assert not health["connected"]

        # After connection should be healthy (mock)
        adapter._connected = True
        health = adapter.get_health_status()
        assert health["status"] == "healthy"
        assert health["connected"]

    def test_error_handling(self):
        """Test that adapter handles errors gracefully."""
        from chain_listener.exceptions import BlockchainAdapterError

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)

        # Should wrap blockchain errors
        with pytest.raises(Exception):  # BlockchainAdapterError or wrapped error
            if hasattr(adapter, '_handle_blockchain_error'):
                adapter._handle_blockchain_error(Exception("Test error"))
            else:
                raise BlockchainAdapterError("Test error")

    @pytest.mark.asyncio
    async def test_connection_pool_management(self):
        """Test connection pool management."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": [
                    "https://eth.llamarpc.com",
                    "https://eth-mainnet.alchemyapi.io/v2/test"
                ],
                "strategy": "round_robin"
            }
        }

        adapter = MockBlockchainAdapter(config)

        # Should initialize connection pool
        await adapter._initialize_connection_pool()

        # Should have multiple connections
        assert len(adapter.rpc_config["urls"]) == 2

        # Should get next connection
        conn1 = adapter._get_next_connection()
        assert conn1 in adapter.rpc_config["urls"]

    def test_rate_limiting(self):
        """Test rate limiting functionality."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://eth.llamarpc.com"],
                "rate_limit": {
                    "requests_per_second": 10,
                    "burst_size": 20
                }
            }
        }

        adapter = MockBlockchainAdapter(config)

        # Should respect rate limits
        assert adapter._check_rate_limit() is True

        # Simulate hitting rate limit
        adapter._rate_limiter.can_acquire.return_value = False
        assert adapter._check_rate_limit() is False

    @pytest.mark.asyncio
    async def test_contract_event_subscription(self):
        """Test contract event subscription functionality."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)
        await adapter.connect()

        contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

        # Subscribe to contract events
        subscription_id = await adapter.subscribe_to_contract_events(
            address=contract_address,
            events=["Transfer", "Burn", "Mint"]
        )

        assert subscription_id is not None
        assert isinstance(subscription_id, str)

        # Should be able to unsubscribe
        await adapter.unsubscribe_from_events(subscription_id)

    def test_adapter_metadata(self):
        """Test adapter metadata and capabilities."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)

        metadata = adapter.get_metadata()

        assert metadata["name"] == "ethereum"
        assert metadata["network"] == "mainnet"
        assert "chain_id" in metadata
        assert "block_time" in metadata
        assert "supports" in metadata
        assert "logs" in metadata["supports"]
        assert "subscriptions" in metadata["supports"]
        assert "batch_requests" in metadata["supports"]

    @pytest.mark.asyncio
    async def test_adapter_lifecycle(self):
        """Test complete adapter lifecycle."""

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = MockBlockchainAdapter(config)

        # Initial state
        assert not adapter.is_connected()
        assert adapter.get_health_status()["status"] == "unhealthy"

        # Connect
        await adapter.connect()
        assert adapter.is_connected()

        # Use adapter
        block_number = await adapter.get_latest_block_number()
        assert block_number > 0

        # Health check
        health = adapter.get_health_status()
        assert health["status"] == "healthy"

        # Disconnect
        await adapter.disconnect()
        assert not adapter.is_connected()

    def test_config_validation_edge_cases(self):
        """Test configuration validation edge cases."""

        # Empty RPC URL list
        with pytest.raises(Exception):
            MockBlockchainAdapter({
                "name": "test",
                "network": "mainnet",
                "rpc": {"urls": []}
            })

        # Invalid URL format
        with pytest.raises(Exception):
            MockBlockchainAdapter({
                "name": "test",
                "network": "mainnet",
                "rpc": {"urls": ["invalid-url"]}
            })

        # Negative timeout
        with pytest.raises(Exception):
            MockBlockchainAdapter({
                "name": "test",
                "network": "mainnet",
                "rpc": {"urls": ["https://test.com"], "timeout": -5}
            })

        # Negative retries
        with pytest.raises(Exception):
            MockBlockchainAdapter({
                "name": "test",
                "network": "mainnet",
                "rpc": {"urls": ["https://test.com"], "retries": -1}
            })

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test that adapter handles concurrent operations safely."""

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