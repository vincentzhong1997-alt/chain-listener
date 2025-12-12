"""Test event data models following TDD principles."""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any

# These tests are written before implementation exists
# They will fail initially, then we'll implement the code to make them pass


def test_blockchain_event_creation():
    """Test that BlockchainEvent can be created with valid data."""
    from chain_listener.models.events import BlockchainEvent

    event_data = {
        "event_type": "Transfer",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "block_number": 18500000,
        "block_timestamp": 1640000000,
        "log_index": 5,
        "transaction_index": 10,
        "from_address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        "to_address": "0x1234567890123456789012345678901234567890",
        "value": "1000000000000000000",
        "event_signature": "Transfer(address,address,uint256)",
        "raw_event": {
            "data": "0x...",
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x000000000000000000000000abcdefabcdefabcdefabcdefabcdefabcdefabcd",
                "0x0000000000000000000000001234567890123456789012345678901234567890"
            ]
        }
    }

    event = BlockchainEvent(**event_data)

    assert event.event_type == "Transfer"
    assert event.contract_address == "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
    assert event.chain_name == "ethereum"
    assert event.transaction_hash == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    assert event.block_number == 18500000
    assert event.log_index == 5
    assert event.transaction_index == 10
    assert event.from_address == "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
    assert event.to_address == "0x1234567890123456789012345678901234567890"
    assert event.value == "1000000000000000000"
    assert event.event_signature == "Transfer(address,address,uint256)"


def test_blockchain_event_validation():
    """Test that BlockchainEvent validates required fields."""
    from chain_listener.models.events import BlockchainEvent

    # Missing required fields should raise ValidationError
    with pytest.raises(ValueError):  # Pydantic raises ValueError for validation errors
        BlockchainEvent()

    # Invalid transaction hash should raise ValidationError
    with pytest.raises(ValueError):
        BlockchainEvent(
            transaction_hash="short",  # Too short to pass validation
            contract_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
            chain_name="ethereum",
            event_type="Transfer"
        )

    # Invalid contract address should raise ValidationError
    with pytest.raises(ValueError):
        BlockchainEvent(
            transaction_hash="0x" + "0" * 64,
            contract_address="0xinvalid",  # Invalid EVM format
            chain_name="ethereum",
            event_type="Transfer"
        )

    # Negative block number should raise ValidationError
    with pytest.raises(ValueError):
        BlockchainEvent(
            transaction_hash="0x" + "0" * 64,
            contract_address="0x" + "1" * 40,
            chain_name="ethereum",
            event_type="Transfer",
            block_number=-1
        )


def test_blockchain_event_defaults():
    """Test that BlockchainEvent provides sensible defaults."""
    from chain_listener.models.events import BlockchainEvent

    # Minimal event should work with defaults
    event = BlockchainEvent(
        transaction_hash="0x" + "0" * 64,
        contract_address="0x" + "1" * 40,
        chain_name="ethereum",
        event_type="Transfer"
    )

    assert event.block_number is None  # Optional
    assert event.block_timestamp is None  # Optional
    assert event.log_index is None  # Optional
    assert event.transaction_index is None  # Optional
    assert event.from_address is None  # Optional
    assert event.to_address is None  # Optional
    assert event.value is None  # Optional
    assert event.event_signature is None  # Optional


def test_contract_event_creation():
    """Test that ContractEvent can be created with valid data."""
    from chain_listener.models.events import ContractEvent

    event_data = {
        "event_type": "Transfer",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x" + "0" * 64,
        "block_number": 18500000,
        "contract_name": "WBTC",
        "abi_name": "ERC20",
        "decoded_params": {
            "from": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "to": "0x1234567890123456789012345678901234567890",
            "value": 1000000000000000000
        }
    }

    event = ContractEvent(**event_data)

    assert event.contract_name == "WBTC"
    assert event.abi_name == "ERC20"
    assert "from" in event.decoded_params
    assert event.decoded_params["value"] == 1000000000000000000


def test_contract_event_inheritance():
    """Test that ContractEvent inherits from BlockchainEvent."""
    from chain_listener.models.events import ContractEvent, BlockchainEvent

    event = ContractEvent(
        transaction_hash="0x" + "0" * 64,
        contract_address="0x" + "1" * 40,
        chain_name="ethereum",
        event_type="Transfer",
        contract_name="TestContract",
        abi_name="Transfer"
    )

    assert isinstance(event, BlockchainEvent)
    assert hasattr(event, 'contract_name')
    assert hasattr(event, 'abi_name')
    assert hasattr(event, 'decoded_params')


def test_cross_chain_event_creation():
    """Test that CrossChainEvent can be created with valid data."""
    from chain_listener.models.events import CrossChainEvent

    event_data = {
        "event_type": "CrossChainBurn",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x" + "0" * 64,
        "block_number": 18500000,
        "source_chain": "ethereum",
        "target_chain": "bsc",  # Use supported chain
        "cross_chain_hash": "btc_txid_1234567890abcdef",
        "amount": "100000000",  # 1 WBTC in satoshis
        "requester": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
    }

    event = CrossChainEvent(**event_data)

    assert event.source_chain == "ethereum"
    assert event.target_chain == "bsc"
    assert event.cross_chain_hash == "btc_txid_1234567890abcdef"
    assert event.amount == "100000000"
    assert event.requester == "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"


def test_cross_chain_event_validation():
    """Test that CrossChainEvent validates cross-chain specific fields."""
    from chain_listener.models.events import CrossChainEvent

    # Missing source_chain should raise ValidationError
    with pytest.raises(ValueError):
        CrossChainEvent(
            transaction_hash="0x" + "0" * 64,
            contract_address="0x" + "1" * 40,
            chain_name="ethereum",
            event_type="CrossChainBurn",
            target_chain="bitcoin"
        )

    # Missing target_chain should raise ValidationError
    with pytest.raises(ValueError):
        CrossChainEvent(
            transaction_hash="0x" + "0" * 64,
            contract_address="0x" + "1" * 40,
            chain_name="ethereum",
            event_type="CrossChainBurn",
            source_chain="ethereum"
        )

    # Empty amount should raise ValidationError
    with pytest.raises(ValueError):
        CrossChainEvent(
            transaction_hash="0x" + "0" * 64,
            contract_address="0x" + "1" * 40,
            chain_name="ethereum",
            event_type="CrossChainBurn",
            source_chain="ethereum",
            target_chain="bitcoin",
            amount=""
        )


def test_event_hash_generation():
    """Test that event hash generation is consistent."""
    from chain_listener.models.events import BlockchainEvent

    # Create two identical events
    event_data = {
        "event_type": "Transfer",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "block_number": 18500000,
        "log_index": 5
    }

    event1 = BlockchainEvent(**event_data)
    event2 = BlockchainEvent(**event_data)

    # Hashes should be identical
    hash1 = event1.get_event_hash()
    hash2 = event2.get_event_hash()

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex length
    assert all(c in '0123456789abcdef' for c in hash1)


def test_event_hash_uniqueness():
    """Test that different events produce different hashes."""
    from chain_listener.models.events import BlockchainEvent

    base_data = {
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "block_number": 18500000,
        "log_index": 5
    }

    event1 = BlockchainEvent(event_type="Transfer", **base_data)
    event2 = BlockchainEvent(event_type="Burn", **base_data)

    # Create a modified version for event3
    event3_data = base_data.copy()
    event3_data["log_index"] = 6
    event3 = BlockchainEvent(event_type="Transfer", **event3_data)

    hash1 = event1.get_event_hash()
    hash2 = event2.get_event_hash()
    hash3 = event3.get_event_hash()

    # All hashes should be different
    assert hash1 != hash2
    assert hash1 != hash3
    assert hash2 != hash3


def test_event_serialization():
    """Test that events can be serialized to dict."""
    from chain_listener.models.events import ContractEvent

    event_data = {
        "event_type": "Transfer",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x" + "0" * 64,
        "block_number": 18500000,
        "contract_name": "WBTC",
        "abi_name": "Transfer",
        "decoded_params": {"value": 1000000000000000000}
    }

    event = ContractEvent(**event_data)
    serialized = event.model_dump()

    assert serialized["event_type"] == "Transfer"
    assert serialized["contract_address"] == "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
    assert serialized["contract_name"] == "WBTC"
    assert serialized["decoded_params"]["value"] == 1000000000000000000


def test_event_deserialization():
    """Test that events can be deserialized from dict."""
    from chain_listener.models.events import ContractEvent

    event_dict = {
        "event_type": "Transfer",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x" + "0" * 64,
        "block_number": 18500000,
        "contract_name": "WBTC",
        "abi_name": "Transfer",
        "decoded_params": {"value": 1000000000000000000}
    }

    event = ContractEvent(**event_dict)

    assert event.event_type == "Transfer"
    assert event.contract_name == "WBTC"
    assert event.decoded_params["value"] == 1000000000000000000


def test_event_metadata():
    """Test that event metadata is handled correctly."""
    from chain_listener.models.events import BlockchainEvent
    import json

    event_data = {
        "event_type": "Transfer",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x" + "0" * 64,
        "block_number": 18500000,
        "metadata": {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": 0,
            "source": "blockchain_listener",
            "version": "1.0"
        }
    }

    event = BlockchainEvent(**event_data)

    assert "processed_at" in event.metadata
    assert event.metadata["retry_count"] == 0
    assert event.metadata["source"] == "blockchain_listener"
    assert event.metadata["version"] == "1.0"


def test_event_processing_info():
    """Test that event processing information is tracked."""
    from chain_listener.models.events import BlockchainEvent
    from datetime import datetime, timezone

    event_data = {
        "event_type": "Transfer",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x" + "0" * 64,
        "processing_info": {
            "processed_at": datetime.now(timezone.utc),
            "status": "success",
            "retry_count": 0,
            "processing_duration_ms": 150
        }
    }

    event = BlockchainEvent(**event_data)

    assert event.processing_info.status == "success"
    assert event.processing_info.retry_count == 0
    assert event.processing_info.processing_duration_ms == 150
    assert event.processing_info.processed_at is not None


def test_event_error_handling():
    """Test that event error information is stored."""
    from chain_listener.models.events import BlockchainEvent
    from datetime import datetime, timezone

    event_data = {
        "event_type": "Transfer",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "chain_name": "ethereum",
        "transaction_hash": "0x" + "0" * 64,
        "processing_info": {
            "processed_at": datetime.now(timezone.utc),
            "status": "failed",
            "retry_count": 2,
            "error_info": {
                "error_type": "ConnectionError",
                "error_message": "Failed to connect to database",
                "error_traceback": "Traceback...",
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
        }
    }

    event = BlockchainEvent(**event_data)

    assert event.processing_info.status == "failed"
    assert event.processing_info.retry_count == 2
    assert event.processing_info.error_info.error_type == "ConnectionError"
    assert "Failed to connect to database" in event.processing_info.error_info.error_message


@pytest.mark.parametrize("event_type", ["Transfer", "Burn", "Mint", "Approval", "Swap"])
def test_common_event_types(event_type: str):
    """Test that common event types are supported."""
    from chain_listener.models.events import BlockchainEvent

    event = BlockchainEvent(
        event_type=event_type,
        transaction_hash="0x" + "0" * 64,
        contract_address="0x" + "1" * 40,
        chain_name="ethereum"
    )

    assert event.event_type == event_type


@pytest.mark.parametrize("chain_name", ["ethereum", "polygon", "arbitrum", "optimism"])
def test_common_chain_names(chain_name: str):
    """Test that common chain names are supported."""
    from chain_listener.models.events import BlockchainEvent

    event = BlockchainEvent(
        event_type="Transfer",
        transaction_hash="0x" + "0" * 64,
        contract_address="0x" + "1" * 40,
        chain_name=chain_name
    )

    assert event.chain_name == chain_name


def test_event_batch_processing():
    """Test that events can be processed in batches."""
    from chain_listener.models.events import BlockchainEvent, EventBatch

    events = []
    for i in range(5):
        event = BlockchainEvent(
            event_type="Transfer",
            transaction_hash=f"0x{'0' * 60}{i:02x}",
            contract_address="0x" + "1" * 40,
            chain_name="ethereum",
            block_number=18500000 + i
        )
        events.append(event)

    batch = EventBatch(events=events)

    assert len(batch.events) == 5
    assert batch.get_event_hashes() == [event.get_event_hash() for event in events]
    assert batch.get_unique_event_hashes() == set(event.get_event_hash() for event in events)


def test_event_batch_deduplication():
    """Test that event batch can remove duplicates."""
    from chain_listener.models.events import BlockchainEvent, EventBatch

    # Create events with some duplicates
    base_data = {
        "event_type": "Transfer",
        "contract_address": "0x" + "1" * 40,
        "chain_name": "ethereum",
        "transaction_hash": "0x" + "0" * 64,
        "block_number": 18500000,
        "log_index": 5
    }

    events = [
        BlockchainEvent(**base_data),
        BlockchainEvent(**base_data),  # Duplicate
    ]

    # Create different events without parameter conflicts
    event3_data = base_data.copy()
    event3_data["log_index"] = 6
    events.append(BlockchainEvent(**event3_data))  # Different

    event4_data = base_data.copy()
    event4_data["transaction_hash"] = "0x" + "1" * 64
    events.append(BlockchainEvent(**event4_data))  # Different

    batch = EventBatch(events=events)
    unique_events = batch.get_unique_events()

    assert len(unique_events) == 3  # 2 duplicates removed


def test_event_time_series_ordering():
    """Test that events can be ordered by time."""
    from chain_listener.models.events import BlockchainEvent
    from datetime import datetime, timezone

    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    events = []
    for i in range(3):
        event = BlockchainEvent(
            event_type="Transfer",
            transaction_hash=f"0x{'0' * 60}{i:02x}",
            contract_address="0x" + "1" * 40,
            chain_name="ethereum",
            block_number=18500000 + i,
            block_timestamp=int((base_time.timestamp()) + i * 60)  # 1 minute apart
        )
        events.append(event)

    # Sort by block_timestamp
    sorted_events = sorted(events, key=lambda e: e.block_timestamp or 0)

    assert len(sorted_events) == 3
    for i in range(1, len(sorted_events)):
        assert sorted_events[i].block_timestamp >= sorted_events[i-1].block_timestamp


def test_raw_event_creation():
    """Test that RawEvent can be created with valid data."""
    from chain_listener.models.events import RawEvent, ChainType

    raw_event = RawEvent(
        chain_type=ChainType.ETHEREUM,
        block_number=18500000,
        block_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        log_index=5,
        contract_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        raw_data={
            "data": "0x000000000000000000000000000000000000000000000000de0b6b3a7640000",
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x000000000000000000000000abcdefabcdefabcdefabcdefabcdefabcdefabcd",
                "0x0000000000000000000000001234567890123456789012345678901234567890"
            ]
        },
        timestamp=1640000000
    )

    assert raw_event.chain_type == ChainType.ETHEREUM
    assert raw_event.block_number == 18500000
    assert raw_event.block_hash == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    assert raw_event.transaction_hash == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    assert raw_event.log_index == 5
    assert raw_event.contract_address == "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
    assert "data" in raw_event.raw_data
    assert len(raw_event.raw_data["topics"]) == 3
    assert raw_event.timestamp == 1640000000


def test_decoded_event_creation():
    """Test that DecodedEvent can be created with valid data."""
    from chain_listener.models.events import DecodedEvent, ChainType

    decoded_event = DecodedEvent(
        chain_type=ChainType.ETHEREUM,
        contract_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        event_name="Transfer",
        parameters={
            "from": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "to": "0x1234567890123456789012345678901234567890",
            "value": 1000000000000000000
        },
        block_number=18500000,
        transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        log_index=5,
        timestamp=1640000000
    )

    assert decoded_event.chain_type == ChainType.ETHEREUM
    assert decoded_event.contract_address == "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
    assert decoded_event.event_name == "Transfer"
    assert decoded_event.parameters["from"] == "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
    assert decoded_event.parameters["to"] == "0x1234567890123456789012345678901234567890"
    assert decoded_event.parameters["value"] == 1000000000000000000
    assert decoded_event.block_number == 18500000
    assert decoded_event.transaction_hash == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    assert decoded_event.log_index == 5
    assert decoded_event.timestamp == 1640000000


def test_raw_event_different_chain_types():
    """Test RawEvent with different chain types."""
    from chain_listener.models.events import RawEvent, ChainType

    # Test with Solana
    solana_event = RawEvent(
        chain_type=ChainType.SOLANA,
        block_number=150000000,
        block_hash="5j7s8LxXJ5mK8n9Q3pL6V8rH2tE3wA1dS4xY9bN6cZ2gF5vN8mK3pLqR6tE9wQ",
        transaction_hash="2j7s8LxXJ5mK8n9Q3pL6V8rH2tE3wA1dS4xY9bN6cZ2gF5vN8mK3pLqR6tE9wQ",
        log_index=0,
        contract_address="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        raw_data={"chain": "solana"},
        timestamp=1640000000
    )

    assert solana_event.chain_type == ChainType.SOLANA

    # Test with Tron
    tron_event = RawEvent(
        chain_type=ChainType.TRON,
        block_number=45000000,
        block_hash="0000000000000000015c51293bf64f797e03c8c5ce5b1f2c5e3a86a1bfb11b2e0",
        transaction_hash="c1e8250e52209010675505a87528dbb91349d2484da8a2a7a8741c4a5a1b4d49",
        log_index=0,
        contract_address="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        raw_data={"chain": "tron"},
        timestamp=1640000000
    )

    assert tron_event.chain_type == ChainType.TRON