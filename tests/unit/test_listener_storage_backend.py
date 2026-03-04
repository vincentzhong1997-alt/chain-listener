"""Tests for ChainListener storage backend switching."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import Mock, patch

import pytest

from chain_listener.core.listener import ChainListener
from chain_listener.exceptions import ChainListenerError
from chain_listener.models.config import ChainListenerConfig
from chain_listener.storage import StorageBackend


class DummyStorage(StorageBackend):
    """Simple storage backend for tests."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def save(self, key: str, value: Any) -> None:
        self._data[key] = value

    async def get(self, key: str) -> Optional[Any]:
        return self._data.get(key)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)


@pytest.fixture
def sample_config() -> ChainListenerConfig:
    """Create a minimal config for ChainListener tests."""
    return ChainListenerConfig(
        chains={
            "ethereum": {
                "chain_type": "ethereum",
                "rpc": {"urls": ["https://eth.llamarpc.com"]},
                "contracts": [],
            }
        }
    )


def test_set_storage_backend_updates_state_manager(sample_config: ChainListenerConfig) -> None:
    """set_storage_backend should replace state manager and sync event processor."""
    with patch("chain_listener.core.listener.adapter_registry") as mock_registry:
        mock_registry.register_adapter = Mock()
        listener = ChainListener(sample_config)

    new_backend = DummyStorage()
    old_state_manager = listener._state_manager

    listener.set_storage_backend(new_backend)

    assert listener._state_manager is not old_state_manager
    assert listener._state_manager._storage is new_backend
    assert listener._event_processor is not None
    assert listener._event_processor._state_manager is listener._state_manager


def test_set_storage_backend_while_listening_raises_error(
    sample_config: ChainListenerConfig,
) -> None:
    """Storage backend should not be switchable during active listening."""
    with patch("chain_listener.core.listener.adapter_registry") as mock_registry:
        mock_registry.register_adapter = Mock()
        listener = ChainListener(sample_config)

    listener._is_listening = True

    with pytest.raises(
        ChainListenerError, match="Cannot change storage backend while listening"
    ):
        listener.set_storage_backend(DummyStorage())
