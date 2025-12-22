"""State management data structures.

This module defines the state-related data classes used by the state manager
and storage backends. Keeping the definitions in a dedicated module avoids
cyclic imports between core components and storage providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .events import ChainType


@dataclass
class BlockState:
    """Represents the processing state for a specific chain block.

    Attributes:
        chain_type: The blockchain network this state belongs to.
        block_number: The highest processed block number for the chain.
        block_hash: The corresponding block hash, used for reorg detection.
        processed_at: Unix timestamp indicating when the block was processed.
    """

    chain_type: ChainType
    block_number: int
    block_hash: str
    processed_at: int

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["BlockState"]:
        """Create a BlockState from a dictionary."""
        if not data:
            return None

        try:
            chain_value = data.get("chain_type")
            chain_type = ChainType(chain_value) if chain_value else None
        except ValueError:
            chain_type = None

        if chain_type is None:
            return None

        return cls(
            chain_type=chain_type,
            block_number=int(data.get("block_number", 0)),
            block_hash=str(data.get("block_hash", "")),
            processed_at=int(data.get("processed_at", 0)),
        )

    def to_dict(self) -> dict:
        """Convert the block state to a serializable dictionary."""
        return {
            "chain_type": self.chain_type.value,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "processed_at": self.processed_at,
        }
