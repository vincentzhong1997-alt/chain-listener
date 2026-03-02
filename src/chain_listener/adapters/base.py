"""Base blockchain adapter interface and common functionality.

This module defines the abstract interface that all blockchain adapters must
implement, along with common functionality for connection management,
rate limiting, error handling, and batch operations.
"""

import asyncio
import inspect
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

    def __init__(self, **kwargs):
        """Initialize connection pool.

        Args:
            urls: List of RPC endpoint URLs
            **kwargs: Additional configuration parameters
        """
        pass

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
        pass


class PriorityConnectionPool(BaseConnectionPool):
    """Manages RPC endpoints with priority and intelligent failover."""

    def __init__(self, endpoints: List, max_retries: int = 3):
        """
        Initialize priority connection pool.

        Args:
            endpoints: List of endpoint definitions (str, tuple, or dict)
            max_retries: Maximum number of retries before marking endpoint as failed
        """
        if not endpoints:
            raise ValueError("Endpoints list cannot be empty")

        self.endpoint_meta: Dict[str, Dict[str, Any]] = {}
        normalized: List[tuple] = []

        # Normalize to list of dicts with url/priority/headers/api_key/api_key_header
        if isinstance(endpoints[0], str):
            endpoint_dicts = [
                {"url": url, "priority": idx + 1} for idx, url in enumerate(endpoints)
            ]
        elif isinstance(endpoints[0], (list, tuple)) and len(endpoints[0]) == 2:
            endpoint_dicts = [
                {"url": url, "priority": priority}
                for url, priority in endpoints
            ]
        else:
            endpoint_dicts = []
            for idx, ep in enumerate(endpoints):
                if not isinstance(ep, dict) or not ep.get("url"):
                    raise ValueError("All endpoints must include a url")
                ep_copy = dict(ep)
                if ep_copy.get("priority") is None:
                    ep_copy["priority"] = idx + 1
                endpoint_dicts.append(ep_copy)

        # Sort by priority
        endpoint_dicts.sort(key=lambda e: e.get("priority", 0))

        for ep in endpoint_dicts:
            url = ep["url"]
            prio = ep.get("priority", 0)
            normalized.append((url, prio))
            self.endpoint_meta[url] = {
                "headers": dict(ep.get("headers") or {}),
                "api_key": ep.get("api_key"),
                "api_key_header": ep.get("api_key_header"),
            }

        urls = [url for url, _ in normalized]

        # Base class doesn't use urls; super call kept for interface consistency.
        super().__init__()

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
            for url, _ in normalized
        }
        self.endpoints = normalized

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

    def get_headers(self, url: str) -> Dict[str, Any]:
        """Return headers bound to a specific endpoint."""
        meta = self.endpoint_meta.get(url, {}) or {}
        headers = dict(meta.get("headers") or {})
        api_key = meta.get("api_key")
        api_key_header = meta.get("api_key_header")
        if api_key and api_key_header and api_key_header not in headers:
            headers[api_key_header] = api_key
        return headers

    def get_endpoint_meta(self, url: str) -> Dict[str, Any]:
        """Return full metadata for an endpoint."""
        return dict(self.endpoint_meta.get(url, {}) or {})


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
        endpoints = self.rpc_config.get("endpoints") or urls
        self._connection_pool = PriorityConnectionPool(
            endpoints=endpoints,
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
        if self._is_rate_limit_error(error):
            raise RateLimitError(
                f"Rate limit exceeded: {error_msg}",
                blockchain=self.name,
                network=self.network,
                limit=self._requests_per_second,
                retry_after=self._extract_retry_after_seconds(error) or 1.0,
                details={"original_error": error_msg},
            )
        if "timeout" in error_msg.lower():
            raise ChainConnectionError(
                f"Blockchain request timeout: {error_msg}",
                blockchain=self.name,
                network=self.network,
                timeout=self.rpc_config.get("timeout"),
                details={"original_error": error_msg}
            )
        else:
            raise BlockchainAdapterError(
                f"Blockchain operation failed: {error_msg}",
                blockchain=self.name,
                network=self.network,
                details={"original_error": error_msg}
            )

    def _extract_retry_after_seconds(self, error: Exception) -> Optional[float]:
        """Extract retry-after hint from exception or response metadata."""
        if isinstance(error, RateLimitError) and error.retry_after:
            return float(error.retry_after)

        response = getattr(error, "response", None)
        if response is not None:
            headers = getattr(response, "headers", None) or {}
            retry_after_raw = headers.get("Retry-After") or headers.get("retry-after")
            if retry_after_raw is not None:
                try:
                    retry_after = float(retry_after_raw)
                    if retry_after >= 0:
                        return retry_after
                except (TypeError, ValueError):
                    pass

        error_msg = str(error)
        match = re.search(
            r"retry(?:\s*after)?\s*[:=]?\s*(\d+(?:\.\d+)?)",
            error_msg,
            re.IGNORECASE,
        )
        if match:
            try:
                retry_after = float(match.group(1))
                if retry_after >= 0:
                    return retry_after
            except ValueError:
                return None

        return None

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Detect whether an exception indicates RPC rate limiting."""
        if isinstance(error, RateLimitError):
            return True

        response = getattr(error, "response", None)
        if response is not None and getattr(response, "status_code", None) == 429:
            return True

        if error.args:
            first_arg = error.args[0]
            if isinstance(first_arg, dict):
                code = first_arg.get("code")
                message = str(first_arg.get("message", "")).lower()
                if code in {-32005, 429}:
                    return True
                if "limit exceeded" in message or "too many requests" in message:
                    return True

        error_msg = str(error).lower()
        rate_limit_markers = (
            "rate limit",
            "too many requests",
            "limit exceeded",
            "quota exceeded",
            "request limit",
            "throttl",
            "-32005",
        )
        return any(marker in error_msg for marker in rate_limit_markers)

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

    @abstractmethod
    def _get_or_create_client(self, endpoint: str) -> Any:
        """Get or create a client for the given endpoint.

        Args:
            endpoint: The RPC endpoint URL

        Returns:
            Client instance for the specific blockchain
        """
        pass

    async def _execute_with_client(self, operation: Callable[[Any], Any]) -> Any:
        """Execute a single-argument operation with client and automatic retry logic.

        Args:
            operation: Callable receiving a client instance and returning a result
                (sync or async). The callable should accept exactly one argument:
                the client retrieved from the connection pool.

        Returns:
            Result of the operation

        Raises:
            RetryExhaustedError: If all retry attempts fail
        """
        last_error: Optional[Exception] = None
        max_retries = self._connection_pool.max_retries

        for attempt in range(max_retries + 1):
            endpoint = self._connection_pool.get_next_connection()
            client = self._get_or_create_client(endpoint)

            try:
                result = await self._execute_with_rate_limit(lambda: operation(client))
                self._connection_pool.mark_success(endpoint)
                return result
            except Exception as exc:
                last_error = exc
                self._connection_pool.mark_failure(endpoint)
                if attempt < max_retries:
                    if self._is_rate_limit_error(exc):
                        retry_after = self._extract_retry_after_seconds(exc)
                        delay = retry_after if retry_after is not None else min(2 ** attempt, 30)
                        await asyncio.sleep(delay)
                    continue

        # All retries exhausted
        if last_error:
            self._handle_blockchain_error(last_error)
        else:
            raise RetryExhaustedError(
                f"All {max_retries + 1} retry attempts failed for adapter {self.name}",
                blockchain=self.name,
                network=self.network,
                attempts=max_retries + 1
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
        # Use async-limiter context manager for rate limiting
        async with self._rate_limiter:

            try:
                # Check if operation is async
                if asyncio.iscoroutinefunction(operation):
                    result = await operation(*args, **kwargs)
                else:
                    result = operation(*args, **kwargs)
                    if inspect.isawaitable(result):
                        result = await result
                return result
            except Exception as e:
                
                self._handle_blockchain_error(e)


    
