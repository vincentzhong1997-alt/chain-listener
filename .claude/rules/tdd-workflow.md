# TDD Workflow - Chain Listener SDK

## Core Philosophy
Write failing tests before production code, then make them pass and refactor.

## TDD Cycle: Red-Green-Refactor

### 1. Red Phase - Write Failing Test
```bash
# Create test file
touch tests/unit/test_new_feature.py

# Write test that describes desired behavior
def test_should_process_transfer_event():
    # Given
    event = create_transfer_event(value=100)

    # When
    result = processor.process_event(event)

    # Then
    assert result.success is True
    assert result.processed_value == 100
```

### 2. Green Phase - Make Test Pass
```python
# Write minimal code to pass the test
def process_event(self, event: TransferEvent) -> ProcessResult:
    return ProcessResult(
        success=True,
        processed_value=event.data['value']
    )
```

### 3. Refactor Phase - Improve Code
```python
# Refactor while keeping tests passing
def process_event(self, event: TransferEvent) -> ProcessResult:
    if not self._validate_event(event):
        return ProcessResult(success=False)

    return ProcessResult(
        success=True,
        processed_value=event.data['value']
    )
```

## Testing Principles

### Unit Testing (FIRST)
- **Fast**: Milliseconds execution time
- **Independent**: No dependencies on other tests
- **Repeatable**: Same result every time
- **Self-validating**: Auto pass/fail, no manual check
- **Timely**: Write before production code

### Unit Testing Best Practices
- One assertion per test
- Test name describes behavior
- Use AAA pattern (Arrange, Act, Assert)
- Mock external dependencies
- Don't test private methods

### Integration Testing
- Test real component interactions
- Verify external integrations (DB, APIs)
- End-to-end business flows
- Error scenarios and recovery
- Use isolated test environment

### Test Structure Example
```python
class TestEventProcessor:
    @pytest.fixture
    def processor(self):
        return EventProcessor()

    @pytest.mark.asyncio
    async def test_process_transfer_event_success(self, processor):
        # Arrange
        event = TransferEvent(from_addr="0x1...", to_addr="0x2...", value=100)

        # Act
        result = await processor.process_event(event)

        # Assert
        assert result.success is True
        assert result.processed_value == 100
```

## Quick Commands
```bash
# Create new test file
touch tests/unit/test_feature.py

# Run unit tests
poetry run pytest tests/unit/

# Run integration tests
poetry run pytest tests/integration/

# Run with coverage
poetry run pytest --cov=src/chain_listener
```

## Common Pitfalls to Avoid
- Testing implementation details
- Shared state between tests
- Brittle tests that break on refactoring
- Testing language features instead of business logic
- Missing edge cases in integration tests