"""Custom exceptions for the chain listener SDK."""

from typing import Optional, Any, Dict


class ChainListenerError(Exception):
    """Base exception for chain listener SDK."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize exception with message and optional details.

        Args:
            message: Human-readable error message
            details: Additional error context and metadata
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(ChainListenerError):
    """Raised when configuration is invalid or missing."""
    pass


class BlockchainAdapterError(ChainListenerError):
    """Raised when blockchain adapter encounters an error."""

    def __init__(
        self,
        message: str,
        blockchain: Optional[str] = None,
        network: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize blockchain adapter error.

        Args:
            message: Human-readable error message
            blockchain: Blockchain name (e.g., 'ethereum')
            network: Network name (e.g., 'mainnet')
            details: Additional error context
        """
        super().__init__(message, details)
        self.blockchain = blockchain
        self.network = network


class ConnectionError(BlockchainAdapterError):
    """Raised when adapter cannot connect to blockchain."""

    def __init__(
        self,
        message: str,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
        retry_count: Optional[int] = None,
        **kwargs
    ):
        """Initialize connection error.

        Args:
            message: Human-readable error message
            endpoint: RPC endpoint that failed
            timeout: Connection timeout in seconds
            retry_count: Number of retries attempted
            **kwargs: Additional arguments for BlockchainAdapterError
        """
        super().__init__(message, **kwargs)
        self.endpoint = endpoint
        self.timeout = timeout
        self.retry_count = retry_count


class RateLimitError(BlockchainAdapterError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        limit: Optional[int] = None,
        window: Optional[float] = None,
        retry_after: Optional[float] = None,
        **kwargs
    ):
        """Initialize rate limit error.

        Args:
            message: Human-readable error message
            limit: Number of requests allowed
            window: Time window in seconds
            retry_after: Seconds to wait before retrying
            **kwargs: Additional arguments for BlockchainAdapterError
        """
        super().__init__(message, **kwargs)
        self.limit = limit
        self.window = window
        self.retry_after = retry_after


class EventProcessingError(ChainListenerError):
    """Raised when event processing encounters an error."""

    def __init__(
        self,
        message: str,
        event_type: Optional[str] = None,
        contract_address: Optional[str] = None,
        transaction_hash: Optional[str] = None,
        **kwargs
    ):
        """Initialize event processing error.

        Args:
            message: Human-readable error message
            event_type: Type of event that failed to process
            contract_address: Contract address related to the error
            transaction_hash: Transaction hash related to the error
            **kwargs: Additional arguments for ChainListenerError
        """
        super().__init__(message, **kwargs)
        self.event_type = event_type
        self.contract_address = contract_address
        self.transaction_hash = transaction_hash


class EventValidationError(EventProcessingError):
    """Raised when event data validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        """Initialize event validation error.

        Args:
            message: Human-readable error message
            field: Field that failed validation
            value: Invalid value
            **kwargs: Additional arguments for EventProcessingError
        """
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value


class DeduplicationError(ChainListenerError):
    """Raised when event deduplication fails."""

    def __init__(
        self,
        message: str,
        event_hash: Optional[str] = None,
        cache_key: Optional[str] = None,
        **kwargs
    ):
        """Initialize deduplication error.

        Args:
            message: Human-readable error message
            event_hash: Hash of the event that caused the error
            cache_key: Cache key related to the error
            **kwargs: Additional arguments for ChainListenerError
        """
        super().__init__(message, **kwargs)
        self.event_hash = event_hash
        self.cache_key = cache_key


class DistributedCoordinationError(ChainListenerError):
    """Raised when distributed coordination fails."""

    def __init__(
        self,
        message: str,
        instance_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        """Initialize distributed coordination error.

        Args:
            message: Human-readable error message
            instance_id: ID of the instance that encountered the error
            operation: Operation that failed (e.g., 'leader_election', 'lock_acquisition')
            **kwargs: Additional arguments for ChainListenerError
        """
        super().__init__(message, **kwargs)
        self.instance_id = instance_id
        self.operation = operation


class HealthCheckError(ChainListenerError):
    """Raised when health check fails."""

    def __init__(
        self,
        message: str,
        component: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs
    ):
        """Initialize health check error.

        Args:
            message: Human-readable error message
            component: Component that failed health check
            status: Health status (e.g., 'unhealthy', 'degraded')
            **kwargs: Additional arguments for ChainListenerError
        """
        super().__init__(message, **kwargs)
        self.component = component
        self.status = status


class RetryExhaustedError(ChainListenerError):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self,
        message: str,
        max_retries: Optional[int] = None,
        last_error: Optional[Exception] = None,
        **kwargs
    ):
        """Initialize retry exhausted error.

        Args:
            message: Human-readable error message
            max_retries: Maximum number of retries attempted
            last_error: The last error that occurred
            **kwargs: Additional arguments for ChainListenerError
        """
        super().__init__(message, **kwargs)
        self.max_retries = max_retries
        self.last_error = last_error


class SubscriptionError(BlockchainAdapterError):
    """Raised when blockchain event subscription fails."""

    def __init__(
        self,
        message: str,
        subscription_id: Optional[str] = None,
        contract_address: Optional[str] = None,
        **kwargs
    ):
        """Initialize subscription error.

        Args:
            message: Human-readable error message
            subscription_id: ID of the subscription that failed
            contract_address: Contract address being subscribed to
            **kwargs: Additional arguments for BlockchainAdapterError
        """
        super().__init__(message, **kwargs)
        self.subscription_id = subscription_id
        self.contract_address = contract_address


class BlockNotFoundError(BlockchainAdapterError):
    """Raised when a block cannot be found."""

    def __init__(
        self,
        message: str,
        block_number: Optional[int] = None,
        block_hash: Optional[str] = None,
        **kwargs
    ):
        """Initialize block not found error.

        Args:
            message: Human-readable error message
            block_number: Block number that was not found
            block_hash: Block hash that was not found
            **kwargs: Additional arguments for BlockchainAdapterError
        """
        super().__init__(message, **kwargs)
        self.block_number = block_number
        self.block_hash = block_hash


class TransactionError(BlockchainAdapterError):
    """Raised when transaction processing fails."""

    def __init__(
        self,
        message: str,
        transaction_hash: Optional[str] = None,
        block_number: Optional[int] = None,
        **kwargs
    ):
        """Initialize transaction error.

        Args:
            message: Human-readable error message
            transaction_hash: Hash of the transaction that failed
            block_number: Block number containing the transaction
            **kwargs: Additional arguments for BlockchainAdapterError
        """
        super().__init__(message, **kwargs)
        self.transaction_hash = transaction_hash
        self.block_number = block_number