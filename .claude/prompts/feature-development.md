# Feature Development Prompt

## Task: Implement New Feature

### Before You Start
1. **Understand Requirements**
   - What is the feature's purpose?
   - What problem does it solve?
   - How will it be used?

2. **Review Existing Code**
   - Check similar implementations
   - Understand current architecture
   - Identify reusable components

3. **Plan Your Approach**
   - Identify test cases needed
   - Consider edge cases
   - Think about integration points

### Implementation Steps

#### Step 1: Write Tests First
```bash
# Create test file
touch tests/unit/test_[feature].py

# Write failing tests covering:
# - Happy path
# - Edge cases
# - Error conditions
# - Integration scenarios
```

#### Step 2: Implement Minimal Solution
- Write just enough code to make tests pass
- Focus on core functionality
- Don't add extra features yet

#### Step 3: Refactor and Improve
- Improve code structure
- Add necessary documentation
- Ensure performance is acceptable
- Run full test suite

### Key Considerations

#### Architecture
- Does this fit existing patterns?
- Should it use adapter pattern?
- Is async/await required?
- How does it integrate with ChainListener?

#### Security
- Validate all inputs
- Handle errors gracefully
- Don't expose sensitive data
- Consider rate limiting if applicable

#### Testing
- Minimum 90% coverage
- Mock external dependencies
- Test both unit and integration
- Use realistic test data

### Example: Adding New Blockchain Support

```python
# 1. First, write the test
def test_solana_adapter_connect_success(self):
    adapter = SolanaAdapter(self.solana_config)
    await adapter.connect()
    assert adapter.is_connected is True

# 2. Then implement minimal adapter
class SolanaAdapter(BaseAdapter):
    async def connect(self) -> None:
        self._client = AsyncClient(self.config.rpc_url)
        await self._client.is_connected()

# 3. Refactor with error handling, logging, etc.
```

### Quality Checklist
- [ ] Tests written before code
- [ ] All tests passing
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Integration tested
- [ ] Performance considered
- [ ] Security reviewed

### Remember
- Build what's needed now (YAGNI)
- Keep it simple
- Test everything
- Document important decisions