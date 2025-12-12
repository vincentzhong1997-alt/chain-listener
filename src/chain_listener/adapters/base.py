"""Base blockchain adapter interface and common functionality.

This module defines the abstract interface that all blockchain adapters must
implement, along with common functionality for connection management,
rate limiting, error handling, and batch operations.
"""

import asyncio
import re
import time
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator, Union
from collections import deque
import random

from chain_listener.exceptions import (
    BlockchainAdapterError,
    ConnectionError as ChainConnectionError,
    RateLimitError,
    SubscriptionError,
    BlockNotFoundError,
    TransactionError,
    HealthCheckError,
    RetryExhaustedError
)


class RateLimiter:
    """Rate limiter for API requests.

    Implements token bucket algorithm for rate limiting with configurable
    requests per second and burst capacity.
    """

    def __init__(self, requests_per_second: int = 10, burst_size: int = 20):
        """Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second
            burst_size: Maximum burst capacity
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, blocking if rate limit is exceeded."""
        async with self._lock:
            now = time.time()
            time_passed = now - self.last_refill
            self.tokens = min(self.burst_size, self.tokens + time_passed * self.requests_per_second)
            self.last_refill = now

            if self.tokens < 1:
                # Calculate wait time needed
                wait_time = (1 - self.tokens) / self.requests_per_second
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

    def can_acquire(self) -> bool:
        """Check if a token can be acquired without waiting."""
        now = time.time()
        time_passed = now - self.last_refill
        current_tokens = min(self.burst_size, self.tokens + time_passed * self.requests_per_second)
        return current_tokens >= 1


class ConnectionPool:
    """Manages multiple RPC endpoints with load balancing strategies."""

    def __init__(
        self,
        urls: List[str],
        strategy: str = "round_robin",
        timeout: int = 30,
        retries: int = 3
    ):
        """Initialize connection pool.

        Args:
            urls: List of RPC endpoint URLs
            strategy: Load balancing strategy ('round_robin', 'random', 'failover')
            timeout: Request timeout in seconds
            retries: Number of retry attempts
        """
        self.urls = urls
        self.strategy = strategy
        self.timeout = timeout
        self.retries = retries
        self._current_index = 0
        self._failed_indices = set()

    def get_next_connection(self) -> str:
        """Get next available connection based on strategy."""
        available_indices = [i for i in range(len(self.urls)) if i not in self._failed_indices]

        if not available_indices:
            # All failed, reset and try again
            self._failed_indices.clear()
            available_indices = list(range(len(self.urls)))

        if self.strategy == "round_robin":
            index = available_indices[self._current_index % len(available_indices)]
            self._current_index += 1
        elif self.strategy == "random":
            index = random.choice(available_indices)
        elif self.strategy == "failover":
            index = available_indices[0]  # Always use first available
        else:
            index = available_indices[0]

        return self.urls[index]

    def mark_failed(self, url: str) -> None:
        """Mark a connection as failed."""
        try:
            index = self.urls.index(url)
            self._failed_indices.add(index)
        except ValueError:
            pass

    def mark_success(self, url: str) -> None:
        """Mark a connection as successful (clear failure state)."""
        try:
            index = self.urls.index(url)
            self._failed_indices.discard(index)
        except ValueError:
            pass


class PriorityConnectionPool:
    """Manages RPC endpoints with priority and intelligent failover."""

    def __init__(self, endpoints_with_priority: List[tuple], max_retries: int = 3):
        """
        Initialize priority connection pool.

        Args:
            endpoints_with_priority: List of (url, priority) tuples
            max_retries: Maximum number of retries before marking endpoint as failed
        """
        # 按优先级排序（数字越小优先级越高）
        self.endpoints = sorted(endpoints_with_priority, key=lambda x: x[1])
        self.max_retries = max_retries

        # 端点统计信息
        self.endpoint_stats = {
            url: {
                'consecutive_failures': 0,      # 连续失败次数
                'total_failures': 0,           # 总失败次数
                'last_failure_time': None,     # 最后失败时间
                'marked_failed': False,        # 是否标记为失败
                'cooling_until': None,         # 冷却截止时间
                'success_count': 0             # 成功次数
            }
            for url, _ in self.endpoints
        }

    def get_best_endpoint(self) -> str:
        """获取当前可用的最佳端点"""
        now = time.time()

        for url, priority in self.endpoints:
            stats = self.endpoint_stats[url]

            # 检查是否在冷却期
            if stats['cooling_until'] and now < stats['cooling_until']:
                continue

            # 如果已标记为失败，跳过
            if stats['marked_failed']:
                continue

            # 这个端点可用
            return url

        # 所有端点都不可用，返回最高优先级的（强制使用）
        return self.endpoints[0][0]

    def mark_success(self, url: str) -> None:
        """标记请求成功，重置失败计数"""
        if url not in self.endpoint_stats:
            return

        stats = self.endpoint_stats[url]
        stats['consecutive_failures'] = 0
        stats['success_count'] += 1

        # 从失败状态恢复
        if stats['marked_failed']:
            stats['marked_failed'] = False
            stats['cooling_until'] = None
            logger = logging.getLogger(__name__)
            logger.info(f"RPC endpoint {url} recovered from failed state")

    def mark_failure(self, url: str) -> None:
        """标记请求失败"""
        if url not in self.endpoint_stats:
            return

        stats = self.endpoint_stats[url]
        stats['consecutive_failures'] += 1
        stats['total_failures'] += 1
        stats['last_failure_time'] = time.time()

        # 只有连续失败次数达到用户配置的重试次数才标记为失败
        if stats['consecutive_failures'] >= self.max_retries:
            stats['marked_failed'] = True
            # 指数退避冷却时间（最大5分钟）
            failure_excess = stats['consecutive_failures'] - self.max_retries
            cooling_time = min(300, 30 * (2 ** failure_excess))
            stats['cooling_until'] = time.time() + cooling_time

            logger = logging.getLogger(__name__)
            logger.warning(
                f"RPC endpoint {url} marked as failed after {self.max_retries} retries. "
                f"Cooling for {cooling_time} seconds"
            )

    def get_health_status(self) -> dict:
        """获取所有端点的健康状态"""
        return {
            url: {
                'priority': priority,
                'consecutive_failures': stats['consecutive_failures'],
                'total_failures': stats['total_failures'],
                'success_count': stats['success_count'],
                'marked_failed': stats['marked_failed'],
                'cooling_until': stats['cooling_until'],
                'success_rate': stats['success_count'] / max(1, stats['success_count'] + stats['total_failures'])
            }
            for (url, priority), stats in zip(self.endpoints, self.endpoint_stats.values())
        }


class BaseAdapter(ABC):
    """Abstract base class for blockchain adapters.

    Provides common functionality for connection management, rate limiting,
    error handling, and batch operations while defining the interface that
    specific blockchain adapters must implement.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize adapter with configuration.

        Args:
            config: Adapter configuration dictionary

        Raises:
            ValueError: If configuration is invalid
            ConfigurationError: If required configuration is missing
        """
        self._validate_config(config)

        self.name = config["name"]
        self.network = config.get("network", "mainnet")
        self.rpc_config = config["rpc"]

        # Connection management
        self._connection_pool = ConnectionPool(
            urls=self.rpc_config["urls"],
            strategy=self.rpc_config.get("strategy", "round_robin"),
            timeout=self.rpc_config.get("timeout", 30),
            retries=self.rpc_config.get("retries", 3)
        )

        self._connection_lock = asyncio.Lock()

        # Rate limiting
        rate_limit_config = self.rpc_config.get("rate_limit", {})
        self._rate_limiter = RateLimiter(
            requests_per_second=rate_limit_config.get("requests_per_second", 10),
            burst_size=rate_limit_config.get("burst_size", 20)
        )

        # Subscription management
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._subscription_id_counter = 0

        # Request tracking for debugging
        self._request_count = 0
        self._error_count = 0
        self._last_request_time = None

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate adapter configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
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
        """Check if adapter is connected to blockchain.

        Returns:
            True if connected, False otherwise
        """
        # Default implementation - subclasses should override
        return True

    @abstractmethod
    async def connect(self) -> None:
        """Connect to blockchain network.

        Raises:
            ConnectionError: If connection fails
            RetryExhaustedError: If all retry attempts fail
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from blockchain network."""
        pass

    async def connect_with_retry(self) -> None:
        """Connect with automatic retry logic.

        Raises:
            ConnectionError: If connection fails after all retries
        """
        last_error = None
        max_retries = self.rpc_config.get("retries", 3)

        for attempt in range(max_retries + 1):
            try:
                await self.connect()
                return
            except (ChainConnectionError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        raise RetryExhaustedError(
            f"Failed to connect after {max_retries + 1} attempts",
            max_retries=max_retries,
            last_error=last_error
        )

    @abstractmethod
    async def get_latest_block_number(self) -> int:
        """Get the latest block number.

        Returns:
            Latest block number

        Raises:
            BlockchainAdapterError: If request fails
        """
        pass

    @abstractmethod
    async def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
        """Get block information by number.

        Args:
            block_number: Block number to retrieve

        Returns:
            Block information dictionary

        Raises:
            BlockNotFoundError: If block is not found
            BlockchainAdapterError: If request fails
        """
        pass

    @abstractmethod
    async def get_logs(
        self,
        address: Optional[Union[str, List[str]]] = None,
        topics: Optional[List[str]] = None,
        from_block: Optional[Union[int, str]] = None,
        to_block: Optional[Union[int, str]] = None
    ) -> List[Dict[str, Any]]:
        """Get logs matching criteria.

        Args:
            address: Contract address to filter by (single address or list of addresses)
            topics: Event topics to filter by
            from_block: Starting block number or 'latest'
            to_block: Ending block number or 'latest'

        Returns:
            List of log entries

        Raises:
            BlockchainAdapterError: If request fails
        """
        pass

    async def batch_get_logs(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Get logs for multiple requests in batch.

        Args:
            requests: List of log request dictionaries

        Returns:
            List of log lists, one for each request

        Raises:
            BlockchainAdapterError: If any request fails
        """
        # Default implementation executes requests concurrently
        tasks = []
        for request in requests:
            task = self.get_logs(**request)
            tasks.append(task)

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to error responses
            final_results = []
            for result in results:
                if isinstance(result, Exception):
                    final_results.append([])  # Return empty list on error
                else:
                    final_results.append(result)

            return final_results
        except Exception as e:
            raise BlockchainAdapterError(f"Batch log retrieval failed: {e}")

    async def subscribe_to_contract_events(
        self,
        address: str,
        events: List[str]
    ) -> str:
        """Subscribe to events from a specific contract.

        Args:
            address: Contract address to subscribe to
            events: List of event names to subscribe to

        Returns:
            Subscription ID for managing the subscription

        Raises:
            SubscriptionError: If subscription fails
        """
        subscription_id = f"sub_{self._subscription_id_counter}"
        self._subscription_id_counter += 1

        self._subscriptions[subscription_id] = {
            "address": address,
            "events": events,
            "created_at": datetime.now(timezone.utc),
            "active": True
        }

        # Default implementation - subclasses should override for real subscriptions
        return subscription_id

    async def unsubscribe_from_events(self, subscription_id: str) -> None:
        """Unsubscribe from events.

        Args:
            subscription_id: Subscription ID to cancel

        Raises:
            SubscriptionError: If unsubscription fails
        """
        if subscription_id in self._subscriptions:
            self._subscriptions[subscription_id]["active"] = False
        else:
            raise SubscriptionError(f"Subscription not found: {subscription_id}")

    def get_health_status(self) -> Dict[str, Any]:
        """Get adapter health status.

        Returns:
            Health status dictionary with status, metrics, and checks
        """
        status = "healthy" if self._connected else "unhealthy"

        return {
            "status": status,
            "connected": self._connected,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
            "last_request_time": self._last_request_time,
            "active_subscriptions": len([s for s in self._subscriptions.values() if s["active"]]),
            "rate_limiter_available": self._rate_limiter.can_acquire(),
            "available_connections": len([i for i in range(len(self.rpc_config["urls"]))
                                        if i not in self._connection_pool._failed_indices]),
            "total_connections": len(self.rpc_config["urls"])
        }

    def get_metadata(self) -> Dict[str, Any]:
        """Get adapter metadata and capabilities.

        Returns:
            Metadata dictionary with blockchain info and supported features
        """
        return {
            "name": self.name,
            "network": self.network,
            "chain_id": getattr(self, 'chain_id', None),
            "block_time": getattr(self, 'block_time', None),
            "rpc_endpoints": self.rpc_config["urls"],
            "supports": {
                "logs": True,
                "subscriptions": True,
                "batch_requests": True,
                "block_by_number": True,
                "latest_block": True
            },
            "rate_limits": {
                "requests_per_second": self._rate_limiter.requests_per_second,
                "burst_size": self._rate_limiter.burst_size
            }
        }

    def _handle_blockchain_error(self, error: Exception) -> None:
        """Handle blockchain-specific errors and convert to SDK exceptions.

        Args:
            error: Original error from blockchain interaction

        Raises:
            BlockchainAdapterError: Converted SDK exception
        """
        self._error_count += 1

        if isinstance(error, BlockchainAdapterError):
            raise error

        # Convert common error types
        error_msg = str(error)
        if "timeout" in error_msg.lower():
            raise ChainConnectionError(
                f"Blockchain request timeout: {error_msg}",
                blockchain=self.name,
                network=self.network,
                timeout=self.rpc_config.get("timeout"),
                details={"original_error": error_msg}
            )
        elif "rate limit" in error_msg.lower():
            raise RateLimitError(
                f"Rate limit exceeded: {error_msg}",
                blockchain=self.name,
                network=self.network,
                limit=self._rate_limiter.requests_per_second,
                retry_after=1.0,
                details={"original_error": error_msg}
            )
        else:
            raise BlockchainAdapterError(
                f"Blockchain operation failed: {error_msg}",
                blockchain=self.name,
                network=self.network,
                details={"original_error": error_msg}
            )

    async def _execute_with_rate_limit(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation with rate limiting and error handling.

        Args:
            operation: Function to execute (can be sync or async)
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Result of operation

        Raises:
            BlockchainAdapterError: If operation fails
        """
        await self._rate_limiter.acquire()

        self._request_count += 1
        self._last_request_time = datetime.now(timezone.utc)

        try:
            # Check if operation is async
            if asyncio.iscoroutinefunction(operation):
                result = await operation(*args, **kwargs)
            else:
                result = operation(*args, **kwargs)
            return result
        except Exception as e:
            self._handle_blockchain_error(e)

    async def _initialize_connection_pool(self) -> None:
        """Initialize connection pool with health checks.

        Tests each connection to determine availability.
        """
        # Default implementation - just mark all as available
        self._connection_pool._failed_indices.clear()

    def _get_next_connection(self) -> str:
        """Get next available RPC connection.

        Returns:
            RPC endpoint URL
        """
        return self._connection_pool.get_next_connection()

    def _record_request(self) -> None:
        """Record a request for rate limiting."""
        self._request_count += 1
        self._last_request_time = datetime.now(timezone.utc)

    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows new requests.

        Returns:
            True if request can proceed, False otherwise
        """
        return self._rate_limiter.can_acquire()

    @abstractmethod
    async def get_transaction(self, transaction_hash: str) -> Dict[str, Any]:
        """Get transaction information by hash.

        Args:
            transaction_hash: Transaction hash

        Returns:
            Transaction information

        Raises:
            TransactionError: If transaction is not found
            BlockchainAdapterError: If request fails
        """
        pass

    async def get_events_stream(
        self,
        address: Optional[str] = None,
        topics: Optional[List[str]] = None,
        from_block: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream events in real-time.

        Args:
            address: Contract address to filter by
            topics: Event topics to filter by
            from_block: Starting block number

        Yields:
            Event dictionaries as they occur

        Raises:
            BlockchainAdapterError: If streaming fails
        """
        # Default implementation - poll for new blocks and get logs
        current_block = from_block or await self.get_latest_block_number()

        while True:
            try:
                latest_block = await self.get_latest_block_number()
                if latest_block > current_block:
                    logs = await self.get_logs(
                        address=address,
                        topics=topics,
                        from_block=current_block + 1,
                        to_block=latest_block
                    )
                    for log in logs:
                        yield log
                    current_block = latest_block

                await asyncio.sleep(1)  # Poll every second
            except Exception as e:
                self._handle_blockchain_error(e)