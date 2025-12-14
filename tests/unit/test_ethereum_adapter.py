"""Test Ethereum blockchain adapter following TDD principles."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
from datetime import datetime, timezone

# These tests are written before implementation exists
# They will fail initially, then we'll implement the code to make them pass


class TestEthereumAdapter:
    """Test suite for EthereumAdapter."""

    def test_ethereum_adapter_initialization(self):
        """Test that Ethereum adapter can be initialized with valid config."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": ["https://eth.llamarpc.com"],
                "timeout": 30,
                "retries": 3
            }
        }

        adapter = EthereumAdapter(config)

        assert adapter.name == "ethereum"
        assert adapter.network == "mainnet"
        assert adapter.chain_id == 1  # Ethereum mainnet
        assert adapter.block_time == 12  # Ethereum block time
        assert adapter.rpc_config["urls"] == ["https://eth.llamarpc.com"]

    def test_ethereum_adapter_testnet_initialization(self):
        """Test that Ethereum adapter can be initialized for testnet."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "goerli",
            "rpc": {
                "urls": ["https://goerli.infura.io/v3/test"],
                "timeout": 30,
                "retries": 3
            }
        }

        adapter = EthereumAdapter(config)

        assert adapter.name == "ethereum"
        assert adapter.network == "goerli"
        assert adapter.chain_id == 5  # Goerli testnet
        assert adapter.rpc_config["urls"] == ["https://goerli.infura.io/v3/test"]

    def test_ethereum_adapter_invalid_network(self):
        """Test that Ethereum adapter validates network types."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        with pytest.raises(ValueError, match="Invalid Ethereum network"):
            EthereumAdapter({
                "name": "ethereum",
                "network": "invalid_network",
                "rpc": {"urls": ["https://eth.llamarpc.com"]}
            })

    def test_ethereum_adapter_chain_id_mapping(self):
        """Test chain ID mapping for different Ethereum networks."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        networks_to_chain_ids = {
            "mainnet": 1,
            "goerli": 5,
            "sepolia": 11155111,
            "holesky": 17000
        }

        for network, expected_chain_id in networks_to_chain_ids.items():
            adapter = EthereumAdapter({
                "name": "ethereum",
                "network": network,
                "rpc": {"urls": ["https://test.com"]}
            })

            assert adapter.chain_id == expected_chain_id

    @pytest.mark.asyncio
    async def test_ethereum_adapter_connect(self):
        """Test that Ethereum adapter can connect to Web3."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        # Create adapter first to see what needs to be mocked
        adapter = EthereumAdapter(config)

        # Now mock the Web3 instance that will be created in connect method
        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 1

            await adapter.connect()

            assert adapter.is_connected()
            assert adapter._w3 == mock_web3
            # Verify Web3 was called with HTTPProvider
            assert mock_web3_class.called

    @pytest.mark.asyncio
    async def test_ethereum_adapter_connect_with_retry(self):
        """Test that Ethereum adapter handles connection failure correctly."""
        from chain_listener.adapters.ethereum import EthereumAdapter
        from chain_listener.exceptions import ConnectionError as ChainConnectionError

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        # Mock Web3 to fail connection
        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = False

            # Should raise ConnectionError when Web3 connection fails
            with pytest.raises(ChainConnectionError, match="Failed to connect"):
                await adapter.connect()

            assert not adapter.is_connected()
            assert mock_web3_class.called

    @pytest.mark.asyncio
    async def test_ethereum_adapter_connection_failure(self):
        """Test that Ethereum adapter raises exception on connection failure."""
        from chain_listener.adapters.ethereum import EthereumAdapter
        from chain_listener.exceptions import ConnectionError as ChainConnectionError

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://invalid.com"], "retries": 2}
        }

        adapter = EthereumAdapter(config)

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = False

            with pytest.raises(ChainConnectionError, match="Failed to connect"):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_get_latest_block_number(self):
        """Test getting latest block number from Ethereum."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock block_number as a callable property access
            mock_web3.eth.block_number = 18500000

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            # Mock the _execute_with_rate_limit to return the block number directly
            with patch.object(adapter, '_execute_with_rate_limit', return_value=18500000):
                block_number = await adapter.get_latest_block_number()

            assert block_number == 18500000
            assert isinstance(block_number, int)

    @pytest.mark.asyncio
    async def test_get_latest_block_number_not_connected(self):
        """Test getting block number when not connected raises error."""
        from chain_listener.adapters.ethereum import EthereumAdapter
        from chain_listener.exceptions import BlockchainAdapterError

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        with pytest.raises(BlockchainAdapterError, match="Not connected"):
            await adapter.get_latest_block_number()

    @pytest.mark.asyncio
    async def test_get_block_by_number(self):
        """Test getting block by number from Ethereum."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        # Create mock block object with attributes expected by implementation
        mock_block = Mock()
        mock_block.number = 18500000
        mock_block.hash = Mock()
        mock_block.hash.hex = Mock(return_value="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef")
        mock_block.parentHash = Mock()
        mock_block.parentHash.hex = Mock(return_value="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890")
        mock_block.timestamp = 1640000000
        mock_block.transactions = []
        mock_block.gasLimit = 30000000
        mock_block.gasUsed = 15000000
        mock_block.miner = Mock()
        mock_block.miner.hex = Mock(return_value="1234567890123456789012345678901234567890")
        mock_block.difficulty = 12345
        mock_block.totalDifficulty = 12345678
        mock_block.size = 1000
        mock_block.uncles = []
        mock_block.extraData = Mock()
        mock_block.extraData.hex = Mock(return_value="0x")
        mock_block.logsBloom = Mock()
        mock_block.logsBloom.hex = Mock(return_value="0x")
        mock_block.mixHash = Mock()
        mock_block.mixHash.hex = Mock(return_value="0x")
        mock_block.nonce = Mock()
        mock_block.nonce.hex = Mock(return_value="0x")
        mock_block.receiptsRoot = Mock()
        mock_block.receiptsRoot.hex = Mock(return_value="0x")
        mock_block.sha3Uncles = Mock()
        mock_block.sha3Uncles.hex = Mock(return_value="0x")
        mock_block.stateRoot = Mock()
        mock_block.stateRoot.hex = Mock(return_value="0x")
        mock_block.transactionsRoot = Mock()
        mock_block.transactionsRoot.hex = Mock(return_value="0x")

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock the eth.get_block method
            mock_web3.eth.get_block = AsyncMock(return_value=mock_block)

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            # Mock the _execute_with_rate_limit to return the mock block
            with patch.object(adapter, '_execute_with_rate_limit', return_value=mock_block):
                block = await adapter.get_block_by_number(18500000)

            assert block["number"] == 18500000
            assert block["timestamp"] == 1640000000
            assert "transactions" in block
            assert isinstance(block["transactions"], list)

    @pytest.mark.asyncio
    async def test_get_block_by_number_not_found(self):
        """Test getting non-existent block raises error."""
        from chain_listener.adapters.ethereum import EthereumAdapter
        from chain_listener.exceptions import BlockNotFoundError

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock the eth.get_block method to raise exception
            from web3.exceptions import BlockNotFound
            mock_web3.eth.get_block = AsyncMock(side_effect=BlockNotFound())

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            # Mock _execute_with_rate_limit to raise the BlockNotFound exception directly
            from web3.exceptions import BlockNotFound
            with patch.object(adapter, '_execute_with_rate_limit', side_effect=BlockNotFound()):
                with pytest.raises(BlockNotFoundError, match="Block 999999999 not found"):
                    await adapter.get_block_by_number(999999999)

    @pytest.mark.asyncio
    async def test_get_logs_by_contract(self):
        """Test getting logs for a specific contract on Ethereum."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"  # WBTC

        mock_logs = [{
            "address": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x000000000000000000000000000abcdefabcdefabcdefabcdefabcdefabcd",
                "0x0000000000000000000000000001234567890123456789012345678901234567890"
            ],
            "data": "0x0000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000014",
            "blockNumber": 18500000,
            "transactionHash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "logIndex": 5
        }]

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock the eth.get_logs method
            mock_web3.eth.get_logs = AsyncMock(return_value=mock_logs)

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            # Create mock log objects with expected attributes
            mock_log_objects = []
            for log_data in mock_logs:
                mock_log = Mock()
                mock_log.address = log_data["address"]
                mock_log.topics = [Mock(hex=lambda: topic) for topic in log_data["topics"]]
                mock_log.data = Mock(hex=lambda: log_data["data"])
                mock_log.blockNumber = log_data["blockNumber"]
                mock_log.blockHash = Mock(hex=lambda: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890")
                mock_log.transactionHash = Mock(hex=lambda: log_data["transactionHash"])
                mock_log.transactionIndex = 0
                mock_log.logIndex = log_data["logIndex"]
                mock_log.removed = False
                mock_log_objects.append(mock_log)

            # Test the actual Web3 integration with proper mocking
            with patch.object(adapter, '_execute_with_priority_routing') as mock_execute:
                # Mock the Web3 get_logs call to return realistic Mock objects
                mock_execute.return_value = mock_log_objects

                logs = await adapter.get_logs(
                    address=contract_address,
                    from_block=18500000,
                    to_block=18500100
                )

                # Verify the underlying Web3 method was called with correct parameters
                mock_execute.assert_called_once()
                call_args = mock_execute.call_args
                operation = call_args[0][0]  # First positional argument should be the operation function

                # Verify that the operation function is callable (it should be our Web3 operation)
                assert callable(operation)

            # Validate returned logs with comprehensive assertions
            assert isinstance(logs, list)
            assert len(logs) == 1

            log = logs[0]
            # Verify address normalization (lowercase)
            assert log["address"] == "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
            # Verify topics are correctly processed (should match the original mock data)
            assert len(log["topics"]) == 3
            assert log["topics"][0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # Transfer event signature
            assert log["topics"][1] == "0x000000000000000000000000000abcdefabcdefabcdefabcdefabcdefabcd"  # From address
            assert log["topics"][2] == "0x0000000000000000000000000001234567890123456789012345678901234567890"  # To address
            # Verify transfer amount in data (should be 10 in hex: 0xa)
            assert log["data"] == "0x0000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000014"
            # Verify block number
            assert log["block_number"] == 18500000
            # Verify transaction hash
            assert log["transaction_hash"] == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            # Verify log index
            assert log["log_index"] == 5

    @pytest.mark.asyncio
    async def test_get_logs_with_event_topics(self):
        """Test getting logs with specific event topics."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

        # Transfer event topic
        transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock the eth.get_logs method
            mock_web3.eth.get_logs = AsyncMock(return_value=[])

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            logs = await adapter.get_logs(
                address=contract_address,
                topics=[transfer_topic],
                from_block=18500000,
                to_block=18500100
            )

            # Verify that get_logs was called with correct parameters
            mock_web3.eth.get_logs.assert_called_once_with({
                "address": contract_address,
                "topics": [transfer_topic],
                "fromBlock": 18500000,
                "toBlock": 18500100
            })

            assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_get_transaction(self):
        """Test getting transaction by hash from Ethereum."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        transaction_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        mock_transaction = {
            "hash": transaction_hash,
            "blockNumber": 18500000,
            "from": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "to": "0x1234567890123456789012345678901234567890",
            "value": 1000000000000000000,
            "gas": 21000,
            "gasPrice": 20000000000
        }

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock the eth.get_transaction method
            mock_web3.eth.get_transaction = AsyncMock(return_value=mock_transaction)

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            transaction = await adapter.get_transaction(transaction_hash)

            assert transaction["hash"] == transaction_hash
            assert transaction["blockNumber"] == 18500000
            assert transaction["value"] == 1000000000000000000

    @pytest.mark.asyncio
    async def test_get_transaction_not_found(self):
        """Test getting non-existent transaction raises error."""
        from chain_listener.adapters.ethereum import EthereumAdapter
        from chain_listener.exceptions import TransactionError

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        transaction_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock the eth.get_transaction method to raise exception
            from web3.exceptions import TransactionNotFound
            mock_web3.eth.get_transaction = AsyncMock(side_effect=TransactionNotFound())

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            with pytest.raises(TransactionError, match="Transaction not found"):
                await adapter.get_transaction(transaction_hash)

    @pytest.mark.asyncio
    async def test_subscribe_to_contract_events(self):
        """Test subscribing to contract events."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

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

    @pytest.mark.asyncio
    async def test_subscribe_to_multiple_events(self):
        """Test subscribing to multiple contract events."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock contract creation and event subscription
            mock_contract = Mock()
            mock_web3.eth.contract.return_value = mock_contract

            # Mock multiple events
            mock_contract.events.Transfer = Mock()
            mock_contract.events.Burn = Mock()
            mock_contract.events.Mint = Mock()

            mock_contract.events.Transfer.create_filter = Mock()
            mock_contract.events.Burn.create_filter = Mock()
            mock_contract.events.Mint.create_filter = Mock()

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            subscription_id = await adapter.subscribe_to_contract_events(
                address=contract_address,
                events=["Transfer", "Burn", "Mint"]
            )

            assert subscription_id is not None
            assert isinstance(subscription_id, str)

            # Verify all event filters were created
            mock_contract.events.Transfer.create_filter.assert_called_once()
            mock_contract.events.Burn.create_filter.assert_called_once()
            mock_contract.events.Mint.create_filter.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_get_logs(self):
        """Test batch log retrieval for performance."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock the eth.get_logs method to return different logs for different requests
            def mock_get_logs(params):
                if params["fromBlock"] == 18500000:
                    return [{"address": "0x123", "blockNumber": 18500000}]
                else:
                    return [{"address": "0x456", "blockNumber": 18500011}]

            mock_web3.eth.get_logs = AsyncMock(side_effect=mock_get_logs)

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            # Create batch requests
            requests = [
                {
                    "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                    "from_block": 18500000,
                    "to_block": 18500010
                },
                {
                    "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                    "from_block": 18500011,
                    "to_block": 18500020
                }
            ]

            results = await adapter.batch_get_logs(requests)

            assert isinstance(results, list)
            assert len(results) == 2

            # First request result
            assert len(results[0]) == 1
            assert results[0][0]["blockNumber"] == 18500000

            # Second request result
            assert len(results[1]) == 1
            assert results[1][0]["blockNumber"] == 18500011

    @pytest.mark.asyncio
    async def test_events_stream(self):
        """Test streaming events in real-time."""
        from chain_listener.adapters.ethereum import EthereumAdapter
        import asyncio

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

        # Create mock events with expected properties
        mock_events = [
            {
                "address": contract_address.lower(),
                "topics": [
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    "0x000000000000000000000000abcdefabcdefabcdefabcdefabcdefabcdefabcd",
                    "0x0000000000000000000000001234567890123456789012345678901234567890"
                ],
                "data": "0x00000000000000000000000000000000000000000000000000000000000000a0",
                "blockNumber": 18500000,
                "transactionHash": "0x1111111111111111111111111111111111111111111111111111111111111111",
                "logIndex": 0
            },
            {
                "address": contract_address.lower(),
                "topics": [
                    "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925",
                    "0x000000000000000000000000abcdefabcdefabcdefabcdefabcdefabcdefabcd",
                    "0x0000000000000000000000001234567890123456789012345678901234567890"
                ],
                "data": "0x0000000000000000000000000000000000000000000000000000000000000140",
                "blockNumber": 18500001,
                "transactionHash": "0x2222222222222222222222222222222222222222222222222222222222222222",
                "logIndex": 0
            },
            {
                "address": contract_address.lower(),
                "topics": [
                    "0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526ed8d7e",
                    "0x000000000000000000000000abcdefabcdefabcdefabcdefabcdefabcdefabcd",
                    "0x000000000000000000000000fedcbafedcbafedcbafedcbafedcbafedcbafed"
                ],
                "data": "0x00000000000000000000000000000000000000000000000000000000000001e0",
                "blockNumber": 18500002,
                "transactionHash": "0x3333333333333333333333333333333333333333333333333333333333333333",
                "logIndex": 0
            }
        ]

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock block and log retrieval to return our test events
            mock_web3.eth.block_number = 18500002

            def mock_get_logs(params):
                # Return events based on block range
                from_block = params.get("fromBlock", 0)
                to_block = params.get("toBlock", 999999999)

                filtered_events = []
                for event in mock_events:
                    if from_block <= event["blockNumber"] <= to_block:
                        filtered_events.append(event)
                return filtered_events

            mock_web3.eth.get_logs = AsyncMock(side_effect=mock_get_logs)
            mock_web3.eth.get_block = AsyncMock()

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            # Start event streaming (limited duration for test)
            event_stream = adapter.get_events_stream(
                address=contract_address,
                from_block=18500000
            )

            # Collect first few events
            events = []
            async for event in event_stream:
                events.append(event)
                if len(events) >= 3:  # Limit for test
                    break

            # Proper assertions to validate event data
            assert isinstance(events, list)
            assert len(events) == 3

            # Verify first event (Transfer)
            assert events[0]["address"] == contract_address.lower()
            assert events[0]["blockNumber"] == 18500000
            assert events[0]["transactionHash"] == "0x1111111111111111111111111111111111111111111111111111111111111111"
            assert events[0]["logIndex"] == 0
            assert len(events[0]["topics"]) == 3
            assert events[0]["topics"][0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # Transfer event signature

            # Verify second event (Approval)
            assert events[1]["address"] == contract_address.lower()
            assert events[1]["blockNumber"] == 18500001
            assert events[1]["transactionHash"] == "0x2222222222222222222222222222222222222222222222222222222222222222"
            assert events[1]["topics"][0] == "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"  # Approval event signature

            # Verify third event (different event)
            assert events[2]["address"] == contract_address.lower()
            assert events[2]["blockNumber"] == 18500002
            assert events[2]["transactionHash"] == "0x3333333333333333333333333333333333333333333333333333333333333333"

            # Verify events are in correct chronological order
            assert events[0]["blockNumber"] < events[1]["blockNumber"] < events[2]["blockNumber"]

            # Verify all events have the expected structure
            for event in events:
                assert "address" in event
                assert "topics" in event
                assert "data" in event
                assert "blockNumber" in event
                assert "transactionHash" in event
                assert "logIndex" in event
                assert isinstance(event["blockNumber"], int)
                assert isinstance(event["logIndex"], int)
                assert isinstance(event["topics"], list)

    def test_ethereum_adapter_metadata(self):
        """Test Ethereum adapter metadata."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        metadata = adapter.get_metadata()

        assert metadata["name"] == "ethereum"
        assert metadata["network"] == "mainnet"
        assert metadata["chain_id"] == 1
        assert metadata["block_time"] == 12
        assert "logs" in metadata["supports"]
        assert "subscriptions" in metadata["supports"]
        assert "batch_requests" in metadata["supports"]
        assert metadata["supports"]["logs"] is True
        assert metadata["supports"]["subscriptions"] is True
        assert metadata["supports"]["batch_requests"] is True

    @pytest.mark.asyncio
    async def test_error_handling_web3_exceptions(self):
        """Test handling of Web3-specific exceptions."""
        from chain_listener.adapters.ethereum import EthereumAdapter
        from chain_listener.exceptions import BlockchainAdapterError

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {"urls": ["https://eth.llamarpc.com"]}
        }

        adapter = EthereumAdapter(config)

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True

            # Mock Web3 exception
            from web3.exceptions import TimeExhausted
            mock_web3.eth.get_block = AsyncMock(side_effect=TimeExhausted())

            # Set up connected state
            adapter._w3 = mock_web3
            adapter._connected = True

            with pytest.raises(BlockchainAdapterError, match="Web3 request timeout"):
                await adapter.get_block_by_number(18500000)

    @pytest.mark.asyncio
    async def test_connection_load_balancing(self):
        """Test that adapter uses connection pool for load balancing."""
        from chain_listener.adapters.ethereum import EthereumAdapter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc": {
                "urls": [
                    "https://eth1.llamarpc.com",
                    "https://eth2.llamarpc.com",
                    "https://eth3.llamarpc.com"
                ],
                "strategy": "round_robin"
            }
        }

        adapter = EthereumAdapter(config)

        with patch('chain_listener.adapters.ethereum.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3_class.return_value = mock_web3
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 1

            # Connect multiple times to test load balancing
            for _ in range(3):
                await adapter.connect()
                await adapter.disconnect()

            # Verify Web3 was called with different URLs
            call_args = [call[0][0] for call in mock_web3_class.call_args_list]
            assert len(set(call_args)) == 3  # All 3 URLs should be used

    @pytest.mark.asyncio
    async def test_rate_limiting_configuration(self):
        """Test that adapter properly configures rate limiting."""
        from chain_listener.adapters.ethereum import EthereumAdapter
        from async_limiter import DualRateLimiter

        config = {
            "name": "ethereum",
            "network": "mainnet",
            "rpc_endpoints": ["https://eth.llamarpc.com"],
            "rpc": {
                "rate_limit": {
                    "requests_per_second": 2,
                    "burst_size": 4
                }
            }
        }

        adapter = EthereumAdapter(config)

        # Verify rate limiter is properly configured
        assert adapter._requests_per_second == 2
        assert adapter._burst_size == 4
        assert isinstance(adapter._rate_limiter, DualRateLimiter)

        # Test with different rate limit configuration
        adapter_with_custom_limit = EthereumAdapter({
            "name": "ethereum",
            "network": "mainnet",
            "rpc_endpoints": ["https://eth.llamarpc.com"],
            "rpc": {
                "rate_limit": {
                    "requests_per_second": 10,
                    "burst_size": 20
                }
            }
        })

        # Verify the adapter properly configures rate limiter with custom values
        assert adapter_with_custom_limit._requests_per_second == 10
        assert adapter_with_custom_limit._burst_size == 20
        assert isinstance(adapter_with_custom_limit._rate_limiter, DualRateLimiter)