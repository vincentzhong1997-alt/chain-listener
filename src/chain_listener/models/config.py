"""Configuration models for the chain listener SDK.

This module defines all configuration classes using Pydantic for type safety
and validation. Configuration follows a hierarchical structure with sensible
defaults and comprehensive validation.
"""

from typing import Dict, List, Optional, Union, Literal
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


class DeduplicationStrategy(str, Enum):
    """Event deduplication strategies."""
    MULTI_LAYER = "multi_layer"
    SINGLE_LAYER = "single"
    DATABASE = "db"


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies for distributed mode."""
    WEIGHTED = "weighted"
    ROUND_ROBIN = "round_robin"
    CONSISTENT_HASH = "consistent_hash"


class EventDistributionStrategy(str, Enum):
    """Event distribution strategies in distributed mode."""
    EVENT_HASH = "event_hash"
    ROUND_ROBIN = "round_robin"
    STICKY = "sticky"


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
        """Validate Ethereum address format."""
        if not v:
            raise ValueError("Address cannot be empty")
        # Ethereum address validation (0x + 40 hex characters)
        address_pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
        if not address_pattern.match(v):
            raise ValueError(f"Invalid Ethereum address format: {v}")
        return v.lower()


class BlockchainConfig(BaseModel):
    """Configuration for a specific blockchain."""
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable this blockchain")
    network: NetworkType = Field(default=NetworkType.MAINNET, description="Network type")
    weight: int = Field(default=1, ge=1, le=100, description="Load balancing weight")
    confirmations: int = Field(default=12, ge=0, le=100, description="Number of confirmations required")
    polling: PollingConfig = Field(default_factory=PollingConfig, description="Polling configuration")
    rpc: RPCConfig = Field(..., description="RPC endpoint configuration")
    contracts: List[ContractConfig] = Field(default_factory=list, description="Smart contracts to monitor")
    filters: Dict[str, Union[str, int]] = Field(
        default_factory=lambda: {
            "from_block": "latest",
            "to_block": "latest"
        },
        description="Event filters"
    )


class RetryConfig(BaseModel):
    """Retry configuration for event processing."""
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum number of retry attempts")
    retry_delay: int = Field(default=5, ge=0, le=300, description="Delay between retries in seconds")


class DeduplicationConfig(BaseModel):
    """Event deduplication configuration."""
    strategy: DeduplicationStrategy = Field(
        default=DeduplicationStrategy.MULTI_LAYER,
        description="Deduplication strategy"
    )
    cache_size: int = Field(default=10000, ge=100, le=1000000, description="Cache size for deduplication")
    ttl: int = Field(default=3600, ge=60, le=86400, description="TTL for cached events in seconds")


class EventProcessingConfig(BaseModel):
    """Configuration for event processing."""
    retry: RetryConfig = Field(default_factory=RetryConfig, description="Retry configuration")
    deduplication: DeduplicationConfig = Field(
        default_factory=DeduplicationConfig,
        description="Deduplication configuration"
    )
    error_log: bool = Field(default=True, description="Enable error logging")


class LeaderElectionConfig(BaseModel):
    """Leader election configuration for distributed mode."""
    enabled: bool = Field(default=True, description="Enable leader election")
    ttl: int = Field(default=30, ge=10, le=300, description="Leader TTL in seconds")
    lock_timeout: int = Field(default=60, ge=30, le=600, description="Lock timeout in seconds")


class CoordinationConfig(BaseModel):
    """Coordination configuration for distributed mode."""
    leader_election: LeaderElectionConfig = Field(
        default_factory=LeaderElectionConfig,
        description="Leader election configuration"
    )


class LoadBalancingConfig(BaseModel):
    """Load balancing configuration for distributed mode."""
    strategy: LoadBalancingStrategy = Field(
        default=LoadBalancingStrategy.WEIGHTED,
        description="Load balancing strategy"
    )
    rebalance_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Rebalance interval in seconds"
    )
    health_check_interval: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Health check interval in seconds"
    )


class ClusterConfig(BaseModel):
    """Cluster configuration for distributed mode."""
    instance_id: str = Field(..., min_length=1, max_length=100, description="Unique instance identifier")
    instance_group: str = Field(..., min_length=1, max_length=100, description="Instance group name")
    zone: Optional[str] = Field(default=None, description="Availability zone")
    weight: int = Field(default=1, ge=1, le=100, description="Instance weight for load balancing")


class DistributedConfig(BaseModel):
    """Configuration for distributed mode."""
    cluster: ClusterConfig = Field(..., description="Cluster configuration")
    coordination: CoordinationConfig = Field(
        default_factory=CoordinationConfig,
        description="Coordination configuration"
    )
    load_balancing: LoadBalancingConfig = Field(
        default_factory=LoadBalancingConfig,
        description="Load balancing configuration"
    )


class StorageConfig(BaseModel):
    """Storage configuration for persistence."""
    mongodb: Dict[str, Union[str, int]] = Field(
        default_factory=lambda: {
            "database": "blockchain_progress",
            "collections": {
                "progress": "listener_progress",
                "instances": "active_instances"
            }
        },
        description="MongoDB configuration"
    )
    redis: Dict[str, Union[str, int]] = Field(
        default_factory=lambda: {
            "cache_ttl": 3600,
            "event_cache_ttl": 300,
            "cache_key_prefix": "block_data_cache_"
        },
        description="Redis configuration"
    )


class MainConfig(BaseModel):
    """Main configuration for the chain listener SDK."""
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )

    blockchains: Dict[str, BlockchainConfig] = Field(..., min_length=1, description="Blockchain configurations")
    event_processing: EventProcessingConfig = Field(
        default_factory=EventProcessingConfig,
        description="Event processing configuration"
    )
    distributed: Optional[DistributedConfig] = Field(default=None, description="Distributed mode configuration")
    storage: StorageConfig = Field(default_factory=StorageConfig, description="Storage configuration")

    @field_validator("blockchains")
    @classmethod
    def validate_blockchains(cls, v):
        """Validate blockchain configurations."""
        if not v:
            raise ValueError("At least one blockchain must be configured")

        for name, config in v.items():
            if not name or not name.strip():
                raise ValueError("Blockchain name cannot be empty")
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', name):
                raise ValueError(f"Invalid blockchain name: {name}")

        return v

    @model_validator(mode='before')
    @classmethod
    def validate_consistency(cls, values):
        """Validate configuration consistency."""
        blockchains = values.get("blockchains", {})
        distributed = values.get("distributed")

        # If distributed mode is enabled, ensure instance configuration is valid
        if distributed and distributed.cluster.instance_id:
            # Check for duplicate instance IDs across blockchains (this would be checked at runtime)
            pass

        return values


# Utility functions for configuration management
def create_main_config(config_dict: Dict) -> MainConfig:
    """Create MainConfig from dictionary with validation."""
    return MainConfig(**config_dict)


def merge_configs(base_config: Dict, override_config: Dict) -> Dict:
    """Merge two configuration dictionaries."""
    merged = base_config.copy()

    for key, value in override_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    return merged


def validate_main_config(config_dict: Dict) -> bool:
    """Validate a configuration dictionary."""
    try:
        MainConfig(**config_dict)
        return True
    except Exception:
        return False


# Configuration presets for common use cases
def get_simple_config() -> Dict:
    """Get a simple standalone configuration preset."""
    return {
        "blockchains": {
            "ethereum": {
                "enabled": True,
                "network": "mainnet",
                "weight": 1,
                "rpc": {
                    "urls": ["https://eth.llamarpc.com"],
                    "timeout": 30
                }
            }
        },
        "event_processing": {
            "retry": {"max_retries": 3, "retry_delay": 5},
            "error_log": True
        }
    }


def get_distributed_config() -> Dict:
    """Get a distributed configuration preset."""
    return {
        "blockchains": {
            "ethereum": {
                "enabled": True,
                "network": "mainnet",
                "weight": 3,
                "confirmations": 12,
                "polling": {"enabled": True, "interval": 15, "batch_size": 100},
                "rpc": {
                    "urls": [
                        "https://mainnet.infura.io/v3/YOUR_PROJECT_ID",
                        "https://eth-mainnet.alchemyapi.io/v2/YOUR_API_KEY"
                    ],
                    "timeout": 30,
                    "retries": 3,
                    "strategy": "round_robin"
                },
                "contracts": [
                    {
                        "name": "WBTC",
                        "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                        "events": ["Transfer", "Burn", "Mint"]
                    }
                ]
            },
            "bsc": {
                "enabled": True,
                "network": "mainnet",
                "weight": 2,
                "rpc": {
                    "urls": ["https://bsc-dataseed.binance.org"],
                    "timeout": 30
                }
            }
        },
        "event_processing": {
            "deduplication": {
                "strategy": "distributed",
                "cache_size": 100000,
                "ttl": 3600
            },
            "retry": {"max_retries": 3, "retry_delay": 5},
            "error_log": True
        },
        "distributed": {
            "cluster": {
                "instance_id": "listener-01",
                "instance_group": "wbtc-listener-prod",
                "weight": 3
            },
            "coordination": {
                "leader_election": {"enabled": True, "ttl": 30, "lock_timeout": 60}
            },
            "load_balancing": {
                "strategy": "weighted",
                "rebalance_interval": 300,
                "health_check_interval": 30
            }
        },
        "storage": {
            "mongodb": {
                "database": "blockchain_progress",
                "collections": {
                    "progress": "listener_progress",
                    "instances": "active_instances"
                }
            },
            "redis": {
                "cache_ttl": 3600,
                "event_cache_ttl": 300,
                "cache_key_prefix": "block_data_cache_"
            }
        }
    }