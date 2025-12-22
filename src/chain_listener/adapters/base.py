"""Base blockchain adapter interface and common functionality.

This module defines the abstract interface that all blockchain adapters must
implement, along with common functionality for connection management,
rate limiting, error handling, and batch operations.
"""

import asyncio
import json
import re
import time
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Union, Awaitable

from chain_listener.exceptions import (
    BlockchainAdapterError,
    ConnectionError as ChainConnectionError,
    RateLimitError,
    RetryExhaustedError
)
from chain_listener.models.events import RawEvent, DecodedEvent, ChainType

logger = logging.getLogger(__name__)


class BaseConnectionPool(ABC):
    """Abstract base class for connection pool implementations."""

    def __init__(self, urls: List[str], **kwargs):
        """Initialize connection pool.

        Args:
            urls: List of RPC endpoint URLs
            **kwargs: Additional configuration parameters
        """
        self.urls = urls

    @abstractmethod
    def get_next_connection(self) -> str:
        """Get next available connection for request.

        Returns:
            RPC endpoint URL
        """
        pass

    @abstractmethod
    def mark_success(self, url: str) -> None:
        """Mark a request as successful.

        Args:
            url: The RPC endpoint URL that was successful
        """
        pass

    @abstractmethod
    def mark_failure(self, url: str) -> None:
        """Mark a request as failed.

        Args:
            url: The RPC endpoint URL that failed
        """
        pass

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all connections.

        Returns:
            Dictionary with health information for each endpoint
        """
        return {url: {"status": "unknown"} for url in self.urls}


class PriorityConnectionPool(BaseConnectionPool):
    """Manages RPC endpoints with priority and intelligent failover."""

    def __init__(self, endpoints: List, max_retries: int = 3):
        """
        Initialize priority connection pool.

        Args:
            endpoints: List of URLs or list of (url, priority) tuples
            max_retries: Maximum number of retries before marking endpoint as failed
        """
        if not endpoints:
            raise ValueError("Endpoints list cannot be empty")

        # 约定大于配置：按顺序分配优先级（数字越小优先级越高）
        if isinstance(endpoints[0], str):
            # 简单URL列表：按顺序分配优先级
            self.endpoints = [(url, index + 1) for index, url in enumerate(endpoints)]
            urls = endpoints
        else:
            # (url, priority) 元组列表
            # 验证所有端点都是正确格式
            for endpoint in endpoints:
                if not isinstance(endpoint, (list, tuple)) or len(endpoint) != 2:
                    raise ValueError("All endpoints must be (url, priority) tuples")

            self.endpoints = [(url, priority) for url, priority in endpoints]
            # 按优先级排序（数字越小优先级越高）
            self.endpoints = sorted(self.endpoints, key=lambda x: x[1])
            urls = [url for url, _ in self.endpoints]

        super().__init__(urls)

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

    def get_next_connection(self) -> str:
        """获取当前可用的最佳端点"""
        now = time.time()

        for url, _ in self.endpoints:
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
        chain_type_value = config.get("chain_type")
        if isinstance(chain_type_value, ChainType):
            self.chain_type = chain_type_value
        elif chain_type_value is not None:
            try:
                self.chain_type = ChainType(chain_type_value)
            except ValueError:
                logger.warning(
                    "Unknown chain type '%s' for adapter %s; keeping raw value",
                    chain_type_value,
                    self.name,
                )
                self.chain_type = chain_type_value
        else:
            logger.warning("Adapter %s initialized without chain_type", self.name)
            self.chain_type = chain_type_value
        self._contract_configs: List[Dict[str, Any]] = config.get("contracts", []) or []
        self._abi_cache: Dict[str, Any] = {}

        # Connection management - use PriorityConnectionPool with URL ordering as priority
        urls = self.rpc_config["urls"]
        self._connection_pool = PriorityConnectionPool(
            endpoints=urls,
            max_retries=self.rpc_config.get("retries", 3)
        )

        # Rate limiting using async-limiter
        from async_limiter import DualRateLimiter
        rate_limit_config = self.rpc_config.get("rate_limit", {})
        self._requests_per_second = rate_limit_config.get("requests_per_second", 10)
        self._burst_size = rate_limit_config.get("burst_size", 20)

        # Convert to DualRateLimiter parameters
        # max_concurrent: allow burst_size concurrent requests
        # max_requests: allow requests_per_second requests per time_period
        # time_period: 1 second for rate limiting per second
        self._rate_limiter = DualRateLimiter(
            max_concurrent=self._burst_size,
            max_requests=self._requests_per_second,
            time_period=1.0
        )

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
    async def get_logs(
        self,
        address: Optional[Union[str, List[str]]] = None,
        topics: Optional[List[str]] = None,
        from_block: Optional[Union[int, str]] = None,
        to_block: Optional[Union[int, str]] = None,
        event_filters: Optional[Dict[str, List[str]]] = None
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

    @abstractmethod
    def decode_event(self, event: RawEvent) -> Union[DecodedEvent, Awaitable[DecodedEvent]]:
        """Decode a raw event into a standardized DecodedEvent."""
        pass

    def _handle_blockchain_error(self, error: Exception) -> None:
        """Handle blockchain-specific errors and convert to SDK exceptions.

        Args:
            error: Original error from blockchain interaction

        Raises:
            BlockchainAdapterError: Converted SDK exception
        """
        response_text = None
        response_status = None
        response_headers = None

        response = getattr(error, "response", None)
        if response is not None:
            response_status = getattr(response, "status_code", None)
            try:
                response_text = response.text
            except Exception:
                response_text = None
            try:
                response_headers = dict(response.headers)
            except Exception:
                response_headers = None

        logger.error(
            "Blockchain adapter '%s' (%s) operation failed: %s (status=%s)",
            getattr(self, "name", "unknown"),
            getattr(self, "network", "unknown"),
            error,
            response_status,
            exc_info=error,
        )

        if response_text:
            logger.error("RPC response body: %s", response_text)
        if response_headers:
            logger.debug("RPC response headers: %s", response_headers)

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
                limit=self._requests_per_second,
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

    def _load_contract_abi(self, abi_path: Optional[str]) -> Optional[Any]:
        """Load and cache contract ABI definitions from disk.

        Args:
            abi_path: Path to the ABI file provided in configuration.

        Returns:
            Parsed ABI object or None if loading fails.
        """
        if not abi_path:
            return None

        logger = logging.getLogger(__name__)

        try:
            path = Path(abi_path).expanduser()
        except Exception as exc:
            logger.warning(f"Unable to expand ABI path '{abi_path}': {exc}")
            return None

        if not path.is_absolute():
            path = Path.cwd() / path

        # Resolve path for cache key (non-strict keeps original behaviour for missing files)
        try:
            path = path.resolve()
        except Exception:
            # If resolution fails we still attempt to read using the constructed path
            pass

        cache_key = str(path)
        if cache_key in self._abi_cache:
            return self._abi_cache[cache_key]

        if not path.exists():
            logger.warning(f"ABI file not found: {path}")
            return None

        try:
            with path.open("r", encoding="utf-8") as abi_file:
                abi = json.load(abi_file)
                self._abi_cache[cache_key] = abi
                return abi
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse ABI JSON at {path}: {exc}")
        except OSError as exc:
            logger.error(f"Failed to read ABI file {path}: {exc}")

        return None

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
        # Use async-limiter context manager for rate limiting
        async with self._rate_limiter:

            try:
                # Check if operation is async
                if asyncio.iscoroutinefunction(operation):
                    result = await operation(*args, **kwargs)
                else:
                    result = operation(*args, **kwargs)
                return result
            except Exception as e:
                
                self._handle_blockchain_error(e)


    
