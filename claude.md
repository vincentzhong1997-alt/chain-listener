# Chain Listener SDK Development Guide

## Project Overview
This is a universal multi-chain distributed blockchain listener SDK that provides reusable multi-chain monitoring capabilities. The SDK focuses on asynchronous blockchain event listening and data processing, offering flexible solutions for different business scenarios.

## 🚨 Critical References (Must Read)
### 📋 Design Protocol
- **文件**: [`design-protocol.md`](design-protocol.md)
- **用途**: 指导软件开发方案设计阶段的思考过程与输出标准
- **触发条件**: 当需求进行技术方案设计时，**必须**参考此文档

## Development Notice
- **Network Access**: Internet access is available. All searches and documentation should be in English. For uncertain technical issues (SQLAlchemy/Web3), use exa MCP.
- **Environment**: Always work in virtual environment if venv exists. Use standardized, readable commit messages for Git.
- **Planning**: Default to deep thinking and step-by-step planning. For complex or high-risk tasks, provide overall plan first, get confirmation once, then implement without repeated confirmations.
- **Quality**: Quality over speed, understanding over blind execution.
- **Progress Updating**: when you achieve millestone progress, update the PROGRESS.md.

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
│       │   ├── solana.py        # Solana adapter
│       │   ├── tron.py          # Tron adapter
│       │   └── base.py          # Base adapter interface
│       ├── exceptions.py        # Custom exceptions
│       └── utils/               # 工具函数 (模块化)
│           ├── address.py       # 地址验证和格式化
│           ├── conversion.py    # 数据转换工具
│           ├── validation.py    # 通用验证逻辑
│           └── crypto.py        # 加密和哈希工具
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
- **Configuration**: Pydantic for type-safe configuration management

### Documentation & Comments
- Use Google-style docstrings for all public modules, classes, and functions
- Include type hints in all function signatures
- Write clear, concise comments explaining complex logic
- Maintain a comprehensive README with quick start guide
- Document all configuration options and examples
- Detailed SDK architecture documentation is available in the `solution/` directory.
- [Critical] If proposed changes conflict with the existing document description or project rules, explicitly flag this discrepancy to the user and ask if the documentation should be updated to reflect the new logic.

### Test-Driven Development (TDD) Workflow

**Important** In this project, you should use TDD as your main Workflow.

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
# Run specific test file
poetry runpytest tests/unit/test_events.py -v

# Run all tests
poetry run pytest
```

**Step 4: Implement Minimal Code**
- Write just enough production code to make tests pass
- Focus on functionality, not perfection
- Avoid gold-plating or over-engineering

**Step 5: Run Tests to Confirm Success**

**Step 6: Refactor and Improve**
- Improve code structure, readability, and performance
- Maintain test coverage during refactoring
- Run tests after each refactoring change
- not to modify test cases, especially the assert statements, unless you have solid evidence.
- When you need to modify test cases, inform the user of the reasons and seek their approval.

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

**Mock Strategy**
- Mock external dependencies (blockchain nodes, databases, APIs)
- Use dependency injection for easier testing
- Create realistic test data and scenarios
- [Critical] Don't mock the system under test

**Coverage Requirements**
- Maintain minimum 90% line coverage
- Aim for 100% coverage for critical business logic
- Use coverage reports to identify untested code paths

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

### Quality Guidelines
- **Consistency**: Maintain unified API naming and style
- **Simplicity**: Avoid over-engineering, pursue elegant solutions
- **Testability**: Design interfaces that are easy to test
- **Backward Compatibility**: Consider compatibility for version upgrades
- **Performance**: Monitor and optimize for high-throughput scenarios
- **Security**: Validate all external inputs and handle errors gracefully