"""Data conversion utilities.

This module provides utilities for converting between different data formats,
units, and representations commonly used in blockchain applications.
"""

from typing import Union, Any


def wei_to_ether(wei: Union[int, str]) -> float:
    """Convert wei to ether.

    Args:
        wei: Amount in wei

    Returns:
        Amount in ether

    Raises:
        ValueError: If wei is negative
    """
    if isinstance(wei, str):
        try:
            wei = int(wei, 10)
        except ValueError:
            raise ValueError(f"Invalid wei value: {wei}")

    if wei < 0:
        raise ValueError("Wei amount cannot be negative")

    return wei / 1e18


def ether_to_wei(ether: Union[float, int, str]) -> int:
    """Convert ether to wei.

    Args:
        ether: Amount in ether

    Returns:
        Amount in wei

    Raises:
        ValueError: If ether is negative
    """
    if isinstance(ether, str):
        try:
            ether = float(ether)
        except ValueError:
            raise ValueError(f"Invalid ether value: {ether}")

    if ether < 0:
        raise ValueError("Ether amount cannot be negative")

    return int(ether * 1e18)


def hex_to_int(hex_string: str) -> int:
    """Convert hexadecimal string to integer.

    Args:
        hex_string: Hexadecimal string (with or without 0x prefix)

    Returns:
        Integer value

    Raises:
        ValueError: If hex_string is invalid
    """
    if not hex_string:
        raise ValueError("Hex string cannot be empty")

    # Remove 0x prefix if present
    if hex_string.startswith('0x'):
        hex_string = hex_string[2:]

    try:
        return int(hex_string, 16)
    except ValueError:
        raise ValueError(f"Invalid hexadecimal string: {hex_string}")


def int_to_hex(value: int, prefix: bool = True) -> str:
    """Convert integer to hexadecimal string.

    Args:
        value: Integer value to convert
        prefix: Whether to include '0x' prefix

    Returns:
        Hexadecimal string

    Raises:
        ValueError: If value is negative
    """
    if value < 0:
        raise ValueError("Value cannot be negative")

    hex_str = hex(value)[2:].upper()  # Remove '0x' prefix and convert to uppercase
    return f"0x{hex_str}" if prefix else hex_str


def normalize_timestamp(timestamp: Union[int, float, str]) -> int:
    """Normalize timestamp to integer Unix timestamp.

    Args:
        timestamp: Timestamp in various formats

    Returns:
        Integer Unix timestamp

    Raises:
        ValueError: If timestamp is invalid
    """
    if isinstance(timestamp, str):
        try:
            timestamp = float(timestamp)
        except ValueError:
            raise ValueError(f"Invalid timestamp string: {timestamp}")

    if isinstance(timestamp, float):
        timestamp = int(timestamp)

    if timestamp < 0:
        raise ValueError("Timestamp cannot be negative")

    return timestamp


def bytes_to_hex(data: bytes, prefix: bool = True) -> str:
    """Convert bytes to hexadecimal string.

    Args:
        data: Bytes data to convert
        prefix: Whether to include '0x' prefix

    Returns:
        Hexadecimal string representation
    """
    hex_str = data.hex()
    return f"0x{hex_str}" if prefix else hex_str


def hex_to_bytes(hex_string: str) -> bytes:
    """Convert hexadecimal string to bytes.

    Args:
        hex_string: Hexadecimal string (with or without 0x prefix)

    Returns:
        Bytes data

    Raises:
        ValueError: If hex_string is invalid
    """
    if not hex_string:
        return b''

    # Remove 0x prefix if present
    if hex_string.startswith('0x'):
        hex_string = hex_string[2:]

    # Ensure even length
    if len(hex_string) % 2 != 0:
        hex_string = '0' + hex_string

    try:
        return bytes.fromhex(hex_string)
    except ValueError:
        raise ValueError(f"Invalid hexadecimal string: {hex_string}")