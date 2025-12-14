"""BSC (Binance Smart Chain) blockchain adapter implementation.

This module provides the BSC-specific implementation of the blockchain adapter,
inheriting from EthereumAdapter since BSC is Ethereum-compatible. It supports
both mainnet and testnet networks with BSC-specific optimizations and RPC endpoints.
"""

from typing import Dict, List, Optional, Any, AsyncGenerator

from web3 import Web3

from chain_listener.adapters.ethereum import EthereumAdapter
from chain_listener.exceptions import (
    BlockchainAdapterError,
    ConnectionError as ChainConnectionError
)


class BSCAdapter(EthereumAdapter):
    """BSC (Binance Smart Chain) blockchain adapter.

    BSC is EVM-compatible and inherits most functionality from Ethereum,
    but with BSC-specific configurations, RPC endpoints, and optimizations.
    Supports both mainnet (chain ID 56) and testnet (chain ID 97).
    """

    # BSC network configurations
    NETWORK_CONFIGS = {
        "mainnet": {
            "chain_id": 56,
            "block_time": 3,  # ~3 seconds on BSC
            "name": "BSC Mainnet"
        },
        "testnet": {
            "chain_id": 97,
            "block_time": 3,  # ~3 seconds on BSC testnet
            "name": "BSC Testnet"
        }
    }

    # Default BSC RPC endpoints
    DEFAULT_RPC_ENDPOINTS = {
        "mainnet": [
            "https://bsc-dataseed.binance.org",
            "https://bsc-dataseed1.defibit.io",
            "https://bsc-dataseed1.ninicoin.io",
            "https://bsc-dataseed2.defibit.io",
            "https://bsc-dataseed3.defibit.io",
            "https://bsc-dataseed4.defibit.io"
        ],
        "testnet": [
            "https://data-seed-prebsc-1-s1.binance.org:8545",
            "https://data-seed-prebsc-2-s1.binance.org:8545",
            "https://data-seed-prebsc-1-s2.binance.org:8545",
            "https://data-seed-prebsc-2-s2.binance.org:8545"
        ]
    }

    def __init__(self, config: Dict[str, Any]):
        """Initialize BSC adapter.

        Args:
            config: BSC-specific configuration

        Raises:
            ValueError: If network or configuration is invalid
        """
        # Set BSC defaults if not specified
        if "rpc" not in config:
            network = config.get("network", "mainnet")
            config["rpc"] = {
                "urls": self.DEFAULT_RPC_ENDPOINTS.get(network, self.DEFAULT_RPC_ENDPOINTS["mainnet"]).copy(),
                "timeout": config.get("rpc", {}).get("timeout", 30),
                "retries": config.get("rpc", {}).get("retries", 3),
                "strategy": config.get("rpc", {}).get("strategy", "round_robin")
            }

        # Override network validation with BSC networks
        self._validate_bsc_config(config)

        # Initialize parent Ethereum adapter
        super().__init__(config)

        # Set BSC-specific properties
        network_config = self.NETWORK_CONFIGS[self.network]
        self.chain_id = network_config["chain_id"]
        self.block_time = network_config["block_time"]

    def _validate_bsc_config(self, config: Dict[str, Any]) -> None:
        """Validate BSC-specific configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        network = config.get("network", "mainnet")

        if network not in self.NETWORK_CONFIGS:
            valid_networks = ", ".join(self.NETWORK_CONFIGS.keys())
            raise ValueError(
                f"Invalid BSC network: {network}. "
                f"Valid networks are: {valid_networks}"
            )

        # Validate RPC URLs for BSC
        rpc_config = config.get("rpc", {})
        urls = rpc_config.get("urls", [])

        for url in urls:
            if not url.startswith(("http://", "https://", "wss://")):
                raise ValueError(f"Invalid BSC RPC URL: {url}")

            # Check for BSC-specific URL patterns
            if any(domain in url for domain in ["bsc", "binance", "ninicoin", "defibit"]):
                continue  # Valid BSC URL
            elif url.startswith(("http://", "https://")):
                # Allow custom HTTPS endpoints
                continue
            else:
                raise ValueError(f"Invalid BSC RPC URL: {url}")

    def get_metadata(self) -> Dict[str, Any]:
        """Get BSC adapter metadata and capabilities.

        Returns:
            Metadata dictionary with BSC-specific info
        """
        base_metadata = super().get_metadata()

        # Override with BSC-specific metadata
        base_metadata.update({
            "name": "bsc",
            "network_name": self.NETWORK_CONFIGS[self.network]["name"],
            "chain_id": self.chain_id,
            "block_time": self.block_time,
            "supports": {
                **base_metadata["supports"],
                "bep20": True,  # BSC equivalent of ERC20
                "bep721": True,  # BSC equivalent of ERC721
                "bep1155": True,  # BSC equivalent of ERC1155
                "bnb_staking": True,
                "ethereum_compatible": True
            },
            "features": {
                **base_metadata.get("features", {}),
                "bep20": True,
                "bep721": True,
                "bep1155": True,
                "bnb_staking": True,
                "bnb_bridge": True,
                "ethereum_compatible": True,
                "fast_finality": True,
                "low_gas_fees": True
            },
            "network_specific": {
                "native_token": "BNB",
                "gas_token": "BNB",
                "consensus": "Proof of Staked Authority (PoSA)",
                "finality": "15 blocks (~45 seconds)",
                "max_gas_limit": 300000000,
                "base_fee": "100 gwei"
            }
        })

        return base_metadata

    async def get_gas_price(self) -> Dict[str, Any]:
        """Get current gas price information for BSC.

        Returns:
            Gas price information dictionary

        Raises:
            BlockchainAdapterError: If request fails
        """
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to BSC network",
                blockchain=self.name,
                network=self.network
            )

        try:
            # Get gas price from BSC
            gas_price = await self._execute_with_rate_limit(
                self._w3.eth.gas_price
            )

            return {
                "gas_price": str(gas_price),
                "gas_price_gwei": float(gas_price) / 1e9,  # Convert to Gwei
                "network": self.network,
                "timestamp": self._get_current_timestamp()
            }

        except Exception as e:
            self._handle_blockchain_error(e)

    async def estimate_gas(
        self,
        to: str,
        value: int = 0,
        data: str = "0x",
        from_address: Optional[str] = None
    ) -> int:
        """Estimate gas for transaction on BSC.

        Args:
            to: Recipient address
            value: Transaction value in wei
            data: Transaction data
            from_address: Sender address (optional)

        Returns:
            Estimated gas amount

        Raises:
            BlockchainAdapterError: If estimation fails
        """
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to BSC network",
                blockchain=self.name,
                network=self.network
            )

        try:
            # Build transaction object
            tx_params = {
                "to": to,
                "value": value,
                "data": data
            }

            if from_address:
                tx_params["from"] = from_address

            # Estimate gas
            gas_estimate = await self._execute_with_rate_limit(
                self._w3.eth.estimate_gas,
                tx_params
            )

            # Add buffer for BSC (typically lower than Ethereum)
            gas_with_buffer = int(gas_estimate * 1.1)  # 10% buffer
            return min(gas_with_buffer, 300000000)  # BSC max gas limit

        except Exception as e:
            self._handle_blockchain_error(e)

    async def get_bnb_balance(self, address: str) -> int:
        """Get BNB balance for an address on BSC.

        Args:
            address: BSC address

        Returns:
            Balance in wei

        Raises:
            BlockchainAdapterError: If request fails
        """
        # Use the inherited get_balance method from Ethereum adapter
        return await self.get_balance(address)

    async def get_transaction_receipt_with_retries(
        self,
        transaction_hash: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Get transaction receipt with retries for BSC.

        Args:
            transaction_hash: Transaction hash
            max_retries: Maximum number of retries

        Returns:
            Transaction receipt dictionary

        Raises:
            TransactionError: If transaction receipt is not found after retries
        """
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to BSC network",
                blockchain=self.name,
                network=self.network
            )

        last_error = None

        for attempt in range(max_retries):
            try:
                receipt = await self.get_transaction_receipt(transaction_hash)

                # Check if transaction was successful
                if receipt is not None:
                    return receipt

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Wait before retrying (BSC blocks are fast)
                    import asyncio
                    await asyncio.sleep(self.block_time)

        # If all retries failed
        from chain_listener.exceptions import TransactionError
        raise TransactionError(
            f"Transaction receipt {transaction_hash} not found after {max_retries} attempts",
            blockchain=self.name,
            network=self.network,
            transaction_hash=transaction_hash,
            last_error=str(last_error)
        )

    async def get_events_stream_with_polling(
        self,
        address: Optional[str] = None,
        topics: Optional[List[str]] = None,
        from_block: Optional[int] = None,
        poll_interval: float = 1.0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream BSC events with optimized polling for fast blocks.

        Args:
            address: Contract address to filter by
            topics: Event topics to filter by
            from_block: Starting block number
            poll_interval: Polling interval in seconds (default 1.0 for BSC)

        Yields:
            Event dictionaries as they occur

        Raises:
            BlockchainAdapterError: If streaming fails
        """
        if not self._connected or not self._w3:
            raise BlockchainAdapterError(
                "Not connected to BSC network",
                blockchain=self.name,
                network=self.network
            )

        current_block = from_block or await self.get_latest_block_number()

        while True:
            try:
                # Get latest block number
                latest_block = await self.get_latest_block_number()

                if latest_block > current_block:
                    # Get new logs
                    logs = await self.get_logs(
                        address=address,
                        topics=topics,
                        from_block=current_block + 1,
                        to_block=latest_block
                    )

                    for log in logs:
                        yield log

                    current_block = latest_block

                # BSC has fast blocks, so shorter polling interval
                await asyncio.sleep(min(poll_interval, self.block_time / 2))

            except Exception as e:
                self._handle_blockchain_error(e)
                # Wait before retrying
                await asyncio.sleep(self.block_time)

    def _get_current_timestamp(self) -> int:
        """Get current timestamp.

        Returns:
            Current Unix timestamp
        """
        from datetime import datetime, timezone
        return int(datetime.now(timezone.utc).timestamp())

    async def validate_address(self, address: str) -> bool:
        """Validate BSC address format.

        Args:
            address: Address to validate

        Returns:
            True if valid, False otherwise
        """
        # BSC uses the same address format as Ethereum
        if not address or not isinstance(address, str):
            return False

        # Basic Ethereum address validation
        if not address.startswith("0x"):
            return False

        if len(address) != 42:
            return False

        try:
            int(address, 16)
            return True
        except ValueError:
            return False

    async def get_network_stats(self) -> Dict[str, Any]:
        """Get BSC network statistics.

        Returns:
            Network statistics dictionary

        Raises:
            BlockchainAdapterError: If request fails
        """
        try:
            latest_block = await self.get_latest_block_number()
            gas_price = await self.get_gas_price()

            return {
                "network": self.network,
                "chain_id": self.chain_id,
                "latest_block": latest_block,
                "block_time": self.block_time,
                "gas_price": gas_price,
                "native_token": "BNB",
                "ethereum_compatible": True,
                "explorer_urls": self._get_explorer_urls(),
                "timestamp": self._get_current_timestamp()
            }

        except Exception as e:
            self._handle_blockchain_error(e)

    def _get_explorer_urls(self) -> List[str]:
        """Get explorer URLs for the current network.

        Returns:
            List of explorer URLs
        """
        if self.network == "mainnet":
            return [
                "https://bscscan.com",
                "https://explorer.binance.org"
            ]
        elif self.network == "testnet":
            return [
                "https://testnet.bscscan.com",
                "https://explorer.binance.org/smart-testnet"
            ]
        return []