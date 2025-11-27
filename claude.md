# Chain Listener SDK Development Guide

## Project Overview
This is a universal multi-chain distributed blockchain listener SDK that provides reusable multi-chain monitoring capabilities. The SDK focuses on asynchronous blockchain event listening and data processing, offering flexible solutions for different business scenarios.

## Development Notice
- **Network Access**: Internet access is available. All searches and documentation should be in English. For uncertain technical issues (SQLAlchemy/Web3), use exa MCP.
- **Environment**: Always work in virtual environment if venv exists. Use standardized, readable commit messages for Git.
- **Planning**: Default to deep thinking and step-by-step planning. For complex or high-risk tasks, provide overall plan first, get confirmation once, then implement without repeated confirmations.
- **Quality**: Quality over speed, understanding over blind execution.

## Project Documentation
Detailed SDK architecture documentation is available in the `solution/` directory.

## SDK Development Standards

### Project Directory Structure
```
chain_listener/
├── src/
│   └── chain_listener/          # Package name using underscores
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── listener.py      # Main blockchain listener
│       │   ├── coordinator.py   # Distributed coordination
│       │   └── processor.py     # Event processing engine
│       ├── models/
│       │   ├── __init__.py
│       │   ├── events.py        # Event data models
│       │   └── config.py        # Configuration models
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── ethereum.py      # Ethereum adapter
│       │   ├── bsc.py          # BSC adapter
│       │   └── base.py         # Base adapter interface
│       ├── exceptions.py        # Custom exceptions
│       └── utils.py             # Utility functions
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
├── examples/
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── test.txt
├── setup.py
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

### Code Spec

#### Code Style & Formatting (强制)
- **基准**：严格遵循 PEP 8。
- **格式化**：
  - 缩进：必须使用 4 个空格，禁止使用 Tab。
  - 行宽：最大 88 字符 (Black default)。
  - 字符串：使用 f-strings 进行格式化。
- **导入规范 (Imports)**：
  - 顺序：标准库 -> 第三方库 -> 本地库 (每组间空一行)。
  - 必须使用绝对导入。
  - **禁止**使用通配符导入 (`from module import *`)。

#### Naming Conventions (命名约定)
- **Package/Module**: `lowercase_with_underscores` (如 `chain_listener`, `utils.py`)，保持简短。
- **Class**: `CapitalizedCamelCase` (如 `BlockchainListener`)。
- **Function/Variable**: `snake_case` (如 `get_user_profile`, `user_id`)。
- **Constant**: `ALL_CAPS` (如 `MAX_CONNECTIONS`)。

#### Type Hints & Documentation (强制)
- **类型注解 (Type Hints)**：
  - **所有**函数签名（参数及返回值）必须包含类型注解。
  - 复杂变量需显式标注类型。
  - 使用 `typing` 模块或 Python 原生类型写法，确保可通过 `mypy` 检查。
- **文档字符串 (Docstrings)**：
  - 所有模块、类、公共方法必须编写文档。
  - **风格**：严格遵循 **Google Style** (包含 Args, Returns, Raises)。

#### Architecture & Design Principles
- **DRY (Don't Repeat Yourself)**：禁止逻辑、常量或配置重复。立即提取为 `utils`、`constants` 或独立类。
- **SRP (Single Responsibility)**：
  - 每个类仅负责一个核心任务。
  - 单个函数长度建议不超过 40 行。
  - 避免“上帝类”或“上帝函数”。
- **Extensibility (推荐)**：
  - 关键业务模块必须基于**接口**设计。
  - 预见变化点时（如多种支付方式），优先使用策略模式或工厂模式，避免复杂的 `if-else` 链。

#### Example Reference
请参照以下范例的代码风格、类型标注和文档写法：

```python
from typing import Optional
from .models import User

def calculate_price(base: float, tax_rate: float) -> float:
    """计算含税价格。

    Args:
        base: 不含税的基础价格。
        tax_rate: 税率，例如 0.1 代表 10%。

    Returns:
        计算得出的含税总价。

    Raises:
        ValueError: 如果 base 或 tax_rate 为负数。
    """
    if base < 0 or tax_rate < 0:
        raise ValueError("价格和税率不能为负数")
    return base * (1 + tax_rate)
```

### SDK Design Principles
- **User-friendly Design**: Simple API with reasonable defaults
- **Asynchronous First**: All operations should be async-compatible
- **Event-driven Architecture**: Callback-based event processing
- **Fault Tolerance**: Graceful handling of network issues and failures
- **Scalability**: Support for both single-instance and distributed deployment
- **Extensibility**: Plugin architecture for custom blockchain adapters

### Dependency Management

**Goal**: Ensure reproducibility, security, and maintainability of dependencies.

- **Use Poetry for Dependency Management**
  - Poetry provides integrated solution for dependency resolution, virtual environment management, and packaging.

  ```toml
  # pyproject.toml
  [tool.poetry]
  name = "chain-listener"
  version = "0.1.0"
  description = "Universal multi-chain distributed blockchain listener SDK"

  [tool.poetry.dependencies]
  python = "^3.9"
  web3 = "^6.11.0"
  aiohttp = "^3.9.0"
  aioredis = "^2.0.0"
  motor = "^3.3.0"
  pydantic = "^2.5.0"
  async-timeout = "^4.0.3"

  [tool.poetry.group.dev.dependencies]
  pytest = "^7.4.3"
  pytest-asyncio = "^0.21.1"
  black = "^23.11.0"
  mypy = "^1.7.1"
  flake8 = "^6.1.0"
  pre-commit = "^3.6.0"

  [build-system]
  requires = ["poetry-core"]
  build-backend = "poetry.core.masonry.api"
  ```

- **Dependency Layering**
  - Clear separation of production, development, and testing dependencies
  - Use dependency groups (Poetry) or multiple requirements files (pip)

  ```bash
  # Poetry dependency groups
  poetry add pytest --group test
  poetry add black --group dev
  poetry add web3 --group core
  ```

### Core Technology Stack
- **Blockchain Interaction**: Web3.py for Ethereum-compatible chains
- **Async Framework**: asyncio with aiohttp for HTTP requests
- **Distributed Coordination**: aioredis for coordination and deduplication
- **Data Persistence**: Motor (async MongoDB driver) for progress storage
- **Configuration**: Pydantic for type-safe configuration management

### Documentation & Comments
- Use Google-style docstrings for all public modules, classes, and functions
- Include type hints in all function signatures
- Write clear, concise comments explaining complex logic
- Maintain a comprehensive README with quick start guide
- Document all configuration options and examples

### Testing Strategy
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test interaction between components
- **End-to-End Tests**: Test complete event flow from blockchain to processing
- **Performance Tests**: Validate performance under load
- Use pytest with pytest-asyncio for async testing
- Mock external dependencies (blockchain nodes, Redis, MongoDB)

### Test-Driven Development (TDD) Workflow

**TDD Philosophy**: Write failing tests before writing production code, then make them pass and refactor. This ensures comprehensive test coverage, better design, and fewer bugs.

#### TDD Cycle (Red-Green-Refactor)

1. **Red Phase**: Write a failing test that defines the desired behavior
2. **Green Phase**: Write minimal production code to make the test pass
3. **Refactor Phase**: Improve code quality while maintaining test coverage

#### TDD Development Process

**Step 1: Test Planning**
- Identify the feature or functionality to implement
- Define specific test cases covering expected behavior, edge cases, and error conditions
- Prioritize tests based on user value and complexity

**Step 2: Write Failing Tests**
```bash
# Create test file following naming convention
touch tests/unit/test_new_feature.py

# Write tests before implementation
# Tests should be descriptive and follow AAA pattern (Arrange, Act, Assert)
```

**Step 3: Run Tests to Confirm Failure**
```bash
# Ensure tests fail for the right reasons
pytest tests/unit/test_new_feature.py -v

# Tests should clearly indicate what's missing
```

**Step 4: Implement Minimal Code**
- Write just enough production code to make tests pass
- Focus on functionality, not perfection
- Avoid gold-plating or over-engineering

**Step 5: Run Tests to Confirm Success**
```bash
# All tests should now pass
pytest tests/unit/test_new_feature.py -v --cov=chain_listener
```

**Step 6: Refactor and Improve**
- Improve code structure, readability, and performance
- Maintain test coverage during refactoring
- Run tests after each refactoring change

**Step 7: Review and Repeat**
- Review test quality and coverage
- Add additional test cases if needed
- Repeat cycle for next feature component

#### TDD Best Practices

**Test Structure**
- Follow AAA pattern (Arrange, Act, Assert)
- Use descriptive test names that explain the behavior
- One assertion per test when possible
- Test both happy path and error conditions

**Test Organization**
```python
# Example test structure
class TestBlockchainListener:
    @pytest.fixture
    def listener_config(self):
        return {"network": "ethereum", "rpc_url": "http://localhost:8545"}

    async def test_listener_connects_successfully(self, listener_config):
        # Arrange
        listener = BlockchainListener(listener_config)

        # Act
        await listener.connect()

        # Assert
        assert listener.is_connected == True

    async def test_listener_raises_error_with_invalid_config(self):
        # Arrange
        invalid_config = {"network": "invalid"}
        listener = BlockchainListener(invalid_config)

        # Act & Assert
        with pytest.raises(InvalidConfigError):
            await listener.connect()
```

**Mock Strategy**
- Mock external dependencies (blockchain nodes, databases, APIs)
- Use dependency injection for easier testing
- Create realistic test data and scenarios
- Don't mock the system under test

**Coverage Requirements**
- Maintain minimum 90% line coverage
- Aim for 100% coverage for critical business logic
- Use coverage reports to identify untested code paths

#### TDD Integration with Git Workflow

**Pre-commit TDD Integration**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
        args: ["--cov=chain_listener", "--cov-fail-under=90"]
```

**TDD Branch Strategy**
1. Create feature branch
2. Write failing tests for new feature
3. Implement feature to make tests pass
4. Ensure 100% test coverage
5. Run full test suite including integration tests
6. Submit pull request with test results

#### TDD Examples for Common Scenarios

**New Functionality**
```python
# 1. Write test first
async def test_event_processor_filters_by_contract_address(self):
    # Arrange
    processor = EventProcessor()
    event = MockEvent(contract_address="0x123...")
    processor.set_contract_filter("0x123...")

    # Act
    result = await processor.process_event(event)

    # Assert
    assert result.processed == True
    assert result.filtered == False
```

**Error Handling**
```python
async def test_listener_handles_network_timeout_gracefully(self):
    # Arrange
    listener = BlockchainListener({"timeout": 1})

    # Act & Assert
    with pytest.raises(NetworkTimeoutError):
        await listener.connect_with_retry(max_attempts=1)
```

**Edge Cases**
```python
async def test_coordinator_handles_empty_event_list(self):
    # Arrange
    coordinator = EventCoordinator()
    events = []

    # Act
    results = await coordinator.process_batch(events)

    # Assert
    assert results == []
    assert coordinator.processed_count == 0
```

#### TDD Metrics and Monitoring

**Code Quality Metrics**
- Test coverage percentage (target: >90%)
- Test-to-code ratio (aim for 1:1 or higher)
- Number of assertions per test
- Test execution time (keep tests fast)

**TDD Workflow Health**
- Percentage of code written test-first
- Average time between test writing and implementation
- Test failure rate during development
- Bug detection rate before production

#### Common TDD Pitfalls to Avoid

**Don't Test Everything**
- Avoid testing language features and framework code
- Focus on business logic and domain rules
- Don't test private methods directly

**Keep Tests Independent**
- Tests should run in any order
- Avoid shared state between tests
- Use fixtures for consistent test setup

**Maintain Test Quality**
- Tests should be readable and maintainable
- Avoid brittle tests that break with implementation changes
- Regularly review and improve test code

### Release Process
1. Update version number in `pyproject.toml`
2. Update changelog with all changes
3. Run full test suite and ensure 100% coverage
4. Build documentation and examples
5. Build package using Poetry
6. Test package in isolated environment
7. Publish to PyPI
8. Create git tag for release

### TDD-Enhanced Development Workflow

**For New Features:**
1. Create feature branch from main
2. **TDD Phase**: Write failing tests for the new functionality
   - Define acceptance criteria through tests
   - Include unit, integration, and edge case tests
   - Ensure tests fail for expected reasons
3. Implement minimal code to make tests pass
4. Refactor code while maintaining test coverage
5. Ensure all tests pass and coverage targets are met (>90%)
6. Run code quality checks (Black, MyPy, Flake8)
7. Submit pull request with test results and coverage reports
8. Code review focusing on both production and test code
9. Merge and tag release if necessary

**For Bug Fixes:**
1. Create bugfix branch from main
2. **TDD Phase**: Write test that reproduces the bug
3. Verify test fails before fixing
4. Fix bug with minimal changes
5. Ensure test passes and no regressions introduced
6. Run full test suite and quality checks
7. Submit pull request with bug reproduction test

**Daily TDD Routine:**
- Start each development session with `pytest` to ensure clean state
- Write tests before implementation whenever possible
- Run tests frequently during development (every 5-10 minutes)
- End each session with full test suite and coverage check
- Commit frequently with descriptive messages mentioning test status

**Quality Gates:**
- No new code without corresponding tests
- Minimum 90% test coverage required for merge
- All tests must pass in CI/CD pipeline
- Code review includes test quality assessment
- Performance tests must pass for critical paths

### Quality Guidelines
- **Consistency**: Maintain unified API naming and style
- **Simplicity**: Avoid over-engineering, pursue elegant solutions
- **Testability**: Design interfaces that are easy to test
- **Backward Compatibility**: Consider compatibility for version upgrades
- **Performance**: Monitor and optimize for high-throughput scenarios
- **Security**: Validate all external inputs and handle errors gracefully