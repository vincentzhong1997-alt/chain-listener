# Chain Listener SDK

A universal multi-chain distributed blockchain listener SDK that provides reusable multi-chain monitoring capabilities. The SDK focuses on asynchronous blockchain event listening and data processing, offering flexible solutions for different business scenarios.

## Features

- **Universal Multi-Chain Support**: Ethereum, BSC, Polygon, Arbitrum, Optimism, Avalanche, Solana, TRON, Kava, Osmosis, Base
- **Distributed Architecture**: Support for multi-instance deployment with automatic load balancing
- **Event-Driven**: Callback-based event processing with user-defined handlers
- **Fault Tolerant**: Automatic failover and recovery mechanisms
- **High Performance**: Async/await architecture with efficient event processing
- **Flexible Deployment**: From simple standalone to distributed cluster

## Quick Start

### Simple Mode (Standalone)

```python
from chain_listener import QuickListener

# Create listener
listener = QuickListener.from_config("config.yaml")

# Register contract and event handler
listener.add_contract(
    chain='ethereum',
    address='0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599'  # WBTC
).on_event('Transfer', handle_transfer)

# Start listening (async, non-blocking)
import asyncio
listener_task = await listener.start_async()

# Continue with other tasks...
```

### Distributed Mode

```python
from chain_listener import DistributedListener
import aioredis
from motor.motor_asyncio import AsyncIOMotorClient

# Create listener
listener = DistributedListener.from_config("production_config.yaml")

# Register clients
listener.register_redis_client(aioredis.from_url("redis://localhost:6379/0"))
listener.register_mongodb_client(AsyncIOMotorClient("mongodb://localhost:27017"))

# Register contract and event handler
listener.add_contract(
    chain='ethereum',
    address='0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599'
).on_event('Transfer', handle_transfer)

# Start distributed listening
listener_task = await listener.start_distributed_async()
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Configuration Guide](docs/configuration.md)
- [API Reference](docs/api.md)
- [Examples](examples/)

## Development

### Setup

```bash
# Install Poetry
pip install poetry

# Install dependencies
poetry install

# Activate virtual environment
poetry env activate
```

### Testing

This project follows Test-Driven Development (TDD) principles and has comprehensive test coverage.

```bash
# Run tests with coverage
poetry run pytest --cov=chain_listener --cov-report=html

# Run specific test file
poetry runpytest tests/unit/test_events.py -v

# Run all tests
poetry run pytest
```

### Code Quality

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

## License

[License Name]

## Contributing

Please read our contributing guidelines and code of conduct before submitting pull requests.