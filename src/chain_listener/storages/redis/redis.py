"""Redis-backed storage backend kept in a separate module for optional deps."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Optional

from aioredis import Redis

from ...storage import StorageBackend


class RedisStorage(StorageBackend):
    """Redis hash based storage backend."""

    def __init__(self, redis_client: "Redis", key_prefix: str = "chain_listener") -> None:
        self._redis = redis_client
        normalized_prefix = key_prefix.rstrip(":")
        self._hash_key = f"{normalized_prefix}:state"

    async def save(self, key: str, value: Any) -> None:
        await self._redis.hset(self._hash_key, key, self._serialize(value))

    async def get(self, key: str) -> Optional[Any]:
        value = await self._redis.hget(self._hash_key, key)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    async def delete(self, key: str) -> None:
        await self._redis.hdel(self._hash_key, key)

    def _serialize(self, value: Any) -> str:
        if is_dataclass(value):
            value = asdict(value)
        return json.dumps(
            value,
            default=lambda obj: obj.value if hasattr(obj, "value") else str(obj),
        )
