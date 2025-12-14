# Bug Fixing Prompt

## Task: Fix Bug

### Before You Start
1. **Understand the Bug**
   - What is the expected behavior?
   - What is actually happening?
   - What are the error messages/logs?

2. **Reproduce the Bug**
   - Create a minimal reproduction case
   - Write a failing test that demonstrates the issue
   - Identify the root cause

3. **Assess Impact**
   - How critical is this bug?
   - What's the affected functionality?
   - Are there workarounds?

### Bug Fixing Process

#### Step 1: Write a Test That Reproduces the Bug
```python
def test_should_handle_invalid_transaction_hash(self):
    # This test should fail before the fix
    adapter = EthereumAdapter(config)

    with pytest.raises(ValueError, match="Invalid transaction hash"):
        await adapter.get_transaction("")
```

#### Step 2: Fix the Issue
- Make the smallest change possible
- Focus only on fixing this bug
- Don't introduce new features

#### Step 3: Verify the Fix
- Ensure the test passes
- Run the full test suite
- Check for regressions

### Fixing Guidelines

#### Debugging Steps
1. Add logging to understand flow
2. Use debugger to trace execution
3. Check assumptions about inputs
4. Verify external dependencies

#### Common Bug Categories
- **Input Validation**: Missing or incorrect validation
- **Edge Cases**: Unhandled boundary conditions
- **Async Issues**: Race conditions, incorrect await usage
- **Resource Leaks**: Unclosed connections, file handles
- **Type Errors**: Wrong type assumptions

#### Example Fixes

**Input Validation Bug**
```python
# Before: No validation
async def get_transaction(self, tx_hash: str) -> Dict:
    return await self.web3.eth.get_transaction(tx_hash)

# After: Add validation
async def get_transaction(self, tx_hash: str) -> Dict:
    if not tx_hash or not isinstance(tx_hash, str):
        raise ValueError("Transaction hash must be a non-empty string")
    if not tx_hash.startswith('0x') or len(tx_hash) != 66:
        raise ValueError("Invalid transaction hash format")
    return await self.web3.eth.get_transaction(tx_hash)
```

**Race Condition Fix**
```python
# Before: Potential race condition
def get_connection(self):
    if not self._connection:
        self._connection = create_connection()
    return self._connection

# After: Thread-safe
async def get_connection(self):
    if not self._connection:
        async with self._lock:
            if not self._connection:
                self._connection = await create_connection()
    return self._connection
```

### After the Fix
1. **Add Regression Tests**
   - Ensure this bug can't reoccur
   - Test similar scenarios

2. **Update Documentation**
   - If behavior changed
   - Add notes about edge cases

3. **Consider Root Cause**
   - Could this happen elsewhere?
   - Should we add more defensive checks?

### Quality Checklist
- [ ] Bug reproduction test written
- [ ] Fix is minimal and focused
- [ ] All tests pass
- [ ] No regressions introduced
- [ ] Root cause addressed
- [ ] Documentation updated if needed

### Remember
- Understand before fixing
- Write tests that demonstrate the bug
- Make minimal changes
- Verify thoroughly
- Learn from the bug