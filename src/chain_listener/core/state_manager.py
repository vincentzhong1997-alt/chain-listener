"""State management built on top of storage backends."""

from __future__ import annotations

import time
from typing import Optional

from ..models.events import ChainType
from ..models.state import BlockState
from ..storage import InMemoryStorage, StorageBackend


class StateManager:
    """High-level API that manages per-chain processing state."""

    def __init__(
        self,
        storage_backend: Optional[StorageBackend] = None,
        key_prefix: str = "chain_listener",
    ) -> None:
        self._storage = storage_backend or InMemoryStorage()
        self._key_prefix = key_prefix.rstrip(":")

    def _build_key(self, chain_type: ChainType) -> str:
        return f"{self._key_prefix}:block_state:{chain_type.value}"

    async def record_block_state(
        self,
        chain_type: ChainType,
        block_number: int,
        processed_at: Optional[int] = None,
    ) -> BlockState:
        """Persist the latest processed block information for a chain."""
        state = BlockState(
            chain_type=chain_type,
            block_number=block_number,
            processed_at=processed_at or int(time.time()),
        )
        await self._storage.save(self._build_key(chain_type), state.to_dict())
        return state

    async def get_block_state(self, chain_type: ChainType) -> Optional[BlockState]:
        """Fetch the latest persisted block state for a chain."""
        data = await self._storage.get(self._build_key(chain_type))
        if isinstance(data, BlockState):
            return data
        return BlockState.from_dict(data)

    async def get_latest_block(self, chain_type: ChainType) -> Optional[int]:
        """Return the last processed block number, if any."""
        state = await self.get_block_state(chain_type)
        return state.block_number if state else None

    async def delete_block_state(self, chain_type: ChainType) -> None:
        """Remove persisted state for a chain."""
        await self._storage.delete(self._build_key(chain_type))
