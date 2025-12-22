"""Registry for managing event callback functions.

This module provides a centralized registry for managing user
callback functions for blockchain events.
"""

import logging
from typing import Dict, Callable, Optional, List, Any
from ..models.events import DecodedEvent
from ..exceptions import EventProcessingError

logger = logging.getLogger(__name__)


class CallbackRegistry:
    """Registry for managing event callback functions.

    This class manages the registration and retrieval of callback
    functions for specific blockchain events. It uses a key-based
    mapping system for efficient lookup.
    """

    def __init__(self) -> None:
        """Initialize the callback registry."""
        self._callbacks: Dict[str, Callable] = {}
        self._callback_metadata: Dict[str, Dict[str, Any]] = {}
        logger.info("CallbackRegistry initialized")

    def _create_key(self, contract_address: str, event_name: str) -> str:
        """Create a unique key for callback registration.

        Args:
            contract_address: The contract address (should be in checksum format)
            event_name: The event name

        Returns:
            str: Unique key for the callback
        """
        return f"{contract_address}:{event_name}"

    def register_callback(
        self,
        contract_address: str,
        event_name: str,
        callback: Callable,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a callback function for a specific event.

        Args:
            contract_address: The contract address to watch
            event_name: The event name to watch for
            callback: The callback function to execute
            metadata: Optional metadata for the callback

        Raises:
            EventProcessingError: If callback is invalid or already registered
        """
        if not callable(callback):
            raise EventProcessingError("Callback must be callable")

        key = self._create_key(contract_address, event_name)

        if key in self._callbacks:
            logger.warning(f"Callback already registered for {key}, overwriting")

        self._callbacks[key] = callback
        self._callback_metadata[key] = metadata or {}

        logger.info(f"Registered callback for {event_name} on {contract_address}")

  
    def get_callback(
        self,
        contract_address: str,
        event_name: str
    ) -> Optional[Callable]:
        """Get a callback function for a specific event.

        Args:
            contract_address: The contract address
            event_name: The event name

        Returns:
            Optional[Callable]: The callback function, or None if not found
        """
        key = self._create_key(contract_address, event_name)
        return self._callbacks.get(key)

    
    
    def list_callbacks(self) -> List[Dict[str, Any]]:
        """List all registered callbacks.

        Returns:
            List[Dict[str, Any]]: List of callback information
        """
        callbacks = []

        for key, callback in self._callbacks.items():
            contract_address, event_name = key.split(':', 1)
            callback_info = {
                "contract_address": contract_address,
                "event_name": event_name,
                "callback_name": getattr(callback, '__name__', 'anonymous'),
                "metadata": self._callback_metadata.get(key, {})
            }
            callbacks.append(callback_info)

        return callbacks

    
    async def execute_callback(
        self,
        contract_address: str,
        event_name: str,
        event_data: DecodedEvent
    ) -> Any:
        """Execute a callback function for an event.

        Args:
            contract_address: The contract address
            event_name: The event name
            event_data: The decoded event data

        Returns:
            Any: Result of the callback function

        Raises:
            EventProcessingError: If callback execution fails
        """
        callback = self.get_callback(contract_address, event_name)

        if callback is None:
            logger.debug(f"No callback registered for {event_name} on {contract_address}")
            return None

        try:
            # Execute callback (sync or async)
            import asyncio
            if asyncio.iscoroutinefunction(callback):
                result = await callback(event_data)
            else:
                result = callback(event_data)

            logger.debug(
                f"Executed callback for {event_name} on {contract_address}: "
                f"result={result}"
            )
            return result

        except Exception as e:
            logger.error(
                f"Error executing callback for {event_name} on {contract_address}: {e}"
            )
            raise EventProcessingError(
                f"Callback execution failed for {event_name} on {contract_address}: {e}"
            )

    def clear(self) -> None:
        """Clear all registered callbacks.

        This is primarily used for testing and reinitialization.
        """
        count = len(self._callbacks)
        self._callbacks.clear()
        self._callback_metadata.clear()

        logger.info(f"Cleared {count} callbacks from registry")

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dict[str, Any]: Registry statistics
        """
        return {
            "total_callbacks": len(self._callbacks),
            "unique_contracts": len(set(key.split(':')[0] for key in self._callbacks.keys())),
            "unique_events": len(set(key.split(':')[1] for key in self._callbacks.keys())),
            "callback_list": self.list_callbacks()
        }