"""General validation utilities.

This module provides reusable validation functions for common data types
and patterns used throughout the chain listener SDK.
"""

import re
from typing import Any, Optional, Union


def is_non_empty_string(value: Any) -> bool:
    """Check if value is a non-empty string.

    Args:
        value: Value to check

    Returns:
        True if value is a non-empty string, False otherwise
    """
    return isinstance(value, str) and len(value.strip()) > 0


def is_positive_integer(value: Any) -> bool:
    """Check if value is a positive integer.

    Args:
        value: Value to check

    Returns:
        True if value is a positive integer, False otherwise
    """
    try:
        return isinstance(value, int) and value > 0
    except (ValueError, TypeError):
        return False


def is_non_negative_integer(value: Any) -> bool:
    """Check if value is a non-negative integer.

    Args:
        value: Value to check

    Returns:
        True if value is a non-negative integer, False otherwise
    """
    try:
        return isinstance(value, int) and value >= 0
    except (ValueError, TypeError):
        return False


def is_valid_url(value: str) -> bool:
    """Check if value is a valid URL.

    Args:
        value: URL string to validate

    Returns:
        True if valid URL, False otherwise
    """
    if not isinstance(value, str) or not value:
        return False

    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    return url_pattern.match(value) is not None


def is_valid_hash(value: str, expected_length: Optional[int] = None) -> bool:
    """Check if value is a valid hexadecimal hash.

    Args:
        value: Hash string to validate
        expected_length: Expected length of hash (without 0x prefix)

    Returns:
        True if valid hash, False otherwise
    """
    if not isinstance(value, str):
        return False

    # Remove 0x prefix if present
    if value.startswith('0x'):
        value = value[2:]

    # Check if all characters are hexadecimal
    if not re.match(r'^[a-fA-F0-9]+$', value):
        return False

    # Check length if specified
    if expected_length is not None:
        return len(value) == expected_length

    return len(value) > 0


def validate_in_range(
    value: Union[int, float],
    min_val: Optional[Union[int, float]] = None,
    max_val: Optional[Union[int, float]] = None,
    field_name: str = "value"
) -> None:
    """Validate that value is within specified range.

    Args:
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        field_name: Name of the field for error messages

    Raises:
        ValueError: If value is out of range
    """
    if min_val is not None and value < min_val:
        raise ValueError(f"{field_name} must be >= {min_val}, got {value}")

    if max_val is not None and value > max_val:
        raise ValueError(f"{field_name} must be <= {max_val}, got {value}")


def validate_length(
    value: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    field_name: str = "value"
) -> None:
    """Validate string length constraints.

    Args:
        value: String value to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        field_name: Name of the field for error messages

    Raises:
        ValueError: If length constraints are violated
    """
    length = len(value)

    if min_length is not None and length < min_length:
        raise ValueError(f"{field_name} must be at least {min_length} characters, got {length}")

    if max_length is not None and length > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters, got {length}")


def is_valid_ethereum_chain_id(chain_id: Union[int, str]) -> bool:
    """Check if value is a valid Ethereum chain ID.

    Args:
        chain_id: Chain ID to validate

    Returns:
        True if valid chain ID, False otherwise
    """
    try:
        chain_id_int = int(chain_id)
        return chain_id_int > 0 and chain_id_int <= 2**32 - 1
    except (ValueError, TypeError):
        return False