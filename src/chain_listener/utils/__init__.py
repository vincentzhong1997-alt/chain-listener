"""Chain listener SDK utilities.

This package provides utility functions for address validation, data conversion,
validation, and cryptographic operations.
"""

# Address utilities
from .address import (
    validate_and_format_address,
    is_valid_evm_address,
    normalize_evm_address,
    is_valid_solana_address,
    is_valid_tron_address,
)

# Conversion utilities
from .conversion import (
    wei_to_ether,
    ether_to_wei,
    hex_to_int,
    int_to_hex,
    normalize_timestamp,
    bytes_to_hex,
    hex_to_bytes,
)

# Validation utilities
from .validation import (
    is_non_empty_string,
    is_positive_integer,
    is_non_negative_integer,
    is_valid_url,
    is_valid_hash,
    validate_in_range,
    validate_length,
    is_valid_ethereum_chain_id,
)

# Crypto utilities
from .crypto import (
    compute_event_hash,
    compute_block_hash,
    hash_string,
    hash_bytes,
    create_deterministic_id,
    verify_hash,
)

__all__ = [
    # Address utilities
    "validate_and_format_address",
    "is_valid_evm_address",
    "normalize_evm_address",
    "is_valid_solana_address",
    "is_valid_tron_address",

    # Conversion utilities
    "wei_to_ether",
    "ether_to_wei",
    "hex_to_int",
    "int_to_hex",
    "normalize_timestamp",
    "bytes_to_hex",
    "hex_to_bytes",

    # Validation utilities
    "is_non_empty_string",
    "is_positive_integer",
    "is_non_negative_integer",
    "is_valid_url",
    "is_valid_hash",
    "validate_in_range",
    "validate_length",
    "is_valid_ethereum_chain_id",

    # Crypto utilities
    "compute_event_hash",
    "compute_block_hash",
    "hash_string",
    "hash_bytes",
    "create_deterministic_id",
    "verify_hash",
]