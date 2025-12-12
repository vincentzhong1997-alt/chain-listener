"""Basic usage example for ChainListener SDK.

This example demonstrates how to use the ChainListener SDK to
monitor blockchain events.
"""

import asyncio
import logging
from chain_listener import ChainListener, ChainListenerConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_transfer(event):
    """Handle transfer events."""
    print(f"🔄 Transfer detected:")
    print(f"   From: {event.parameters.get('from', 'Unknown')}")
    print(f"   To: {event.parameters.get('to', 'Unknown')}")
    print(f"   Value: {event.parameters.get('value', 'Unknown')}")
    print(f"   Transaction: {event.transaction_hash}")
    print("-" * 50)


async def handle_approval(event):
    """Handle approval events."""
    print(f"✅ Approval detected:")
    print(f"   Owner: {event.parameters.get('owner', 'Unknown')}")
    print(f"   Spender: {event.parameters.get('spender', 'Unknown')}")
    print(f"   Value: {event.parameters.get('value', 'Unknown')}")
    print(f"   Transaction: {event.transaction_hash}")
    print("-" * 50)


async def main():
    """Main example function."""
    # Method 1: Create configuration programmatically
    config_data = {
        "chains": {
            "ethereum": {
                "enabled": True,
                "chain_type": "ethereum",
                "chain_id": 1,
                "confirmation_blocks": 12,
                "polling_interval": 15000,  # 15 seconds
                "rpc_urls": [
                    {"url": "https://eth-mainnet.g.alchemy.com/v2/8kg5BVMw4kdwNLo0bMkA6", "priority": 1},
                    {"url": "https://eth-mainnet.alchemyapi.io/v2/demo", "priority": 2}
                ],
                "contracts": [
                    {
                        "name": "WBTC",
                        "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                        "events": ["Transfer", "Approval"]
                    },
                    {
                        "name": "USDC",
                        "address": "0xA0B86a33E6441E1cA48558572A901D6885543326",
                        "events": ["Transfer"]
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

    # Create configuration
    config = ChainListenerConfig(**config_data)

    # Initialize the chain listener
    listener = ChainListener(config)

    try:
        # Register event callbacks
        logger.info("📝 Registering event callbacks...")

        # Ethereum WBTC events
        listener.on_event(
            "ethereum",
            "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
            "Transfer",
            handle_transfer
        )

        listener.on_event(
            "ethereum",
            "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
            "Approval",
            handle_approval
        )

        # Ethereum USDC events
        listener.on_event(
            "ethereum",
            "0xA0B86a33E6441E1cA48558572A901D6885543326",
            "Transfer",
            handle_transfer
        )

        # Get system status
        logger.info("📊 Getting system status...")
        status = await listener.get_system_status()
        print(f"Configured chains: {status['configured_chains']}")
        print(f"Enabled chains: {status['enabled_chains']}")

        # Get latest block numbers
        logger.info("🔍 Getting latest block numbers...")
        eth_block = await listener.get_latest_block("ethereum")
        print(f"Ethereum latest block: {eth_block}")

        # Start listening for events
        logger.info("🎧 Starting to listen for events...")
        print("Press Ctrl+C to stop listening")
        print("=" * 60)

        await listener.start_listening()

        # Keep listening until interrupted
        try:
            while True:
                await asyncio.sleep(1)

                # Print status every 30 seconds
                if hasattr(main, '_last_status'):
                    if asyncio.get_event_loop().time() - main._last_status > 30:
                        status = await listener.get_system_status()
                        print(f"\n📈 Status update: {status['is_listening']}")
                        main._last_status = asyncio.get_event_loop().time()
                else:
                    main._last_status = asyncio.get_event_loop().time()

        except KeyboardInterrupt:
            logger.info("🛑 Stopping listener...")
            await listener.stop_listening()

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        await listener.stop_listening()


async def example_with_config_file():
    """Example using configuration file."""
    try:
        # Method 2: Load configuration from YAML file
        listener = ChainListener.from_config_file("examples/config.yaml")

        # Register callbacks
        listener.on_event(
            "ethereum",
            "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
            "Transfer",
            lambda event: print(f"File-based transfer: {event.transaction_hash}")
        )

        # Use context manager for automatic cleanup
        async with listener as l:
            print("Listening with file-based config...")
            await asyncio.sleep(10)  # Listen for 10 seconds

    except Exception as e:
        print(f"Config file example failed: {e}")


if __name__ == "__main__":
    print("🚀 Chain Listener SDK - Basic Usage Example")
    print("=" * 60)

    # Run the main example
    asyncio.run(main())

    # Uncomment to run config file example
    # asyncio.run(example_with_config_file())