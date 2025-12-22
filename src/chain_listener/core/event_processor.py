"""Event processor for handling blockchain events.

This module provides the core event processing functionality,
including event decoding, callback execution, and state management.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
from ..models.events import RawEvent, DecodedEvent, ChainType
from ..models.config import ChainListenerConfig
from ..exceptions import EventProcessingError
from .callback_registry import CallbackRegistry

if TYPE_CHECKING:
    from .adapter_registry import AdapterRegistry

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Result of event processing."""
    success: bool
    event: RawEvent
    decoded_event: Optional[DecodedEvent] = None
    error: Optional[str] = None
    callback_result: Optional[Any] = None


@dataclass
class ReorgInfo:
    """Information about a blockchain reorganization."""
    detected_at: int
    old_block_hash: str
    new_block_hash: str
    block_number: int
    depth: int


class EventProcessor:
    """Processor for handling blockchain events.

    This class handles the decoding of raw events, execution of callbacks,
    and management of event processing state.
    """

    def __init__(
        self,
        config: ChainListenerConfig,
        callback_registry: CallbackRegistry,
        adapter_registry: 'AdapterRegistry'
    ) -> None:
        """Initialize the event processor.

        Args:
            config: The chain listener configuration
            callback_registry: The callback registry for event callbacks
        """
        self.config = config
        self.callback_registry = callback_registry
        self._adapter_registry = adapter_registry
        self._processed_events: Dict[str, int] = {}  # Cache for deduplication
        self._reorg_detection: Dict[ChainType, Dict[int, str]] = {}  # Block hash cache

        logger.info("EventProcessor initialized")

    async def process_events(self, raw_events: List[RawEvent]) -> List[ProcessResult]:
        """Process a list of raw events.

        This method decodes events, executes callbacks, and handles errors.

        Args:
            raw_events: List of raw events to process

        Returns:
            List[ProcessResult]: Results of event processing
        """
        results = []

        # Process events concurrently for better performance
        semaphore = asyncio.Semaphore(
            self.config.global_config.max_concurrent_processing
        )

        async def process_single_event(event: RawEvent) -> ProcessResult:
            async with semaphore:
                return await self._process_single_event(event)

        # Execute processing concurrently
        tasks = [process_single_event(event) for event in raw_events]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to ProcessResult
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ProcessResult(
                    success=False,
                    event=raw_events[i],
                    error=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results

    async def _process_single_event(self, event: RawEvent) -> ProcessResult:
        """Process a single event.

        Args:
            event: The raw event to process

        Returns:
            ProcessResult: Result of event processing
        """
        try:
            # Check for duplicates
            event_hash = self._compute_event_hash(event)
            if event_hash in self._processed_events:
                logger.debug(f"Skipping duplicate event: {event_hash}")
                return ProcessResult(success=True, event=event)

            # Get adapter for decoding
            adapter = self._adapter_registry.get_adapter(event.chain_type)

            # Decode the event
            if hasattr(adapter, 'decode_event'):
                if asyncio.iscoroutinefunction(adapter.decode_event):
                    decoded_event = await adapter.decode_event(event)
                else:
                    decoded_event = adapter.decode_event(event)
            else:
                # Create basic decoded event if adapter doesn't support decoding
                decoded_event = DecodedEvent(
                    chain_type=event.chain_type,
                    contract_address=event.contract_address,
                    event_name="Unknown",  # Will be filled by adapter if available
                    parameters={},
                    block_number=event.block_number,
                    transaction_hash=event.transaction_hash,
                    log_index=event.log_index,
                    timestamp=event.timestamp
                )

            # Execute callback if registered
            callback_result = None
            try:
                callback_result = await self.callback_registry.execute_callback(
                    event.contract_address,
                    decoded_event.event_name,
                    decoded_event
                )
            except Exception as callback_error:
                logger.warning(
                    f"Callback execution failed for {decoded_event.event_name} "
                    f"on {event.contract_address}: {callback_error}"
                )
                # Don't fail the entire processing for callback errors

            # Mark event as processed
            self._processed_events[event_hash] = event.timestamp

            # Cleanup old events from cache (prevent memory leak)
            await self._cleanup_old_events()

            return ProcessResult(
                success=True,
                event=event,
                decoded_event=decoded_event,
                callback_result=callback_result
            )

        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return ProcessResult(
                success=False,
                event=event,
                error=str(e)
            )

    def _compute_event_hash(self, event: RawEvent) -> str:
        """Compute a unique hash for an event.

        Args:
            event: The raw event

        Returns:
            str: Unique event hash
        """
        # Use transaction hash and log index for uniqueness
        return f"{event.transaction_hash}:{event.log_index}"

    async def _cleanup_old_events(self) -> None:
        """Clean up old events from the processing cache.

        This method prevents memory leaks by removing old processed events.
        """
        if len(self._processed_events) > self.config.global_config.event_batch_size * 10:
            # Remove oldest half of events
            sorted_events = sorted(
                self._processed_events.items(),
                key=lambda x: x[1]  # Sort by timestamp
            )
            cutoff = len(sorted_events) // 2

            for event_hash, _ in sorted_events[:cutoff]:
                del self._processed_events[event_hash]

            logger.debug(f"Cleaned up {cutoff} old events from cache")

    async def detect_reorg(self, chain_type: ChainType) -> Optional[ReorgInfo]:
        """Detect if a blockchain reorganization has occurred.

        Args:
            chain_type: The blockchain type to check

        Returns:
            Optional[ReorgInfo]: Information about the reorg, or None if none detected
        """
        try:
            adapter = self._adapter_registry.get_adapter(chain_type)

            if not hasattr(adapter, 'get_latest_block_number'):
                return None

            # Get current block info
            if asyncio.iscoroutinefunction(adapter.get_latest_block_number):
                latest_block = await adapter.get_latest_block_number()
            else:
                latest_block = adapter.get_latest_block_number()

            if chain_type not in self._reorg_detection:
                # Initialize block hash cache
                self._reorg_detection[chain_type] = {}

            # Check if we have a cached hash for this block
            if latest_block in self._reorg_detection[chain_type]:
                cached_hash = self._reorg_detection[chain_type][latest_block]

                # Get current block hash
                if hasattr(adapter, 'get_block_by_number'):
                    if asyncio.iscoroutinefunction(adapter.get_block_by_number):
                        current_block = await adapter.get_block_by_number(latest_block)
                    else:
                        current_block = adapter.get_block_by_number(latest_block)

                    current_hash = current_block.get('hash', '') if current_block else ''

                    if current_hash and current_hash != cached_hash:
                        # Reorg detected
                        reorg_info = ReorgInfo(
                            detected_at=latest_block,
                            old_block_hash=cached_hash,
                            new_block_hash=current_hash,
                            block_number=latest_block,
                            depth=1  # TODO: Calculate actual reorg depth
                        )

                        logger.warning(f"Blockchain reorg detected for {chain_type}: {reorg_info}")
                        return reorg_info

            # Update cache with current block hash
            if hasattr(adapter, 'get_block_by_number'):
                if asyncio.iscoroutinefunction(adapter.get_block_by_number):
                    current_block = await adapter.get_block_by_number(latest_block)
                else:
                    current_block = adapter.get_block_by_number(latest_block)

                if current_block and 'hash' in current_block:
                    self._reorg_detection[chain_type][latest_block] = current_block['hash']

        except Exception as e:
            logger.error(f"Error detecting reorg for {chain_type}: {e}")

        return None

    def is_event_processed(self, event_hash: str) -> bool:
        """Check if an event has been processed.

        Args:
            event_hash: The event hash to check

        Returns:
            bool: True if event has been processed, False otherwise
        """
        return event_hash in self._processed_events

    def get_processed_events_count(self) -> int:
        """Get the number of processed events in cache.

        Returns:
            int: Number of processed events
        """
        return len(self._processed_events)

    def clear_cache(self) -> None:
        """Clear the processed events cache.

        This is primarily used for testing and reinitialization.
        """
        self._processed_events.clear()
        self._reorg_detection.clear()
        logger.info("Cleared event processor cache")

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics.

        Returns:
            Dict[str, Any]: Processor statistics
        """
        return {
            "processed_events_cache_size": len(self._processed_events),
            "reorg_cache_entries": {
                str(chain_type): len(block_hashes)
                for chain_type, block_hashes in self._reorg_detection.items()
            },
            "max_concurrent_processing": self.config.global_config.max_concurrent_processing,
            "event_batch_size": self.config.global_config.event_batch_size
        }
