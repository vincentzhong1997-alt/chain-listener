"""Storage abstraction layer for state persistence."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional

class StorageBackend(ABC):
    """Abstract storage backend API."""

    @abstractmethod
    async def save(self, key: str, value: Any) -> None:
        """Persist a value under the given key."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a value by key."""


class InMemoryStorage(StorageBackend):
    """Simple dictionary based storage used for defaults and tests."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def save(self, key: str, value: Any) -> None:
        async with self._lock:
            self._store[key] = value

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            return self._store.get(key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

__all__ = [
    "StorageBackend",
    "InMemoryStorage",
]

