"""Configuration models for the chain listener SDK.

This module defines all configuration classes using Pydantic for type safety
and validation. Configuration follows a hierarchical structure with sensible
defaults and comprehensive validation.
"""

from typing import Dict, List, Optional, Union, Literal, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from enum import Enum
import re


class NetworkType(str, Enum):
    """Supported blockchain networks."""
    MAINNET = "mainnet"
    TESTNET = "testnet"
    DEVNET = "devnet"


class RPCStrategy(str, Enum):
    """RPC endpoint selection strategies."""
    ROUND_ROBIN = "round_robin"
    FAILOVER = "failover"
    RANDOM = "random"




class RPCConfig(BaseModel):
    """RPC endpoint configuration."""
    model_config = ConfigDict(validate_assignment=True)

    urls: List[str] = Field(..., min_length=1, description="RPC endpoint URLs")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    retries: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")
    strategy: RPCStrategy = Field(default=RPCStrategy.ROUND_ROBIN, description="Endpoint selection strategy")

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v):
        """Validate that all URLs are properly formatted."""
        url_pattern = re.compile(r'^https?://.+')
        for url in v:
            if not url_pattern.match(url):
                raise ValueError(f"Invalid RPC URL format: {url}")
        return v


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
        # Ethereum address validation (0x + 40 hex characters)
        address_pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
        if not address_pattern.match(v):
            raise ValueError(f"Invalid Ethereum address format: {v}")

        # Convert to checksum format (requires web3)
        try:
            from web3 import Web3
            return Web3.to_checksum_address(v)
        except ImportError:
            # If web3 is not available, return as lowercase (fallback)
            return v.lower()


class ChainConfig(BaseModel):
    """Configuration for a specific blockchain."""
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable this blockchain")
    chain_type: str = Field(..., description="Chain type (ethereum, bsc, solana, tron)")
    chain_id: Optional[int] = Field(default=None, description="Chain ID for EVM chains")
    confirmation_blocks: int = Field(default=12, ge=0, le=100, description="Number of confirmation blocks")
    polling_interval: int = Field(default=1000, ge=100, le=60000, description="Polling interval in milliseconds")
    rpc_urls: List[Dict[str, Any]] = Field(..., min_length=1, description="RPC endpoint URLs with priorities")
    contracts: List[ContractConfig] = Field(default_factory=list, description="Smart contracts to monitor")
    adapter_config: Optional[Dict[str, Any]] = Field(default=None, description="Adapter-specific configuration overrides")


class RetryConfig(BaseModel):
    """Retry configuration for event processing."""
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum number of retry attempts")
    retry_delay: int = Field(default=5, ge=0, le=300, description="Delay between retries in seconds")


class EventProcessingConfig(BaseModel):
    """Configuration for event processing."""
    retry: RetryConfig = Field(default_factory=RetryConfig, description="Retry configuration")
    error_log: bool = Field(default=True, description="Enable error logging")


class StorageConfig(BaseModel):
    """Storage configuration for persistence."""
    model_config = ConfigDict(validate_assignment=True)

    backend: str = Field(default="redis", description="Storage backend type")
    key_prefix: str = Field(default="chain_listener:", description="Key prefix for storage")
    redis_client: Optional[Any] = Field(default=None, description="Redis client instance")


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

    version: str = Field(default="1.0", description="Configuration version")
    global_config: GlobalConfig = Field(default_factory=GlobalConfig, description="Global configuration")
    storage: StorageConfig = Field(default_factory=StorageConfig, description="Storage configuration")
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


# Utility functions for configuration management
def create_chain_listener_config(config_dict: Dict) -> ChainListenerConfig:
    """Create ChainListenerConfig from dictionary with validation."""
    return ChainListenerConfig(**config_dict)


def validate_chain_listener_config(config_dict: Dict) -> bool:
    """Validate a configuration dictionary."""
    try:
        ChainListenerConfig(**config_dict)
        return True
    except Exception:
        return False