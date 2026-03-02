"""Generic EVM blockchain adapter.

This adapter reuses the existing Ethereum JSON-RPC implementation and exposes
it as a chain-agnostic EVM adapter for EVM-compatible networks.
"""

from .ethereum import EthereumAdapter


class EVMAdapter(EthereumAdapter):
    """Generic EVM adapter based on the Ethereum adapter implementation."""

