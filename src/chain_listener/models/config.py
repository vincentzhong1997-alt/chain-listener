"""Configuration models for the chain listener SDK.

This module defines all configuration classes using Pydantic for type safety
and validation. Configuration follows a hierarchical structure with sensible
defaults and comprehensive validation.
"""

from typing import Dict, List, Optional, Annotated, Any
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
)
from enum import Enum
import re


class NetworkType(str, Enum):
    """Supported blockchain networks."""
    MAINNET = "mainnet"
    TESTNET = "testnet"
    DEVNET = "devnet"

class RateLimitConfig(BaseModel):
    """Rate limiting configuration for RPC requests."""
    requests_per_second: int = Field(default=10, ge=1, le=1000, description="Maximum requests per second")
    burst_size: int = Field(default=20, ge=1, le=1000, description="Maximum burst size")


class RPCConfig(BaseModel):
    """RPC endpoint configuration."""
    model_config = ConfigDict(validate_assignment=True)

    endpoints: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Endpoint definitions with url/api_key/api_key_header/priority"
    )
    urls: List[str] = Field(default_factory=list, description="RPC endpoint URLs (derived from endpoints)")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers to send with RPC requests")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    retries: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")
    max_block_batch: int = Field(default=10, ge=0, description="batch get events size")
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig, description="Rate limiting configuration")

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v):
        """Validate that all URLs are properly formatted."""
        url_pattern = re.compile(r'^https?://.+')
        for url in v:
            if not url_pattern.match(url):
                raise ValueError(f"Invalid RPC URL format: {url}")
        return v

    @model_validator(mode="after")
    def populate_urls_from_endpoints(self):
        """Populate urls from endpoints if provided and validate existence."""
        # Work on local copies to avoid recursive validation loops
        endpoints = list(self.endpoints) if self.endpoints else []
        urls = list(self.urls) if self.urls else []

        # Normalize priority: smaller number = higher priority; default by order if absent
        normalized_endpoints: List[Dict[str, Any]] = []
        if endpoints:
            for idx, ep in enumerate(endpoints):
                ep_copy = dict(ep)
                if "priority" not in ep_copy or ep_copy["priority"] is None:
                    ep_copy["priority"] = idx + 1
                normalized_endpoints.append(ep_copy)

            # Sort by priority ascending, then original order fallback
            normalized_endpoints.sort(key=lambda item: item.get("priority", 0))
            endpoints = normalized_endpoints

        if endpoints and not urls:
            extracted: List[str] = []
            for ep in endpoints:
                url = ep.get("url")
                if url:
                    extracted.append(url)
            urls = extracted

        if not urls:
            raise ValueError("At least one RPC URL must be provided via endpoints or urls")

        # Assign back without triggering validation recursion
        object.__setattr__(self, "endpoints", endpoints)
        object.__setattr__(self, "urls", urls)
        return self


class PollingConfig(BaseModel):
    """Polling configuration for blockchain event monitoring."""
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable polling")
    interval: int = Field(default=15, ge=1, le=3600, description="Polling interval in seconds")
    batch_size: int = Field(default=100, ge=1, le=10000, description="Batch size for event processing")


class ContractConfig(BaseModel):
    """Smart contract configuration."""
    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(..., min_length=1, max_length=100, description="Contract name")
    address: str = Field(..., description="Contract address")
    abi_path: Optional[str] = Field(default=None, description="Path to contract ABI file")
    events: List[str] = Field(default_factory=list, description="List of events to monitor")

    @field_validator("address")
    @classmethod
    def validate_address(cls, v):
        """Validate Ethereum address format and convert to checksum."""
        if not v:
            raise ValueError("Address cannot be empty")
        # If it's an EVM-style address, enforce EVM rules; otherwise accept as-is
        if v.startswith(("0x", "0X")):
            address_pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
            if not address_pattern.match(v):
                raise ValueError(f"Invalid Ethereum address format: {v}")
            return v.lower()

        return v


class ChainConfig(BaseModel):
    """Configuration for a specific blockchain."""
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable this blockchain")
    # TODO - consider using an Enum for chain_type
    chain_type: str = Field(
        ...,
        description=(
            "Chain type (ethereum/bsc/polygon/arbitrum/optimism/"
            "avalanche/base/kava/solana/tron)"
        ),
    )
    chain_id: Optional[int] = Field(default=None, ge=1, description="Chain ID")
    network: Optional[NetworkType] = Field(default=NetworkType.MAINNET, description="Network type")
    start_block: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional starting block override for initial sync"
    )
    confirmation_blocks: int = Field(default=12, ge=0, description="Number of confirmation blocks")
    polling_interval: int = Field(default=1000, ge=100, description="Polling interval in milliseconds")
    rpc: Annotated[RPCConfig, Field(..., description="RPC configuration for connection management")]
    contracts: Annotated[List[ContractConfig], Field(default_factory=list, description="Smart contracts to monitor")]


class RetryConfig(BaseModel):
    """Retry configuration for event processing."""
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum number of retry attempts")
    retry_delay: int = Field(default=5, ge=0, le=300, description="Delay between retries in seconds")


class EventProcessingConfig(BaseModel):
    """Configuration for event processing."""
    retry: RetryConfig = Field(default_factory=RetryConfig, description="Retry configuration")
    error_log: bool = Field(default=True, description="Enable error logging for processing failures")


class StorageConfig(BaseModel):
    """Storage configuration for persistence."""
    model_config = ConfigDict(validate_assignment=True)

    backend: str = Field(default="memory", description="Storage backend identifier")
    key_prefix: str = Field(default="chain_listener:", description="Key prefix for storage")
    redis_client: Optional[Any] = Field(default=None, description="Optional Redis client")

class GlobalConfig(BaseModel):
    """Global configuration settings."""
    model_config = ConfigDict(validate_assignment=True)

    max_concurrent_processing: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum concurrent processing tasks"
    )
    event_batch_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Event batch processing size"
    )
    callback_error_handling: str = Field(
        default="ignore",
        pattern="^(ignore|retry|stop)$",
        description="Error handling strategy for callbacks"
    )
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARN|ERROR)$",
        description="Logging level"
    )


class ChainListenerConfig(BaseModel):
    """Main configuration for the chain listener SDK."""
    model_config = ConfigDict(validate_assignment=True)

    global_config: GlobalConfig = Field(default_factory=GlobalConfig, description="Global configuration")
    storage: StorageConfig = Field(default_factory=StorageConfig, description="Storage configuration")
    event_processing: EventProcessingConfig = Field(
        default_factory=EventProcessingConfig,
        description="Event processing configuration"
    )
    chains: Dict[str, ChainConfig] = Field(..., min_length=1, description="Blockchain configurations")

    @classmethod
    def from_file(cls, file_path: str) -> 'ChainListenerConfig':
        """Load configuration from YAML file.

        Args:
            file_path: Path to YAML configuration file

        Returns:
            ChainListenerConfig instance

        Raises:
            FileNotFoundError: If configuration file does not exist
            ValueError: If configuration format is invalid
        """
        import yaml
        from pathlib import Path

        config_path = Path(file_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            return cls(**config_data)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")

    def get_enabled_chains(self) -> Dict[str, ChainConfig]:
        """Get enabled blockchain configurations.

        Returns:
            Dictionary of enabled chain configurations
        """
        return {name: config for name, config in self.chains.items() if config.enabled}

    def get_contracts_for_chain(self, chain_name: str) -> Dict[str, ContractConfig]:
        """Get contracts for specific chain.

        Args:
            chain_name: Name of the blockchain

        Returns:
            Dictionary mapping contract names to configurations
        """
        if chain_name not in self.chains:
            return {}

        contracts = {}
        for contract in self.chains[chain_name].contracts:
            contracts[contract.name] = contract
        return contracts
