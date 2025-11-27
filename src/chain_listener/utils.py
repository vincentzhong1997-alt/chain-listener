"""Utility functions for the chain listener SDK.

This module provides reusable utility functions for address validation,
format conversion, and other common operations.
"""

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False


def validate_and_format_address(address: str) -> str:
    """Validate and format a blockchain address according to chain standards.

    Args:
        address: The address string to validate and format

    Returns:
        Formatted address (checksum format for EVM chains)

    Raises:
        ValueError: If address format is invalid
    """
    if not address:
        raise ValueError("Address cannot be empty")

    if len(address) < 3:
        raise ValueError("Address must be at least 3 characters")

    # EVM0@lb:!ŒŒ<
    if address.startswith("0x") and len(address) == 42 and WEB3_AVAILABLE:
        try:
            return Web3.to_checksum_address(address)
        except Exception:
            raise ValueError("Invalid EVM address format")

    return address


def is_valid_evm_address(address: str) -> bool:
    """Check if an address is a valid EVM address format.

    Args:
        address: Address to validate

    Returns:
        True if valid EVM address format, False otherwise
    """
    if not WEB3_AVAILABLE:
        return False

    try:
        return Web3.is_address(address)
    except Exception:
        return False


def normalize_evm_address(address: str) -> str:
    """Normalize EVM address to checksum format.

    Args:
        address: EVM address to normalize

    Returns:
        Checksum formatted address

    Raises:
        ValueError: If address is not a valid EVM address
    """
    if not WEB3_AVAILABLE:
        raise ValueError("Web3 not available for address normalization")

    if not Web3.is_address(address):
        raise ValueError("Invalid EVM address format")

    return Web3.to_checksum_address(address)