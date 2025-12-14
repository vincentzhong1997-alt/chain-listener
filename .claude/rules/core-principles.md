# Core Principles - Chain Listener SDK

## Priority 1: Critical Rules (MUST Follow)

### Security & Safety
- **Never expose sensitive data**: No private keys, seeds, or credentials in logs or code
- **Input validation**: Validate all external inputs (addresses, transaction hashes, etc.)
- **Error handling**: Handle errors gracefully without exposing system internals
- **No command injection**: Never execute user-provided strings as commands

### Test-Driven Development
- **Tests first**: Always write failing tests before production code
- **Red-Green-Refactor**: Follow the TDD cycle strictly
- **Coverage requirement**: Maintain minimum 90% test coverage
- **Test independence**: Tests must run independently without shared state

### Code Quality
- **Type hints mandatory**: All function signatures must have type hints
- **Documentation required**: All public modules, classes, and functions need Google-style docstrings
- **PEP 8 compliance**: Strict adherence to Python style guide
- **No production code without tests**: Every feature must have corresponding tests
- **No over-engineering**: Don't write code that won't be used or isn't necessary

### Simplicity & Pragmatism
- **YAGNI principle**: You Ain't Gonna Need It - don't implement features without clear requirements
- **Simple solutions**: Choose the simplest solution that meets current needs
- **Avoid premature abstraction**: Don't create abstractions until you have multiple concrete implementations
- **Real value over imagined flexibility**: Solve actual problems, not hypothetical ones

## Priority 2: Important Guidelines (SHOULD Follow)

### Architecture Principles
- **Single Responsibility**: Each class/function should have one clear purpose
- **Don't Repeat Yourself**: Extract common functionality to utilities
- **Interface-based design**: Use abstract base classes when multiple implementations exist
- **Async-first**: All I/O operations must be asynchronous
- **Practical design**: Build what's needed now, not what might be needed later

### Performance & Reliability
- **Efficient async patterns**: Use proper asyncio patterns, avoid blocking calls
- **Resource management**: Proper cleanup of resources (connections, subscriptions)
- **Error recovery**: Implement retry mechanisms for transient failures
- **Memory efficiency**: Avoid memory leaks in long-running listeners

### Maintainability
- **Clear naming**: Use descriptive names for classes, functions, and variables
- **Consistent patterns**: Follow established patterns in the codebase
- **Modular design**: Keep modules focused and loosely coupled
- **Progress tracking**: Update PROGRESS.md when reaching milestones

## Priority 3: Recommendations (Nice to Have)

### Development Workflow
- **Small commits**: Make frequent, small commits with clear messages
- **Code review**: Self-review code before considering it complete
- **Documentation updates**: Keep documentation in sync with code changes
- **Example code**: Provide usage examples for new features

### Optimization
- **Profile before optimizing**: Measure performance before making changes
- **Consider readability**: Optimize for clarity first, performance second
- **Use built-in features**: Leverage Python standard library and proven libraries
- **Avoid premature optimization**: Don't optimize without proven need

## Decision Framework

When making implementation decisions:

1. **Security trumps everything**: If unsure, choose the more secure option
2. **Is it needed now?**: Don't build for hypothetical future requirements (YAGNI)
3. **Testability matters**: Prefer designs that are easy to test
4. **Simplicity over complexity**: Choose the simplest solution that works
5. **Consistency over cleverness**: Follow existing patterns
6. **Performance last**: Optimize only after correctness is ensured