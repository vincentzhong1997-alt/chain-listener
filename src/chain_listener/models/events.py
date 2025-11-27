"""Event data models for the chain listener SDK.

This module defines all event data classes using Pydantic for type safety
and validation. Events represent blockchain events with rich metadata and
cross-chain support.
"""

import json
import hashlib
from typing import Dict, List, Optional, Union, Any, Set
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from enum import Enum


class EventStatus(str, Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


class EventType(str, Enum):
    """Common event types."""
    TRANSFER = "Transfer"
    BURN = "Burn"
    MINT = "Mint"
    APPROVAL = "Approval"
    SWAP = "Swap"
    DEPOSIT = "Deposit"
    WITHDRAWAL = "Withdrawal"
    CROSS_CHAIN_BURN = "CrossChainBurn"
    CROSS_CHAIN_MINT = "CrossChainMint"
    REQUEST_BURN = "BurnRequest"
    REQUEST_MINT = "MintRequest"


class ChainName(str, Enum):
    """Supported blockchain names."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    SOLANA = "solana"
    TRON = "tron"
    KAVA = "kava"
    OSMOSIS = "osmosis"
    BASE = "base"


class ErrorInfo(BaseModel):
    """Error information for failed event processing."""
    error_type: str = Field(..., description="Type of error")
    error_message: str = Field(..., description="Error message")
    error_traceback: Optional[str] = Field(default=None, description="Full error traceback")
    failed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the error occurred")
    retry_count: int = Field(default=0, description="Number of retries attempted")


class ProcessingInfo(BaseModel):
    """Event processing information."""
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the event was processed")
    status: EventStatus = Field(default=EventStatus.PENDING, description="Processing status")
    retry_count: int = Field(default=0, ge=0, le=10, description="Number of retries attempted")
    processing_duration_ms: Optional[int] = Field(default=None, ge=0, description="Processing time in milliseconds")
    error_info: Optional[ErrorInfo] = Field(default=None, description="Error information if processing failed")
    processor_id: Optional[str] = Field(default=None, description="ID of the processor that handled the event")

    @validator("error_info")
    def validate_error_info_consistency(cls, v, values):
        """Ensure error_info is present when status is FAILED."""
        if values.get("status") == EventStatus.FAILED and v is None:
            raise ValueError("error_info is required when status is FAILED")
        return v


class BlockchainEvent(BaseModel):
    """Base blockchain event data model."""
    event_type: str = Field(..., min_length=1, max_length=100, description="Event type name")
    contract_address: str = Field(..., description="Contract address that emitted the event")
    chain_name: ChainName = Field(..., description="Blockchain name")
    transaction_hash: str = Field(..., description="Transaction hash")
    block_number: Optional[int] = Field(default=None, ge=0, description="Block number")
    block_timestamp: Optional[int] = Field(default=None, ge=0, description="Block timestamp (Unix timestamp)")
    log_index: Optional[int] = Field(default=None, ge=0, description="Log index in transaction")
    transaction_index: Optional[int] = Field(default=None, ge=0, description="Transaction index in block")
    from_address: Optional[str] = Field(default=None, description="From address")
    to_address: Optional[str] = Field(default=None, description="To address")
    value: Optional[Union[str, int, float]] = Field(default=None, description="Event value")
    event_signature: Optional[str] = Field(default=None, description="Event signature")
    raw_event: Optional[Dict[str, Any]] = Field(default=None, description="Raw event data from blockchain")
    processing_info: ProcessingInfo = Field(default_factory=ProcessingInfo, description="Processing information")
    metadata: Dict[str, Any] = Field(
        default_factory=lambda: {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": 0,
            "source": "blockchain_listener",
            "version": "1.0"
        },
        description="Additional event metadata"
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True

    @validator("transaction_hash")
    def validate_transaction_hash(cls, v):
        """Validate transaction hash format."""
        if not v or len(v) < 10:
            raise ValueError("Transaction hash must be at least 10 characters")
        return v

    @validator("contract_address")
    def validate_contract_address(cls, v):
        """Validate contract address format."""
        if not v:
            raise ValueError("Contract address cannot be empty")

        # For non-EVM chains, just check non-empty
        if len(v) < 3:
            raise ValueError("Contract address must be at least 3 characters")

        return v.lower() if v.startswith("0x") else v

    @validator("block_number")
    def validate_block_number(cls, v):
        """Validate block number."""
        if v is not None and v < 0:
            raise ValueError("Block number cannot be negative")
        return v

    @validator("block_timestamp")
    def validate_block_timestamp(cls, v):
        """Validate block timestamp."""
        if v is not None and v < 0:
            raise ValueError("Block timestamp cannot be negative")
        return v

    def get_event_hash(self) -> str:
        """Generate a unique hash for this event."""
        hash_data = {
            "transaction_hash": self.transaction_hash,
            "log_index": self.log_index or 0,
            "block_number": self.block_number or 0,
            "chain_name": self.chain_name,
            "event_type": self.event_type,
            "contract_address": self.contract_address
        }

        hash_string = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(hash_string.encode()).hexdigest()

    def is_duplicate_of(self, other: 'BlockchainEvent') -> bool:
        """Check if this event is a duplicate of another event."""
        return self.get_event_hash() == other.get_event_hash()

    def mark_processed(self, status: EventStatus = EventStatus.SUCCESS, processor_id: Optional[str] = None) -> None:
        """Mark this event as processed."""
        self.processing_info.status = status
        self.processing_info.processed_at = datetime.now(timezone.utc)
        if processor_id:
            self.processing_info.processor_id = processor_id
        self.metadata["processed_at"] = self.processing_info.processed_at.isoformat()

    def mark_failed(self, error: Exception, processor_id: Optional[str] = None) -> None:
        """Mark this event as failed."""
        self.processing_info.status = EventStatus.FAILED
        self.processing_info.error_info = ErrorInfo(
            error_type=type(error).__name__,
            error_message=str(error),
            failed_at=datetime.now(timezone.utc),
            retry_count=self.processing_info.retry_count
        )
        if processor_id:
            self.processing_info.processor_id = processor_id
        self.metadata["processed_at"] = self.processing_info.processed_at.isoformat()

    def increment_retry_count(self) -> None:
        """Increment the retry count."""
        self.processing_info.retry_count += 1
        self.metadata["retry_count"] = self.processing_info.retry_count

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        data = self.model_dump()
        data["event_hash"] = self.get_event_hash()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BlockchainEvent':
        """Create event from dictionary."""
        if "event_hash" in data:
            data.pop("event_hash")
        return cls(**data)


class ContractEvent(BlockchainEvent):
    """Smart contract event with decoded parameters."""
    contract_name: str = Field(..., min_length=1, max_length=100, description="Contract name")
    abi_name: str = Field(..., min_length=1, max_length=100, description="ABI function name")
    decoded_params: Dict[str, Any] = Field(default_factory=dict, description="Decoded event parameters")

    def get_param(self, name: str, default: Any = None) -> Any:
        """Get a decoded parameter by name."""
        return self.decoded_params.get(name, default)

    def has_param(self, name: str) -> bool:
        """Check if a decoded parameter exists."""
        return name in self.decoded_params


class CrossChainEvent(BlockchainEvent):
    """Cross-chain event with additional cross-chain metadata."""
    source_chain: ChainName = Field(..., description="Source blockchain")
    target_chain: ChainName = Field(..., description="Target blockchain")
    cross_chain_hash: Optional[str] = Field(default=None, description="Cross-chain transaction hash")
    amount: str = Field(..., min_length=1, description="Cross-chain amount (as string to preserve precision)")
    requester: str = Field(..., min_length=1, description="Address requesting the cross-chain operation")
    bridge_contract: Optional[str] = Field(default=None, description="Bridge contract address")
    relay_data: Optional[Dict[str, Any]] = Field(default=None, description="Additional relay data")

    @validator("amount")
    def validate_amount(cls, v):
        """Validate amount format."""
        if not v:
            raise ValueError("Amount cannot be empty")
        # Ensure it's a valid numeric string
        try:
            float(v)
        except ValueError:
            raise ValueError(f"Amount must be a valid number string: {v}")
        return v

    @validator("requester")
    def validate_requester(cls, v):
        """Validate requester address."""
        if not v:
            raise ValueError("Requester address cannot be empty")
        return v

    def is_burn_event(self) -> bool:
        """Check if this is a burn event."""
        return "burn" in self.event_type.lower()

    def is_mint_event(self) -> bool:
        """Check if this is a mint event."""
        return "mint" in self.event_type.lower()

    def get_amount_as_float(self) -> float:
        """Get amount as float."""
        return float(self.amount)


class EventBatch(BaseModel):
    """A batch of events for processing."""
    events: List[BlockchainEvent] = Field(default_factory=list, description="List of events")
    batch_id: str = Field(default_factory=lambda: f"batch_{datetime.now(timezone.utc).timestamp()}", description="Batch identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Batch creation time")

    def add_event(self, event: BlockchainEvent) -> None:
        """Add an event to the batch."""
        self.events.append(event)

    def get_event_hashes(self) -> List[str]:
        """Get all event hashes in the batch."""
        return [event.get_event_hash() for event in self.events]

    def get_unique_events(self) -> List[BlockchainEvent]:
        """Get unique events from the batch (remove duplicates)."""
        seen_hashes: Set[str] = set()
        unique_events: List[BlockchainEvent] = []

        for event in self.events:
            event_hash = event.get_event_hash()
            if event_hash not in seen_hashes:
                seen_hashes.add(event_hash)
                unique_events.append(event)

        return unique_events

    def get_unique_event_hashes(self) -> Set[str]:
        """Get set of unique event hashes."""
        return set(self.get_event_hashes())

    def filter_by_status(self, status: EventStatus) -> List[BlockchainEvent]:
        """Filter events by processing status."""
        return [event for event in self.events if event.processing_info.status == status]

    def get_failed_events(self) -> List[BlockchainEvent]:
        """Get all failed events."""
        return self.filter_by_status(EventStatus.FAILED)

    def get_successful_events(self) -> List[BlockchainEvent]:
        """Get all successful events."""
        return self.filter_by_status(EventStatus.SUCCESS)

    def get_pending_events(self) -> List[BlockchainEvent]:
        """Get all pending events."""
        return self.filter_by_status(EventStatus.PENDING)

    def get_events_by_chain(self, chain_name: ChainName) -> List[BlockchainEvent]:
        """Get events for a specific chain."""
        return [event for event in self.events if event.chain_name == chain_name]

    def get_events_by_contract(self, contract_address: str) -> List[BlockchainEvent]:
        """Get events for a specific contract."""
        normalized_address = contract_address.lower()
        return [
            event for event in self.events
            if event.contract_address.lower() == normalized_address
        ]

    def get_events_by_type(self, event_type: str) -> List[BlockchainEvent]:
        """Get events of a specific type."""
        return [event for event in self.events if event.event_type == event_type]

    def sort_by_block(self) -> 'EventBatch':
        """Sort events by block number (and by log index within blocks)."""
        sorted_events = sorted(
            self.events,
            key=lambda e: (e.block_number or 0, e.log_index or 0)
        )
        self.events = sorted_events
        return self

    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics."""
        total_events = len(self.events)
        successful_events = len(self.get_successful_events())
        failed_events = len(self.get_failed_events())
        pending_events = len(self.get_pending_events())

        # Events by chain
        chains: Dict[str, int] = {}
        for event in self.events:
            chains[event.chain_name] = chains.get(event.chain_name, 0) + 1

        # Events by type
        event_types: Dict[str, int] = {}
        for event in self.events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1

        return {
            "batch_id": self.batch_id,
            "total_events": total_events,
            "successful_events": successful_events,
            "failed_events": failed_events,
            "pending_events": pending_events,
            "success_rate": successful_events / total_events if total_events > 0 else 0,
            "chains": chains,
            "event_types": event_types,
            "created_at": self.created_at.isoformat()
        }

    def mark_all_processed(self, status: EventStatus = EventStatus.SUCCESS, processor_id: Optional[str] = None) -> None:
        """Mark all events in the batch as processed."""
        for event in self.events:
            event.mark_processed(status, processor_id)

    def retry_failed_events(self) -> List[BlockchainEvent]:
        """Retry failed events and return them."""
        failed_events = self.get_failed_events()
        for event in failed_events:
            event.increment_retry_count()
            event.processing_info.status = EventStatus.RETRY
        return failed_events

    def get_events_for_retry(self, max_retries: int = 3) -> List[BlockchainEvent]:
        """Get events that should be retried."""
        return [
            event for event in self.get_failed_events()
            if event.processing_info.retry_count < max_retries
        ]

    def split_by_chain(self) -> Dict[ChainName, 'EventBatch']:
        """Split batch into separate batches by chain."""
        chain_batches: Dict[ChainName, EventBatch] = {}

        for event in self.events:
            if event.chain_name not in chain_batches:
                chain_batches[event.chain_name] = EventBatch(
                    events=[],
                    batch_id=f"{self.batch_id}_{event.chain_name}"
                )
            chain_batches[event.chain_name].add_event(event)

        return chain_batches


# Utility functions for event processing
def create_event_from_web3_log(log_data: Dict[str, Any], chain_name: ChainName) -> BlockchainEvent:
    """Create a BlockchainEvent from Web3 log data."""
    return BlockchainEvent(
        event_type=log_data.get("event", "Unknown"),
        contract_address=log_data.get("address", ""),
        chain_name=chain_name,
        transaction_hash=log_data.get("transactionHash", ""),
        block_number=log_data.get("blockNumber"),
        block_timestamp=log_data.get("blockTimestamp"),
        log_index=log_data.get("logIndex"),
        transaction_index=log_data.get("transactionIndex"),
        from_address=log_data.get("args", {}).get("from"),
        to_address=log_data.get("args", {}).get("to"),
        value=str(log_data.get("args", {}).get("value", "0")),
        raw_event=log_data
    )


def calculate_event_signature(event: Dict[str, Any]) -> str:
    """Calculate event signature from event data."""
    if "signature" in event:
        return event["signature"]

    # Calculate from event name and parameters
    event_name = event.get("event", "")
    if not event_name:
        return ""

    # For standard events, return common signatures
    if event_name == "Transfer":
        return "Transfer(address,address,uint256)"
    elif event_name == "Burn":
        return "Burn(address,uint256)"
    elif event_name == "Mint":
        return "Mint(address,uint256)"
    elif event_name == "Approval":
        return "Approval(address,address,uint256)"
    else:
        return event_name


def normalize_address(address: str) -> str:
    """Normalize blockchain address format."""
    if not address:
        return ""

    # Remove any whitespace and convert to lowercase
    address = address.strip().lower()

    # Add 0x prefix if missing for Ethereum-like addresses
    if len(address) == 40 and not address.startswith("0x"):
        address = "0x" + address

    return address


def validate_event_chain(event: BlockchainEvent, expected_chain: ChainName) -> bool:
    """Validate that an event belongs to the expected chain."""
    return event.chain_name == expected_chain


def filter_events_by_contracts(events: List[BlockchainEvent], contract_addresses: List[str]) -> List[BlockchainEvent]:
    """Filter events by contract addresses."""
    normalized_addresses = [normalize_address(addr) for addr in contract_addresses]

    return [
        event for event in events
        if normalize_address(event.contract_address) in normalized_addresses
    ]


def filter_events_by_time_range(
    events: List[BlockchainEvent],
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None
) -> List[BlockchainEvent]:
    """Filter events by timestamp range."""
    filtered_events = []

    for event in events:
        if event.block_timestamp is None:
            continue

        if start_timestamp and event.block_timestamp < start_timestamp:
            continue

        if end_timestamp and event.block_timestamp > end_timestamp:
            continue

        filtered_events.append(event)

    return filtered_events


def deduplicate_events(events: List[BlockchainEvent]) -> List[BlockchainEvent]:
    """Remove duplicate events from a list."""
    seen_hashes: Set[str] = set()
    unique_events: List[BlockchainEvent] = []

    for event in events:
        event_hash = event.get_event_hash()
        if event_hash not in seen_hashes:
            seen_hashes.add(event_hash)
            unique_events.append(event)

    return unique_events