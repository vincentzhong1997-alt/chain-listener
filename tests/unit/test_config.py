"""Test configuration models following TDD principles."""

import pytest
from typing import Dict, Any
from pydantic import ValidationError

# These tests are written before the implementation exists
# They will fail initially, then we'll implement the code to make them pass


def test_blockchain_config_creation():
    """Test that ChainConfig can be created with valid data."""
    # This test will fail until we implement the model
    from chain_listener.models.config import ChainConfig

    config_data = {
        "enabled": True,
        "chain_type": "ethereum",
        "chain_id": 1,
        "confirmation_blocks": 12,
        "polling_interval": 15000,
        "rpc": {
            "endpoints": [
                {"url": "https://eth.llamarpc.com"},
                {"url": "https://eth.example.com", "api_key": "secret", "api_key_header": "X-API-KEY"},
            ]
        }
    }

    config = ChainConfig(**config_data)

    assert config.enabled is True
    assert config.chain_type == "ethereum"
    assert config.chain_id == 1
    assert config.confirmation_blocks == 12
    assert config.polling_interval == 15000
    assert len(config.rpc.endpoints) == 2
    assert config.rpc.urls == ["https://eth.llamarpc.com", "https://eth.example.com"]


def test_blockchain_config_default_values():
    """Test that BlockchainConfig provides sensible defaults."""
    from chain_listener.models.config import ChainConfig

    # Minimal configuration should work with defaults
    config = ChainConfig(
        chain_type="ethereum",
        rpc={
            "endpoints": [{"url": "https://eth.llamarpc.com"}]
        }
    )

    assert config.enabled is True  # Default
    assert config.chain_type == "ethereum"
    assert config.chain_id is None  # Default
    assert config.confirmation_blocks == 12  # Default
    assert config.polling_interval == 1000  # Default
    assert len(config.rpc.endpoints) == 1


def test_blockchain_config_validation():
    """Test that BlockchainConfig validates invalid inputs."""
    from chain_listener.models.config import ChainConfig

    # Invalid network should raise ValidationError
    with pytest.raises(ValidationError):
        ChainConfig(
            network="invalid_network",
            rpc={"endpoints": [{"url": "https://eth.llamarpc.com"}]}
        )

    # Invalid polling interval should raise ValidationError
    with pytest.raises(ValidationError):
        ChainConfig(
            polling={"interval": -1},
            rpc={"endpoints": [{"url": "https://eth.llamarpc.com"}]}
        )

    # Invalid RPC timeout should raise ValidationError
    with pytest.raises(ValidationError):
        ChainConfig(
            rpc={"endpoints": [{"url": "https://eth.llamarpc.com"}], "timeout": -1}
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
        "error_log": True
    }

    config = EventProcessingConfig(**config_data)

    assert config.retry.max_retries == 5
    assert config.retry.retry_delay == 10
    assert config.error_log == True


def test_event_processing_config_defaults():
    """Test that EventProcessingConfig provides sensible defaults."""
    from chain_listener.models.config import EventProcessingConfig

    # Empty config should use defaults
    config = EventProcessingConfig()

    assert config.retry.max_retries == 3
    assert config.retry.retry_delay == 5
    assert config.error_log == True


def test_storage_config_creation():
    """Test that StorageConfig can be created with valid data."""
    from chain_listener.models.config import StorageConfig

    config_data = {
        "backend": "redis",
        "key_prefix": "chain_listener:",
        "redis_client": None
    }

    config = StorageConfig(**config_data)

    assert config.backend == "redis"
    assert config.key_prefix == "chain_listener:"


def test_main_config_creation():
    """Test that ChainListenerConfig can be created with valid blockchain configurations."""
    from chain_listener.models.config import ChainListenerConfig

    config_data = {
        "chains": {
            "ethereum": {
                "enabled": True,
                "chain_type": "ethereum",
                "chain_id": 1,
                "confirmation_blocks": 12,
                "polling_interval": 15000,
                "rpc_urls": [
                    {"url": "https://eth.llamarpc.com", "priority": 1}
                ],
                "contracts": [
                    {
                        "name": "WBTC",
                        "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                        "events": ["Transfer", "Burn"]
                    }
                ]
            }
        },
        "global_config": {
            "max_concurrent_processing": 10,
            "event_batch_size": 100,
            "log_level": "INFO"
        }
    }

    config = ChainListenerConfig(**config_data)

    # Test chain configurations
    assert "ethereum" in config.chains
    assert config.chains["ethereum"].chain_type == "ethereum"
    assert len(config.chains["ethereum"].contracts) == 1
    assert config.chains["ethereum"].contracts[0].name == "WBTC"

    # Test global configuration
    assert config.global_config.max_concurrent_processing == 10
    assert config.global_config.event_batch_size == 100


def test_config_from_yaml():
    """Test that configuration can be loaded from YAML string."""
    import yaml
    from chain_listener.models.config import ChainListenerConfig

    yaml_config = """
chains:
  ethereum:
    enabled: true
    chain_type: ethereum
    chain_id: 1
    confirmation_blocks: 12
    polling_interval: 15000
    rpc:
      endpoints:
        - url: "https://eth.llamarpc.com"
    contracts:
      - name: "WBTC"
        address: "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
        events: ["Transfer", "Burn"]

global_config:
  max_concurrent_processing: 10
  event_batch_size: 100
  log_level: "INFO"
"""

    config_dict = yaml.safe_load(yaml_config)
    config = ChainListenerConfig(**config_dict)

    assert config.chains["ethereum"].enabled == True
    assert config.chains["ethereum"].chain_type == "ethereum"
    assert len(config.chains["ethereum"].contracts) == 1
    assert config.global_config.max_concurrent_processing == 10


def test_config_validation_edge_cases():
    """Test edge cases in configuration validation."""
    from chain_listener.models.config import ChainListenerConfig

    # Empty blockchains should raise error
    with pytest.raises(ValidationError):
        ChainListenerConfig(blockchains={})

    # Invalid blockchain names should raise error
    with pytest.raises(ValidationError):
        ChainListenerConfig(blockchains={
            "": {"enabled": True, "rpc": {"urls": ["https://eth.llamarpc.com"]}}
        })

    # Invalid deduplication strategy should raise error
    with pytest.raises(ValidationError):
        ChainListenerConfig(
            blockchains={"ethereum": {"enabled": True, "rpc": {"urls": ["https://eth.llamarpc.com"]}}},
            event_processing={"deduplication": {"strategy": "invalid_strategy"}}
        )




@pytest.mark.parametrize("chain_type", ["ethereum", "polygon", "solana", "tron"])
def test_valid_chain_types(chain_type: str):
    """Test that all valid chain type values are accepted."""
    from chain_listener.models.config import ChainConfig

    config = ChainConfig(
        chain_type=chain_type,
        rpc_urls=[{"url": "https://example.com", "priority": 1}]
    )
    assert config.chain_type == chain_type


@pytest.mark.parametrize("chain_type", ["invalid", "main", "test", ""])
def test_invalid_chain_types(chain_type: str):
    """Test that invalid chain type values are still accepted (as strings)."""
    from chain_listener.models.config import ChainConfig

    # Chain type is a string field, so it accepts any string
    config = ChainConfig(
        chain_type=chain_type,
        rpc_urls=[{"url": "https://example.com", "priority": 1}]
    )
    assert config.chain_type == chain_type


def test_config_serialization():
    """Test that configuration can be serialized to dict."""
    from chain_listener.models.config import ChainListenerConfig

    config_data = {
        "chains": {
            "ethereum": {
                "chain_type": "ethereum",
                "rpc": {"endpoints": [{"url": "https://eth.llamarpc.com"}]}
            }
        }
    }

    config = ChainListenerConfig(**config_data)
    serialized = config.model_dump()

    assert "chains" in serialized
    assert "ethereum" in serialized["chains"]
    assert serialized["chains"]["ethereum"]["chain_type"] == "ethereum"
