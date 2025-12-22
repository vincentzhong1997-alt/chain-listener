"""Unit tests for StateManager storage coordination."""

import pytest

from chain_listener.core.state_manager import StateManager
from chain_listener.models.events import ChainType


@pytest.mark.asyncio
async def test_record_block_state_sets_latest_block_number():
    manager = StateManager()

    await manager.record_block_state(
        chain_type=ChainType.ETHEREUM,
        block_number=123,
        block_hash="0xabc",
        processed_at=1700000000,
    )

    assert await manager.get_latest_block(ChainType.ETHEREUM) == 123


@pytest.mark.asyncio
async def test_get_block_state_returns_block_hash():
    manager = StateManager()

    await manager.record_block_state(
        chain_type=ChainType.BSC,
        block_number=5,
        block_hash="0xbeef",
        processed_at=1700000001,
    )

    state = await manager.get_block_state(ChainType.BSC)
    if state is None:
        pytest.fail("Expected block state for BSC")
    assert state.block_hash == "0xbeef"


@pytest.mark.asyncio
async def test_subsequent_record_overwrites_previous_block():
    manager = StateManager()

    await manager.record_block_state(ChainType.SOLANA, 10, "0x1")
    await manager.record_block_state(ChainType.SOLANA, 11, "0x2")

    assert await manager.get_latest_block(ChainType.SOLANA) == 11


@pytest.mark.asyncio
async def test_delete_block_state_clears_persisted_state():
    manager = StateManager()
    await manager.record_block_state(ChainType.TRON, 7, "0x7")

    await manager.delete_block_state(ChainType.TRON)

    assert await manager.get_latest_block(ChainType.TRON) is None
