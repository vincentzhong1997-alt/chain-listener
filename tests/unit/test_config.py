"""Test configuration models following TDD principles."""

import pytest
from typing import Dict, Any
from pydantic import ValidationError

# These tests are written before the implementation exists
# They will fail initially, then we'll implement the code to make them pass


def test_blockchain_config_creation():
    """Test that BlockchainConfig can be created with valid data."""
    # This test will fail until we implement the model
    from chain_listener.models.config import BlockchainConfig

    config_data = {
        "enabled": True,
        "network": "mainnet",
        "weight": 3,
        "polling": {
            "enabled": True,
            "interval": 15,
            "batch_size": 100
        },
        "rpc": {
            "urls": ["https://eth.llamarpc.com"],
            "timeout": 30,
            "retries": 3,
            "strategy": "round_robin"
        }
    }

    config = BlockchainConfig(**config_data)

    assert config.enabled == True
    assert config.network == "mainnet"
    assert config.weight == 3
    assert config.polling.interval == 15
    assert config.polling.batch_size == 100
    assert len(config.rpc.urls) == 1
    assert config.rpc.timeout == 30


def test_blockchain_config_default_values():
    """Test that BlockchainConfig provides sensible defaults."""
    from chain_listener.models.config import BlockchainConfig

    # Minimal configuration should work with defaults
    config = BlockchainConfig(
        rpc={"urls": ["https://eth.llamarpc.com"]}
    )

    assert config.enabled == True  # Default
    assert config.network == "mainnet"  # Default
    assert config.weight == 1  # Default
    assert config.polling.enabled == True  # Default
    assert config.polling.interval == 15  # Default
    assert config.rpc.timeout == 30  # Default


def test_blockchain_config_validation():
    """Test that BlockchainConfig validates invalid inputs."""
    from chain_listener.models.config import BlockchainConfig

    # Invalid network should raise ValidationError
    with pytest.raises(ValidationError):
        BlockchainConfig(
            network="invalid_network",
            rpc={"urls": ["https://eth.llamarpc.com"]}
        )

    # Invalid polling interval should raise ValidationError
    with pytest.raises(ValidationError):
        BlockchainConfig(
            polling={"interval": -1},
            rpc={"urls": ["https://eth.llamarpc.com"]}
        )

    # Invalid RPC timeout should raise ValidationError
    with pytest.raises(ValidationError):
        BlockchainConfig(
            rpc={"urls": ["https://eth.llamarpc.com"], "timeout": -1}
        )


def test_contract_config_creation():
    """Test that ContractConfig can be created with valid data."""
    from chain_listener.models.config import ContractConfig

    config_data = {
        "name": "WBTC",
        "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "abi_path": "./abis/wbtc.json",
        "events": ["Transfer", "Burn", "Mint"]
    }

    config = ContractConfig(**config_data)

    assert config.name == "WBTC"
    assert config.address == "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
    assert config.abi_path == "./abis/wbtc.json"
    assert "Transfer" in config.events
    assert "Burn" in config.events
    assert "Mint" in config.events


def test_contract_config_address_validation():
    """Test that ContractConfig validates Ethereum addresses."""
    from chain_listener.models.config import ContractConfig

    # Valid address should work
    config = ContractConfig(
        name="WBTC",
        address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
    )
    assert config.address == "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"

    # Invalid address should raise ValidationError
    with pytest.raises(ValidationError):
        ContractConfig(address="invalid_address")

    # Empty address should raise ValidationError
    with pytest.raises(ValidationError):
        ContractConfig(address="")


def test_event_processing_config_creation():
    """Test that EventProcessingConfig can be created with valid data."""
    from chain_listener.models.config import EventProcessingConfig

    config_data = {
        "retry": {
            "max_retries": 5,
            "retry_delay": 10
        },
        "deduplication": {
            "strategy": "multi_layer",
            "cache_size": 10000,
            "ttl": 3600
        },
        "error_log": True
    }

    config = EventProcessingConfig(**config_data)

    assert config.retry.max_retries == 5
    assert config.retry.retry_delay == 10
    assert config.deduplication.strategy == "multi_layer"
    assert config.deduplication.cache_size == 10000
    assert config.deduplication.ttl == 3600
    assert config.error_log == True


def test_event_processing_config_defaults():
    """Test that EventProcessingConfig provides sensible defaults."""
    from chain_listener.models.config import EventProcessingConfig

    # Empty config should use defaults
    config = EventProcessingConfig()

    assert config.retry.max_retries == 3
    assert config.retry.retry_delay == 5
    assert config.deduplication.strategy == "multi_layer"
    assert config.deduplication.cache_size == 10000
    assert config.deduplication.ttl == 3600
    assert config.error_log == True


def test_distributed_config_creation():
    """Test that DistributedConfig can be created with valid data."""
    from chain_listener.models.config import DistributedConfig

    config_data = {
        "cluster": {
            "instance_id": "listener-01",
            "instance_group": "wbtc-listener-group",
            "zone": "us-east-1a",
            "weight": 3
        },
        "coordination": {
            "leader_election": {
                "enabled": True,
                "ttl": 30,
                "lock_timeout": 60
            }
        },
        "load_balancing": {
            "strategy": "weighted",
            "rebalance_interval": 300,
            "health_check_interval": 30
        }
    }

    config = DistributedConfig(**config_data)

    assert config.cluster.instance_id == "listener-01"
    assert config.cluster.instance_group == "wbtc-listener-group"
    assert config.cluster.zone == "us-east-1a"
    assert config.cluster.weight == 3
    assert config.coordination.leader_election.enabled == True
    assert config.coordination.leader_election.ttl == 30
    assert config.load_balancing.strategy == "weighted"
    assert config.load_balancing.rebalance_interval == 300


def test_main_config_creation():
    """Test that MainConfig can be created with valid blockchain configurations."""
    from chain_listener.models.config import MainConfig

    config_data = {
        "blockchains": {
            "ethereum": {
                "enabled": True,
                "network": "mainnet",
                "weight": 3,
                "rpc": {
                    "urls": ["https://eth.llamarpc.com"],
                    "timeout": 30
                },
                "contracts": [
                    {
                        "name": "WBTC",
                        "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                        "events": ["Transfer", "Burn"]
                    }
                ]
            },
            "bsc": {
                "enabled": True,
                "network": "mainnet",
                "weight": 2,
                "rpc": {
                    "urls": ["https://bsc-dataseed.binance.org"]
                }
            }
        },
        "event_processing": {
            "retry": {"max_retries": 3},
            "error_log": True
        }
    }

    config = MainConfig(**config_data)

    # Test blockchain configurations
    assert "ethereum" in config.blockchains
    assert "bsc" in config.blockchains
    assert config.blockchains["ethereum"].weight == 3
    assert config.blockchains["bsc"].weight == 2
    assert len(config.blockchains["ethereum"].contracts) == 1
    assert config.blockchains["ethereum"].contracts[0].name == "WBTC"

    # Test event processing configuration
    assert config.event_processing.retry.max_retries == 3
    assert config.event_processing.error_log == True


def test_config_from_yaml():
    """Test that configuration can be loaded from YAML string."""
    import yaml
    from chain_listener.models.config import MainConfig

    yaml_config = """
blockchains:
  ethereum:
    enabled: true
    network: mainnet
    weight: 3
    rpc:
      urls:
        - "https://eth.llamarpc.com"
      timeout: 30
    contracts:
      - name: "WBTC"
        address: "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
        events: ["Transfer", "Burn"]

event_processing:
  retry:
    max_retries: 3
    retry_delay: 5
  error_log: true
"""

    config_dict = yaml.safe_load(yaml_config)
    config = MainConfig(**config_dict)

    assert config.blockchains["ethereum"].enabled == True
    assert config.blockchains["ethereum"].weight == 3
    assert len(config.blockchains["ethereum"].contracts) == 1
    assert config.event_processing.retry.max_retries == 3


def test_config_validation_edge_cases():
    """Test edge cases in configuration validation."""
    from chain_listener.models.config import MainConfig

    # Empty blockchains should raise error
    with pytest.raises(ValidationError):
        MainConfig(blockchains={})

    # Invalid blockchain names should raise error
    with pytest.raises(ValidationError):
        MainConfig(blockchains={
            "": {"enabled": True, "rpc": {"urls": ["https://eth.llamarpc.com"]}}
        })

    # Invalid deduplication strategy should raise error
    with pytest.raises(ValidationError):
        MainConfig(
            blockchains={"ethereum": {"enabled": True, "rpc": {"urls": ["https://eth.llamarpc.com"]}}},
            event_processing={"deduplication": {"strategy": "invalid_strategy"}}
        )


def test_config_merging():
    """Test that configuration merging works correctly."""
    from chain_listener.models.config import MainConfig, merge_configs

    base_config = {
        "blockchains": {
            "ethereum": {
                "enabled": True,
                "weight": 1,
                "rpc": {"urls": ["https://eth.llamarpc.com"]}
            }
        }
    }

    override_config = {
        "blockchains": {
            "ethereum": {
                "weight": 3,  # Override weight
                "contracts": [  # Add contracts
                    {
                        "name": "WBTC",
                        "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
                    }
                ]
            }
        }
    }

    # Merge configurations
    merged_config = merge_configs(base_config, override_config)
    config = MainConfig(**merged_config)

    assert config.blockchains["ethereum"].enabled == True  # From base
    assert config.blockchains["ethereum"].weight == 3  # Override
    assert len(config.blockchains["ethereum"].contracts) == 1  # From override


@pytest.mark.parametrize("network", ["mainnet", "testnet", "devnet"])
def test_valid_networks(network: str):
    """Test that all valid network values are accepted."""
    from chain_listener.models.config import BlockchainConfig

    config = BlockchainConfig(
        network=network,
        rpc={"urls": ["https://eth.llamarpc.com"]}
    )
    assert config.network == network


@pytest.mark.parametrize("invalid_network", ["invalid", "main", "test", ""])
def test_invalid_networks(invalid_network: str):
    """Test that invalid network values are rejected."""
    from chain_listener.models.config import BlockchainConfig

    with pytest.raises(ValidationError):
        BlockchainConfig(
            network=invalid_network,
            rpc={"urls": ["https://eth.llamarpc.com"]}
        )


@pytest.mark.parametrize("strategy", ["round_robin", "failover", "random"])
def test_valid_rpc_strategies(strategy: str):
    """Test that all valid RPC strategies are accepted."""
    from chain_listener.models.config import BlockchainConfig

    config = BlockchainConfig(
        rpc={"urls": ["https://eth.llamarpc.com"], "strategy": strategy}
    )
    assert config.rpc.strategy == strategy


def test_config_serialization():
    """Test that configuration can be serialized to dict."""
    from chain_listener.models.config import MainConfig

    config_data = {
        "blockchains": {
            "ethereum": {
                "enabled": True,
                "rpc": {"urls": ["https://eth.llamarpc.com"]}
            }
        }
    }

    config = MainConfig(**config_data)
    serialized = config.model_dump()

    assert "blockchains" in serialized
    assert "ethereum" in serialized["blockchains"]
    assert serialized["blockchains"]["ethereum"]["enabled"] == True