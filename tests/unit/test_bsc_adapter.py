"""Test BSC blockchain adapter following TDD principles."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# These tests are written before implementation exists
# They will fail initially, then we'll implement the code to make them pass


class TestBSCAdapter:
    """Test suite for BSCAdapter."""

    def test_bsc_adapter_initialization(self):
        """Test that BSC adapter can be initialized with valid config."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://bsc-dataseed.binance.org"],
                "timeout": 30,
                "retries": 3
            }
        }

        adapter = BSCAdapter(config)

        assert adapter.name == "bsc"
        assert adapter.network == "mainnet"
        assert adapter.chain_id == 56  # BSC mainnet
        assert adapter.block_time == 3  # BSC block time
        assert adapter.rpc_config["urls"] == ["https://bsc-dataseed.binance.org"]

    def test_bsc_adapter_testnet_initialization(self):
        """Test that BSC adapter can be initialized for testnet."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "testnet",
            "rpc": {
                "urls": ["https://data-seed-prebsc-1-s1.binance.org:8545"],
                "timeout": 30,
                "retries": 3
            }
        }

        adapter = BSCAdapter(config)

        assert adapter.name == "bsc"
        assert adapter.network == "testnet"
        assert adapter.chain_id == 97  # BSC testnet
        assert adapter.block_time == 3  # BSC block time

    def test_bsc_adapter_invalid_network(self):
        """Test that BSC adapter validates network types."""
        from chain_listener.adapters.bsc import BSCAdapter

        with pytest.raises(ValueError, match="Invalid BSC network"):
            BSCAdapter({
                "name": "bsc",
                "network": "invalid_network",
                "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
            })

    def test_bsc_adapter_chain_id_mapping(self):
        """Test chain ID mapping for different BSC networks."""
        from chain_listener.adapters.bsc import BSCAdapter

        networks_to_chain_ids = {
            "mainnet": 56,
            "testnet": 97
        }

        for network, expected_chain_id in networks_to_chain_ids.items():
            adapter = BSCAdapter({
                "name": "bsc",
                "network": network,
                "rpc": {"urls": ["https://test.binance.org"]}
            })

            assert adapter.chain_id == expected_chain_id

    def test_bsc_adapter_inherits_from_ethereum(self):
        """Test that BSC adapter inherits from Ethereum adapter."""
        from chain_listener.adapters.bsc import BSCAdapter
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        assert isinstance(adapter, EthereumAdapter)
        assert hasattr(adapter, 'chain_id')
        assert hasattr(adapter, 'block_time')
        assert hasattr(adapter, '_get_contract_instance')

    @pytest.mark.asyncio
    async def test_bsc_adapter_connect(self):
        """Test that BSC adapter can connect to BSC network."""
        from chain_listener.adapters.bsc import BSCAdapter
        from web3 import Web3

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        # Mock Web3 connection
        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56  # BSC mainnet

            await adapter.connect()

            assert adapter.is_connected()
            assert adapter._w3 == mock_web3
            mock_web3_class.assert_called_once_with("https://bsc-dataseed.binance.org")

    @pytest.mark.asyncio
    async def test_bsc_adapter_connect_with_retry(self):
        """Test that BSC adapter retries connection on failure."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://invalid1.com", "https://invalid2.com"],
                "retries": 3
            }
        }

        adapter = BSCAdapter(config)

        # Mock Web3 to fail first attempts, succeed on last
        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.side_effect = [False, False, True]
            mock_web3.eth.chain_id = 56

            await adapter.connect()

            assert adapter.is_connected()
            assert mock_web3_class.call_count == 3

    @pytest.mark.asyncio
    async def test_bsc_adapter_connection_failure_wrong_chain_id(self):
        """Test that BSC adapter raises error for wrong chain ID."""
        from chain_listener.adapters.bsc import BSCAdapter
        from chain_listener.exceptions import ConnectionError as ChainConnectionError

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"], "retries": 1}
        }

        adapter = BSCAdapter(config)

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 1  # Ethereum chain ID instead of BSC

            with pytest.raises(ChainConnectionError, match="Chain ID mismatch"):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_bsc_adapter_get_latest_block_number(self):
        """Test getting latest block number from BSC."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56
            mock_web3.eth.block_number = 42000000

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            block_number = await adapter.get_latest_block_number()

            assert block_number == 42000000
            assert isinstance(block_number, int)

    @pytest.mark.asyncio
    async def test_bsc_adapter_get_block_by_number(self):
        """Test getting block by number from BSC."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        mock_block = {
            "number": 42000000,
            "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef",
            "timestamp": 1700000000,
            "transactions": [],
            "gasLimit": 30000000,
            "gasUsed": 15000000
        }

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56

            # Mock eth.get_block method
            mock_web3.eth.get_block = AsyncMock(return_value=mock_block)

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            block = await adapter.get_block_by_number(42000000)

            assert block["number"] == 42000000
            assert block["hash"] == "0x1234567890abcdef1234567890abcdef1234567890abcdef"
            assert "timestamp" in block
            assert "gas_limit" in block  # Should be converted from gasLimit

    @pytest.mark.asyncio
    async def test_bsc_adapter_get_logs_by_contract(self):
        """Test getting logs for a specific contract on BSC."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        contract_address = "0x2170ed0880ac9a755fd29b268895859272cf878"  # BUSD on BSC

        mock_logs = [{
            "address": "0x2170ed0880ac9a755fd29b268895859272cf878",
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x000000000000000000000000abcdefabcdefabcdefabcdefabcd",
                "0x000000000000000000000000123456789012345678901234567890"
            ],
            "data": "0x0000000000000000000000000000000000000000000000000000000000a0000000000000000000000000000000000000000014",
            "blockNumber": 42000000,
            "transactionHash": "0x1234567890abcdef1234567890abcdef1234567890abcdef",
            "logIndex": 0
        }]

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56

            # Mock eth.get_logs method
            mock_web3.eth.get_logs = AsyncMock(return_value=mock_logs)

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            logs = await adapter.get_logs(
                address=contract_address,
                from_block=42000000,
                to_block=42000100
            )

            assert isinstance(logs, list)
            assert len(logs) == 1
            assert logs[0]["address"] == "0x2170ed0880ac9a755fd29b268895859272cf878"
            assert logs[0]["block_number"] == 42000000  # Should be converted from blockNumber

    @pytest.mark.asyncio
    async def test_bsc_adapter_get_transaction(self):
        """Test getting transaction by hash from BSC."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        transaction_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef"

        mock_transaction = {
            "hash": transaction_hash,
            "blockNumber": 42000000,
            "from": "0xabcdefabcdefabcdefabcdefabcdefabcd",
            "to": "0x1234567890123456789012345678901234567890",
            "value": 1000000000000000000,  # 1000 BNB in wei
            "gas": 21000,
            "gasPrice": 20000000000,  # 20 gwei
            "nonce": 123
        }

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56

            # Mock eth.get_transaction method
            mock_web3.eth.get_transaction = AsyncMock(return_value=mock_transaction)

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            transaction = await adapter.get_transaction(transaction_hash)

            assert transaction["hash"] == transaction_hash
            assert transaction["block_number"] == 42000000
            assert transaction["value"] == "1000000000000000000"
            assert transaction["gas"] == 21000

    @pytest.mark.asyncio
    async def test_bsc_adapter_subscribe_to_contract_events(self):
        """Test subscribing to contract events on BSC."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        contract_address = "0x2170ed0880ac9a755fd29b268895859272cf878"  # BUSD

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56

            # Mock contract creation and event subscription
            mock_contract = Mock()
            mock_web3.eth.contract.return_value = mock_contract
            mock_contract.events.Transfer = Mock()
            mock_contract.events.Transfer.create_filter = Mock()
            mock_filter = Mock()
            mock_contract.events.Transfer.create_filter.return_value = mock_filter

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            subscription_id = await adapter.subscribe_to_contract_events(
                address=contract_address,
                events=["Transfer"]
            )

            assert subscription_id is not None
            assert isinstance(subscription_id, str)
            assert subscription_id in adapter._subscriptions

            # Verify contract was created with correct address
            mock_web3.eth.contract.assert_called_with(address=contract_address)

    def test_bsc_adapter_metadata(self):
        """Test BSC adapter metadata."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        metadata = adapter.get_metadata()

        assert metadata["name"] == "bsc"
        assert metadata["network"] == "mainnet"
        assert metadata["chain_id"] == 56
        assert metadata["block_time"] == 3
        assert "logs" in metadata["supports"]
        assert "subscriptions" in metadata["supports"]
        assert "batch_requests" in metadata["supports"]

        # Should have BSC-specific metadata
        assert "network_name" in metadata
        assert "BSC" in metadata["network_name"]

    @pytest.mark.asyncio
    async def test_bsc_adapter_health_check(self):
        """Test BSC adapter health check."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3

            # Initial health check - not connected
            health = adapter.get_health_status()
            assert health["status"] == "unhealthy"
            assert not health["connected"]

            # Connect and check health
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56
            mock_web3.eth.block_number = 42000000
            mock_web3.eth.syncing = False

            adapter._w3 = mock_web3
            adapter._connected = True

            health = adapter.get_health_status()
            assert health["status"] == "healthy"
            assert health["connected"]
            assert health["connected_chain_id"] == 56
            assert health["latest_block"] == 42000000

    def test_bsc_adapter_bsc_specific_features(self):
        """Test BSC adapter specific features."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        metadata = adapter.get_metadata()

        # Should have BSC-specific features
        assert "features" in metadata
        assert metadata["features"]["smart_contracts"] is True
        assert metadata["features"]["erc20"] is True
        assert metadata["features"]["erc721"] is True
        assert metadata["features"]["erc1155"] is True

        # Should mention BSC compatibility
        assert "ethereum_compatible" in metadata
        assert metadata["ethereum_compatible"] is True

    @pytest.mark.asyncio
    async def test_bsc_adapter_inherits_ethereum_methods(self):
        """Test that BSC adapter inherits Ethereum methods correctly."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            # Test inherited methods work
            assert hasattr(adapter, 'get_latest_block_number')
            assert hasattr(adapter, 'get_block_by_number')
            assert hasattr(adapter, 'get_logs')
            assert hasattr(adapter, 'get_transaction')
            assert hasattr(adapter, 'subscribe_to_contract_events')
            assert hasattr(adapter, 'get_events_stream')

            # Test one inherited method works
            block_number = await adapter.get_latest_block_number()
            assert isinstance(block_number, int)

    def test_bsc_adapter_network_configurations(self):
        """Test BSC adapter network configurations."""
        from chain_listener.adapters.bsc import BSCAdapter

        # Test mainnet configuration
        mainnet_adapter = BSCAdapter({
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        })

        assert mainnet_adapter.chain_id == 56
        assert mainnet_adapter.block_time == 3

        # Test testnet configuration
        testnet_adapter = BSCAdapter({
            "name": "bsc",
            "network": "testnet",
            "rpc": {"urls": ["https://data-seed-prebsc-1-s1.binance.org:8545"]}
        })

        assert testnet_adapter.chain_id == 97
        assert testnet_adapter.block_time == 3

    @pytest.mark.asyncio
    async def test_bsc_adapter_error_handling(self):
        """Test BSC adapter error handling."""
        from chain_listener.adapters.bsc import BSCAdapter
        from chain_listener.exceptions import BlockchainAdapterError

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56

            # Mock Web3 exception
            from web3.exceptions import TimeExhausted
            mock_web3.eth.get_block = AsyncMock(side_effect=TimeExhausted())

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            with pytest.raises(BlockchainAdapterError, match="Web3 request timeout"):
                await adapter.get_block_by_number(42000000)

    def test_bsc_adapter_rpc_urls_validation(self):
        """Test BSC adapter RPC URL validation."""
        from chain_listener.adapters.bsc import BSCAdapter

        # Test valid BSC RPC URLs
        valid_urls = [
            "https://bsc-dataseed.binance.org",
            "https://bsc-dataseed1.defibit.io",
            "https://bsc-dataseed1.ninicoin.io",
            "https://bsc-dataseed2.defibit.io",
            "https://data-seed-prebsc-1-s1.binance.org:8545"
        ]

        for url in valid_urls:
            adapter = BSCAdapter({
                "name": "bsc",
                "network": "mainnet",
                "rpc": {"urls": [url]}
            })
            assert adapter.rpc_config["urls"] == [url]

        # Test invalid URL
        with pytest.raises(ValueError, match="Invalid Ethereum RPC URL"):
            BSCAdapter({
                "name": "bsc",
                "network": "mainnet",
                "rpc": {"urls": ["invalid-url"]}
            })

    @pytest.mark.asyncio
    async def test_bsc_adapter_batch_operations(self):
        """Test BSC adapter batch operations."""
        from chain_listener.adapters.bsc import BSCAdapter

        config = {
            "name": "bsc",
            "network": "mainnet",
            "rpc": {"urls": ["https://bsc-dataseed.binance.org"]}
        }

        adapter = BSCAdapter(config)

        with patch('chain_listener.adapters.bsc.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 56

            # Mock eth.get_logs method
            mock_web3.eth.get_logs = AsyncMock(return_value=[])

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            # Create batch requests
            requests = [
                {
                    "address": "0x2170ed0880ac9a755fd29b268895859272cf878",
                    "from_block": 42000000,
                    "to_block": 42000010
                },
                {
                    "address": "0x2170ed0880ac9a755fd29b268895859272cf878",
                    "from_block": 42000011,
                    "to_block": 42000020
                }
            ]

            results = await adapter.batch_get_logs(requests)

            assert isinstance(results, list)
            assert len(results) == 2

            # Verify get_logs was called for each request
            assert mock_web3.eth.get_logs.call_count == 2