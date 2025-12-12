"""Test utils module following TDD principles."""

import pytest
from chain_listener.utils import (
    # Address utilities
    validate_and_format_address,
    is_valid_evm_address,
    normalize_evm_address,
    is_valid_solana_address,
    is_valid_tron_address,

    # Conversion utilities
    wei_to_ether,
    ether_to_wei,
    hex_to_int,
    int_to_hex,
    normalize_timestamp,

    # Validation utilities
    is_non_empty_string,
    is_positive_integer,
    is_valid_url,
    is_valid_hash,
    validate_in_range,

    # Crypto utilities
    compute_event_hash,
    compute_block_hash,
    hash_string,
    create_deterministic_id,
)


def test_validate_and_format_address():
    """Test address validation and formatting."""
    # Test EVM addresses (will work if Web3 is available, otherwise returns as-is)
    formatted = validate_and_format_address("0x1234567890123456789012345678901234567890")
    assert formatted == "0x1234567890123456789012345678901234567890"

    # Test empty address
    with pytest.raises(ValueError):
        validate_and_format_address("")

    # Test short address (under 3 characters)
    with pytest.raises(ValueError):
        validate_and_format_address("0x")

    # Test addresses without 0x prefix should pass through
    result = validate_and_format_address("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")
    assert result == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def test_is_valid_evm_address():
    """Test EVM address validation."""
    # Valid addresses
    assert is_valid_evm_address("0x1234567890123456789012345678901234567890")
    assert is_valid_evm_address("0xabcdefABCDEF1234567890123456789012345678")

    # Invalid addresses
    assert not is_valid_evm_address("0x123")  # Too short
    assert not is_valid_evm_address("invalid")  # Invalid format
    assert not is_valid_evm_address("")  # Empty


def test_is_valid_solana_address():
    """Test Solana address validation."""
    # Valid Solana address lengths (32-44 chars)
    assert is_valid_solana_address("11111111111111111111111111111112")
    assert is_valid_solana_address("9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM")

    # Invalid addresses
    assert not is_valid_solana_address("")  # Empty
    assert not is_valid_solana_address("short")  # Too short
    assert not is_valid_solana_address("x" * 50)  # Too long


def test_is_valid_tron_address():
    """Test TRON address validation."""
    # Valid TRON addresses
    assert is_valid_tron_address("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")
    assert is_valid_tron_address("TLyqzVGLV1srkB7dToTAEqgDSfPtXRJZYH")

    # Invalid addresses
    assert not is_valid_tron_address("")  # Empty
    assert not is_valid_tron_address("0x1234567890123456789012345678901234567890")  # EVM format
    assert not is_valid_tron_address("TR123")  # Too short
    assert not is_valid_tron_address("TR" + "x" * 50)  # Too long


def test_wei_to_ether():
    """Test wei to ether conversion."""
    assert wei_to_ether(1000000000000000000) == 1.0
    assert wei_to_ether("2000000000000000000") == 2.0
    assert wei_to_ether(500000000000000000) == 0.5

    # Test negative values
    with pytest.raises(ValueError):
        wei_to_ether(-1000000000000000000)


def test_ether_to_wei():
    """Test ether to wei conversion."""
    assert ether_to_wei(1.0) == 1000000000000000000
    assert ether_to_wei("2.5") == 2500000000000000000
    assert ether_to_wei(0) == 0

    # Test negative values
    with pytest.raises(ValueError):
        ether_to_wei(-1.0)


def test_hex_to_int():
    """Test hex to integer conversion."""
    assert hex_to_int("0xFF") == 255
    assert hex_to_int("FF") == 255
    assert hex_to_int("0x123") == 291

    # Test invalid hex
    with pytest.raises(ValueError):
        hex_to_int("invalid")

    with pytest.raises(ValueError):
        hex_to_int("")


def test_int_to_hex():
    """Test integer to hex conversion."""
    assert int_to_hex(255) == "0xFF"
    assert int_to_hex(255, prefix=False) == "FF"
    assert int_to_hex(291) == "0x123"

    # Test negative values
    with pytest.raises(ValueError):
        int_to_hex(-1)


def test_normalize_timestamp():
    """Test timestamp normalization."""
    assert normalize_timestamp(1640995200) == 1640995200
    assert normalize_timestamp("1640995200") == 1640995200
    assert normalize_timestamp(1640995200.5) == 1640995200

    # Test negative timestamps
    with pytest.raises(ValueError):
        normalize_timestamp(-1)


def test_is_valid_url():
    """Test URL validation."""
    # Valid URLs
    assert is_valid_url("https://example.com")
    assert is_valid_url("http://localhost:8545")
    assert is_valid_url("https://api.mainnet.infura.io/v3/123")

    # Invalid URLs
    assert not is_valid_url("")
    assert not is_valid_url("not-a-url")
    assert not is_valid_url("ftp://example.com")  # Only http/https


def test_is_valid_hash():
    """Test hash validation."""
    # Valid hashes
    assert is_valid_hash("abc123")
    assert is_valid_hash("0xabcdef1234567890")
    assert is_valid_hash("1234567890abcdef", expected_length=16)

    # Invalid hashes
    assert not is_valid_hash("")
    assert not is_valid_hash("xyz789")  # Non-hex chars
    assert not is_valid_hash("123", expected_length=4)  # Wrong length


def test_validate_in_range():
    """Test range validation."""
    # Valid ranges
    validate_in_range(5, min_val=0, max_val=10)
    validate_in_range(100, min_val=50)
    validate_in_range(50, max_val=100)

    # Invalid ranges
    with pytest.raises(ValueError):
        validate_in_range(5, min_val=10)

    with pytest.raises(ValueError):
        validate_in_range(15, max_val=10)


def test_compute_event_hash():
    """Test event hash computation."""
    hash1 = compute_event_hash(
        "ethereum",
        "0x1234567890abcdef",
        1,
        "0xabcdef1234567890"
    )

    hash2 = compute_event_hash(
        "ETHEREUM",  # Different case
        "0x1234567890ABCDEF",  # Different case
        1,
        "0xABCDEF1234567890"  # Different case
    )

    # Should be same regardless of case
    assert hash1 == hash2

    # Different parameters should produce different hashes
    hash3 = compute_event_hash(
        "bsc",  # Different chain
        "0x1234567890abcdef",
        1,
        "0xabcdef1234567890"
    )

    assert hash1 != hash3


def test_compute_block_hash():
    """Test block hash computation."""
    hash1 = compute_block_hash("ethereum", 18500000, "0x1234567890abcdef")
    hash2 = compute_block_hash("ETHEREUM", 18500000, "0x1234567890ABCDEF")

    # Should be same regardless of case
    assert hash1 == hash2

    # Different block number should produce different hash
    hash3 = compute_block_hash("ethereum", 18500001, "0x1234567890abcdef")
    assert hash1 != hash3


def test_hash_string():
    """Test string hashing."""
    hash1 = hash_string("hello world")
    hash2 = hash_string("hello world", algorithm="sha256")
    hash3 = hash_string("HELLO WORLD", algorithm="sha256")

    # Same string should produce same hash
    assert hash1 == hash2

    # Different case should produce different hash
    assert hash2 != hash3


def test_create_deterministic_id():
    """Test deterministic ID creation."""
    id1 = create_deterministic_id("ethereum", "0x123", 1)
    id2 = create_deterministic_id("ETHEREUM", "0x123", 1)
    id3 = create_deterministic_id("ethereum", "0x123", 2)

    # Same components (case-insensitive) should produce same ID
    assert id1 == id2

    # Different components should produce different IDs
    assert id1 != id3


def test_utils_module_import():
    """Test that all utilities can be imported."""
    from chain_listener.utils import validate_and_format_address
    from chain_listener.utils.address import validate_and_format_address as addr_validator

    # Both should work
    assert validate_and_format_address == addr_validator