"""Cryptography and hashing utilities.

This module provides utilities for hashing, encryption, and other cryptographic
operations commonly used in blockchain applications.
"""

import hashlib
import json
from typing import Any, Union


def compute_event_hash(
    chain_type: str,
    transaction_hash: str,
    log_index: int,
    contract_address: str
) -> str:
    """Compute a unique hash for an event.

    Args:
        chain_type: Type of blockchain (ethereum, bsc, solana, tron)
        transaction_hash: Transaction hash
        log_index: Log index within transaction
        contract_address: Contract address

    Returns:
        Hexadecimal hash of the event data
    """
    # Create a consistent string representation
    event_data = {
        "chain_type": chain_type.lower(),
        "transaction_hash": transaction_hash.lower(),
        "log_index": log_index,
        "contract_address": contract_address.lower()
    }

    # Convert to JSON string with sorted keys for consistency
    event_string = json.dumps(event_data, sort_keys=True, separators=(',', ':'))

    # Compute SHA-256 hash
    return hashlib.sha256(event_string.encode('utf-8')).hexdigest()


def compute_block_hash(
    chain_type: str,
    block_number: int,
    block_hash: str
) -> str:
    """Compute a unique hash for a block.

    Args:
        chain_type: Type of blockchain
        block_number: Block number
        block_hash: Block hash from blockchain

    Returns:
        Hexadecimal hash of the block data
    """
    block_data = {
        "chain_type": chain_type.lower(),
        "block_number": block_number,
        "block_hash": block_hash.lower()
    }

    block_string = json.dumps(block_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(block_string.encode('utf-8')).hexdigest()


def hash_string(data: str, algorithm: str = "sha256") -> str:
    """Hash a string using specified algorithm.

    Args:
        data: String to hash
        algorithm: Hash algorithm ('sha256', 'md5', 'sha1', etc.)

    Returns:
        Hexadecimal hash

    Raises:
        ValueError: If algorithm is not supported
    """
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Hash algorithm '{algorithm}' not supported")

    hasher = hashlib.new(algorithm)
    hasher.update(data.encode('utf-8'))
    return hasher.hexdigest()


def hash_bytes(data: bytes, algorithm: str = "sha256") -> str:
    """Hash bytes using specified algorithm.

    Args:
        data: Bytes to hash
        algorithm: Hash algorithm ('sha256', 'md5', 'sha1', etc.)

    Returns:
        Hexadecimal hash

    Raises:
        ValueError: If algorithm is not supported
    """
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Hash algorithm '{algorithm}' not supported")

    hasher = hashlib.new(algorithm)
    hasher.update(data)
    return hasher.hexdigest()


def create_deterministic_id(*components: Any) -> str:
    """Create a deterministic ID from multiple components.

    Args:
        *components: Components to include in ID generation

    Returns:
        Deterministic hexadecimal ID
    """
    # Convert all components to strings and normalize
    normalized_components = []
    for component in components:
        if isinstance(component, (dict, list)):
            # Sort dictionaries and lists for consistency
            component_str = json.dumps(component, sort_keys=True)
        else:
            component_str = str(component)
        normalized_components.append(component_str.lower())

    # Join components and hash
    combined = "|".join(normalized_components)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def verify_hash(
    data: Union[str, bytes],
    expected_hash: str,
    algorithm: str = "sha256"
) -> bool:
    """Verify that data matches expected hash.

    Args:
        data: Data to verify
        expected_hash: Expected hash value
        algorithm: Hash algorithm used

    Returns:
        True if hash matches, False otherwise
    """
    if isinstance(data, str):
        computed_hash = hash_string(data, algorithm)
    else:
        computed_hash = hash_bytes(data, algorithm)

    return computed_hash.lower() == expected_hash.lower()