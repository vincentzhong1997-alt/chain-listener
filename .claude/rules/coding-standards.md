# Coding Standards - Chain Listener SDK

## Core Rules

### Formatting (PEP 8)
- **Indentation**: 4 spaces, no tabs
- **Line width**: 88 characters
- **Imports**: Standard → Third-party → Local (grouped with blank lines)
- **Strings**: Use f-strings for formatting

### Naming Conventions
- **Modules**: `lowercase_with_underscores`
- **Classes**: `CapitalizedCamelCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `ALL_CAPS`

### Type Hints (Mandatory)
```python
def process_event(event: ChainEvent, timeout: Optional[float] = None) -> bool:
    """Process event with timeout."""
    pass

class Transaction:
    def __init__(self, hash: str, value: int) -> None:
        self.hash = hash
        self.value = value
        self.timestamp: Optional[float] = None
```

### Documentation (Google Style)
```python
def calculate_gas_price(base_fee: float, priority_fee: float) -> float:
    """Calculate total gas price.

    Args:
        base_fee: Network base fee
        priority_fee: Priority fee for faster inclusion

    Returns:
        Total gas price
    """
    return base_fee + priority_fee
```

## Organization

### File Structure
1. Imports (standard → third-party → local)
2. Constants
3. Classes/Functions
4. Private helpers (`_prefixed`)
5. `if __name__ == "__main__"` (if needed)

### Class Structure
1. Class attributes/constants
2. `__init__`
3. Public methods
4. Abstract methods
5. Private methods

## Error Handling
```python
# Custom exceptions
class AdapterError(ChainListenerError):
    def __init__(self, message: str, chain_type: str) -> None:
        super().__init__(f"[{chain_type}] {message}")
        self.chain_type = chain_type

# Error handling pattern
async def fetch_data(self) -> Optional[Dict]:
    try:
        return await self._client.get("endpoint")
    except NetworkError as e:
        logger.error(f"Network error: {e}")
        return None
```

## Testing Pattern
```python
class TestEthereumAdapter:
    @pytest.fixture
    def adapter(self, config):
        return EthereumAdapter(config)

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter):
        with patch.object(adapter, '_connect') as mock_connect:
            await adapter.connect()
            mock_connect.assert_called_once()
```

## Quick Checklist
- [ ] Type hints on all functions
- [ ] Google-style docstrings for public APIs
- [ ] Functions under 40 lines
- [ ] No wildcard imports
- [ ] Proper async/await usage
- [ ] Input validation
- [ ] Error handling
- [ ] Tests written before implementation