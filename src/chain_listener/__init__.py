"""Chain Listener SDK - Universal multi-chain blockchain event listener.

This package provides a unified interface for listening to blockchain events
across multiple blockchain networks including Ethereum, BSC, Solana, and TRON.

Main API:
    ChainListener: Main class for blockchain event listening
    ChainListenerConfig: Configuration class for the listener

Example:
    from chain_listener import ChainListener, ChainListenerConfig

    # Load configuration from file
    listener = ChainListener.from_config_file("config.yaml")

    # Register event callback
    def handle_transfer(event):
        print(f"Transfer event: {event}")

    listener.on_event("ethereum", "0x...", "Transfer", handle_transfer)

    # Start listening
    await listener.start_listening()
"""

from .core.listener import ChainListener
from .models.config import ChainListenerConfig, ChainConfig
from .models.events import ChainType, RawEvent, DecodedEvent
from .exceptions import ChainListenerError

__version__ = "0.1.0"
__author__ = "Chain Listener Team"

# Main API exports
__all__ = [
    # Main classes
    "ChainListener",
    "ChainListenerConfig",
    "ChainConfig",

    # Event models
    "ChainType",
    "RawEvent",
    "DecodedEvent",

    # Exceptions
    "ChainListenerError",
]

# Convenience imports for advanced usage
from .core import AdapterRegistry, CallbackRegistry, EventProcessor, StateManager
from .adapters import BaseAdapter, EVMAdapter, EthereumAdapter, SolanaAdapter, TronAdapter
from .storage import StorageBackend, InMemoryStorage

__all__.extend([
    # Core components
    "AdapterRegistry",
    "CallbackRegistry",
    "EventProcessor",
    "StateManager",

    # Adapters
    "BaseAdapter",
    "EVMAdapter",
    "EthereumAdapter",
    "SolanaAdapter",
    "TronAdapter",

    # Storage
    "StorageBackend",
    "InMemoryStorage",
])
