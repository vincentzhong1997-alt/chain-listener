# Chain Listener SDK - Quick Start Guide

🚀 **Universal multi-chain blockchain event listener SDK**
Monitor events across Ethereum, BSC, Solana, and TRON with a single unified API.

## Installation

```bash
# Install the SDK
pip install chain-listener

# Or install from source
git clone https://github.com/chain-listener/chain-listener
cd chain-listener
poetry install
```

## Quick Start

### 1. Basic Usage (5 lines of code)

```python
import asyncio
from chain_listener import ChainListener

async def handle_transfer(event):
    print(f"💰 Transfer: {event.parameters.get('from')} → {event.parameters.get('to')}")

async def main():
    # Load from configuration file
    listener = ChainListener.from_config_file("config.yaml")

    # Register event callback
    listener.on_event("ethereum", "0x...", "Transfer", handle_transfer)

    # Start listening
    await listener.start_listening()

asyncio.run(main())
```

### 2. Configuration File

Create `config.yaml`:

```yaml
version: "1.0"

global_config:
  max_concurrent_processing: 10
  log_level: "INFO"

chains:
  ethereum:
    enabled: true
    chain_type: "ethereum"
    chain_id: 1
    confirmation_blocks: 12
    polling_interval: 15000  # 15 seconds
    rpc_urls:
      - url: "https://eth.llamarpc.com"
        priority: 1
    contracts:
      - name: "WBTC"
        address: "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
        events: ["Transfer", "Approval"]

  bsc:
    enabled: true
    chain_type: "bsc"
    chain_id: 56
    confirmation_blocks: 6
    polling_interval: 3000  # 3 seconds
    rpc_urls:
      - url: "https://bsc-dataseed.binance.org"
        priority: 1
```

### 3. Advanced Usage

```python
import asyncio
from chain_listener import ChainListener, ChainListenerConfig

async def main():
    # Create configuration programmatically
    config = ChainListenerConfig(
        chains={
            "ethereum": {
                "chain_type": "ethereum",
                "chain_id": 1,
                "confirmation_blocks": 12,
                "polling_interval": 15000,
                "rpc_urls": [{"url": "https://eth.llamarpc.com", "priority": 1}],
                "contracts": [
                    {
                        "name": "USDC",
                        "address": "0xA0b86a33E6441e1cA48558572A901D6885543326",
                        "events": ["Transfer", "Approval"]
                    }
                ]
            }
        }
    )

    listener = ChainListener(config)

    # Register multiple callbacks
    def handle_transfer(event):
        amount = int(event.parameters.get('value', 0))
        print(f"Transfer of {amount} USDC")

    def handle_approval(event):
        owner = event.parameters.get('owner')
        print(f"Approval from {owner}")

    listener.on_event("ethereum", "0xA0b86a33E6441e1cA48558572A901D6885543326", "Transfer", handle_transfer)
    listener.on_event("ethereum", "0xA0b86a33E6441e1cA48558572A901D6885543326", "Approval", handle_approval)

    # Use context manager for automatic cleanup
    async with listener:
        # Get system status
        status = await listener.get_system_status()
        print(f"Status: {status}")

        # Get latest block
        latest_block = await listener.get_latest_block("ethereum")
        print(f"Latest block: {latest_block}")

        # Keep listening
        print("Listening for events... Press Ctrl+C to stop")
        await asyncio.sleep(60)  # Listen for 60 seconds

asyncio.run(main())
```

## Key Features

### 🔗 **Multi-Chain Support**
- **Ethereum & EVM Compatible**: ETH, BSC, Polygon, Arbitrum
- **Solana**: Program-based event monitoring
- **TRON**: TRC-20/TRC-721 token events

### ⚡ **High Performance**
- **Async Processing**: Built on asyncio for high concurrency
- **Batch Operations**: Efficient event processing in batches
- **Smart Polling**: Adaptive polling intervals

### 🛡️ **Reliable & Safe**
- **Reorg Protection**: Automatic blockchain reorganization detection
- **Error Isolation**: Failed callbacks don't affect other events
- **Connection Recovery**: Automatic reconnection with retry logic

### 🔧 **Developer Friendly**
- **Simple API**: Start listening in 5 lines of code
- **Flexible Configuration**: YAML files or programmatic setup
- **Type Safe**: Full type annotations throughout

## Configuration Options

### Global Settings
```yaml
global_config:
  max_concurrent_processing: 10    # Max concurrent event processing
  event_batch_size: 100           # Batch size for event processing
  callback_error_handling: "ignore" # ignore|retry|stop
  log_level: "INFO"               # DEBUG|INFO|WARN|ERROR
```

### Chain Settings
```yaml
chains:
  ethereum:
    enabled: true                 # Enable/disable this chain
    chain_type: "ethereum"        # Chain type
    chain_id: 1                   # Chain ID
    confirmation_blocks: 12       # Blocks to wait for finality
    polling_interval: 15000       # Polling interval (ms)
    rpc_urls:                     # RPC endpoints with priority
      - url: "https://eth.llamarpc.com"
        priority: 1
    contracts:                    # Contracts to monitor
      - name: "WBTC"
        address: "0x2260FAC5..."
        events: ["Transfer", "Approval"]
```

## Event Callbacks

### Event Object Structure
```python
@dataclass
class DecodedEvent:
    chain_type: ChainType        # ethereum, bsc, solana, tron
    contract_address: str         # Contract that emitted the event
    event_name: str               # Name of the event
    parameters: Dict[str, Any]    # Decoded event parameters
    block_number: int             # Block number
    transaction_hash: str         # Transaction hash
    log_index: int               # Log index within transaction
    timestamp: int               # Event timestamp
```

### Callback Examples
```python
async def handle_transfer(event: DecodedEvent):
    """Handle ERC-20 Transfer events."""
    from_address = event.parameters.get('from')
    to_address = event.parameters.get('to')
    amount = int(event.parameters.get('value', 0))

    print(f"📡 Transfer detected:")
    print(f"   From: {from_address}")
    print(f"   To: {to_address}")
    print(f"   Amount: {amount}")
    print(f"   Tx: {event.transaction_hash}")

async def handle_swap(event: DecodedEvent):
    """Handle DEX swap events."""
    token_in = event.parameters.get('tokenIn')
    token_out = event.parameters.get('tokenOut')
    amount_in = event.parameters.get('amountIn')

    # Process swap logic here
    print(f"🔄 Swap: {amount_in} {token_in} → {token_out}")
```

## Best Practices

### 1. **Error Handling**
```python
async def safe_callback(event: DecodedEvent):
    try:
        # Your business logic here
        process_event(event)
    except Exception as e:
        logger.error(f"Error processing event: {e}")
        # Don't re-raise to avoid affecting other events
```

### 2. **Performance Optimization**
```python
# Configure appropriate batch sizes and concurrency
config = ChainListenerConfig(
    global_config={
        "max_concurrent_processing": 20,  # Based on your needs
        "event_batch_size": 200,         # Optimize for your workload
    }
)
```

### 3. **Production Deployment**
```python
import logging
from chain_listener import ChainListener

# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    listener = ChainListener.from_config_file("production-config.yaml")

    # Register callbacks with metadata
    listener.on_event(
        "ethereum",
        "0x...",
        "Transfer",
        handle_transfer,
        metadata={"priority": "high", "retry_count": 3}
    )

    # Use context manager for graceful shutdown
    async with listener:
        # Run indefinitely
        while True:
            await asyncio.sleep(1)
```

## Support & Community

- **Documentation**: [Full Documentation](https://chain-listener.readthedocs.io)
- **Issues**: [GitHub Issues](https://github.com/chain-listener/chain-listener/issues)
- **Discord**: [Community Discord](https://discord.gg/chain-listener)
- **Examples**: [More Examples](../examples/)

## Next Steps

1. **Explore Examples**: Check out `examples/` directory for more use cases
2. **Read Full Docs**: Visit our comprehensive documentation
3. **Join Community**: Get help and share your use cases
4. **Contribute**: See CONTRIBUTING.md for development guidelines

---

🎉 **Happy coding with Chain Listener SDK!**
Monitor any blockchain event with ease and confidence.