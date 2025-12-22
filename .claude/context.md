# Chain Listener SDK - Core Context

## Project Overview
Universal multi-chain blockchain listener SDK that provides reusable monitoring capabilities across multiple blockchain networks. Focuses on asynchronous blockchain event listening and data processing in a single-instance deployment.

## Core Mission
Develop high-quality, well-tested blockchain monitoring solutions with exceptional reliability and performance.

## Critical Rules (Must Follow)
1. **Test-Driven Development**: Always write tests before production code. Every change must follow the full Red → Green → Refactor cycle from `tdd-workflow.md` with a failing test first, minimal implementation, then refactor, and finish by running the relevant test suite to confirm Green.
2. **Security First**: Never expose sensitive data or create vulnerabilities
3. **Quality Over Speed**: Understand requirements before implementation
4. **Async-First**: All operations must be async-compatible

## Technology Stack
- **Language**: Python 3.8+
- **Blockchain**: Web3.py for Ethereum-compatible chains
- **Async**: asyncio with aiohttp
- **Config**: Pydantic for type-safe configuration
- **Tests**: pytest with 90%+ coverage requirement
- **Dependencies**: Managed with Poetry, so run test and example_usage with poetry.

## Key Constraints
- Always use virtual environment (poetry)
- Network access available, use English for searches
- Use exa MCP for uncertain technical issues
- Follow TDD workflow strictly
- Maintain backward compatibility

## Architecture Overview
- **Multi-Chain Support**: Single instance monitoring multiple blockchains
- **Adapter Pattern**: Pluggable blockchain adapters
- **Event-Driven**: Callback-based event processing
- **Async Architecture**: Non-blocking event handling

## Project Structure
```
chain_listener/
├── src/chain_listener/          # Main package
│   ├── __init__.py
│   ├── core/                    # Core components
│   │   ├── listener.py         # Main ChainListener class
│   │   ├── adapter_registry.py # Adapter management
│   │   ├── callback_registry.py # Event callbacks
│   │   └── event_processor.py  # Event processing engine
│   ├── models/                  # Data models
│   │   ├── events.py           # Event data structures
│   │   └── config.py           # Configuration models
│   ├── adapters/                # Blockchain adapters
│   │   ├── base.py             # Base adapter interface
│   │   ├── ethereum.py         # Ethereum implementation
│   ├── utils/                   # Utilities
│   │   ├── address.py          # Address validation
│   │   ├── validation.py       # General validation
│   │   ├── conversion.py       # Data conversion
│   │   └── crypto.py           # Cryptographic helpers
│   └── exceptions.py           # Custom exceptions
├── tests/                       # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── fixtures/               # Test data
├── examples/                    # Usage examples
│   ├── basic_usage.py
│   └── config.yaml
├── docs/                        # Documentation
├── solution/                    # Technical solutions
├── pyproject.toml               # Poetry config
└── README.md
```

## Quality Standards
- 90%+ test coverage
- Type hints required
- Google-style docstrings
- PEP 8 compliance (88 char line width)

## Quick References
- Tests: `poetry run pytest`
- TDD Cycle: Red → Green → Refactor
- Main Class: `ChainListener` in core/listener.py
- Documentation: Check CLAUDE.md for detailed specs
