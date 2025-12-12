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

    def unregister_callback(
        self,
        contract_address: str,
        event_name: str
    ) -> Optional[Callable]:
        """Unregister a callback function.

        Args:
            contract_address: The contract address
            event_name: The event name

        Returns:
            Optional[Callable]: The removed callback function, or None if not found
        """
        key = self._create_key(contract_address, event_name)

        callback = self._callbacks.pop(key, None)
        self._callback_metadata.pop(key, None)

        if callback:
            logger.info(f"Unregistered callback for {event_name} on {contract_address}")
        else:
            logger.warning(f"No callback found for {event_name} on {contract_address}")

        return callback

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

    def get_callback_metadata(
        self,
        contract_address: str,
        event_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get metadata for a callback function.

        Args:
            contract_address: The contract address
            event_name: The event name

        Returns:
            Optional[Dict[str, Any]]: The metadata, or None if not found
        """
        key = self._create_key(contract_address, event_name)
        return self._callback_metadata.get(key)

    def has_callback(
        self,
        contract_address: str,
        event_name: str
    ) -> bool:
        """Check if a callback is registered for a specific event.

        Args:
            contract_address: The contract address
            event_name: The event name

        Returns:
            bool: True if callback exists, False otherwise
        """
        key = self._create_key(contract_address, event_name)
        return key in self._callbacks

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

    def get_callbacks_for_contract(self, contract_address: str) -> List[Dict[str, Any]]:
        """Get all callbacks for a specific contract.

        Args:
            contract_address: The contract address (should be in checksum format)

        Returns:
            List[Dict[str, Any]]: List of callbacks for the contract
        """
        callbacks = []

        for key, callback in self._callbacks.items():
            key_address, event_name = key.split(':', 1)
            if key_address == contract_address:
                callback_info = {
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