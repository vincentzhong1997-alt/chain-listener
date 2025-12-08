# Multi-Chain Event Listener SDK - Technical Solution

## System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "Chain Listener SDK"
        Coordinator[Event Listener]

        subgraph "Registry Layer"
            AdapterRegistry[Adapter Registry]
            CallbackRegistry[Callback Registry]
        end

        subgraph "Chain Adapters (Unified: Connection + Decoding)"
            ETH[Ethereum Adapter]
            BSC[BSC Adapter]
            SOL[Solana Adapter]
            TRON[Tron Adapter]
        end

        subgraph "Core Components"
            Processor[Event Processor]
            StateManager[State Manager]
        end

        subgraph "Storage Layer"
            RedisStore[(Redis)]
        end
    end

    subgraph "External Systems"
        ETH_RPC[Ethereum RPC]
        BSC_RPC[BSC RPC]
        SOL_RPC[Solana RPC]
        TRON_RPC[Tron API]
        UserCallbacks[User Callback Functions]
    end

    Coordinator --> AdapterRegistry
    Coordinator --> CallbackRegistry

    AdapterRegistry --> ETH
    AdapterRegistry --> BSC
    AdapterRegistry --> SOL
    AdapterRegistry --> TRON

    ETH --> ETH_RPC
    BSC --> BSC_RPC
    SOL --> SOL_RPC
    TRON --> TRON_RPC

    Coordinator --> Processor
    Processor --> AdapterRegistry
    Processor --> StateManager
    Processor --> CallbackRegistry

    StateManager --> RedisStore

    CallbackRegistry --> UserCallbacks

    %% Note: Each Chain Adapter includes both connection management and event decoding capabilities
    classDef ETH fill:#e1f5fe
    classDef BSC fill:#e8f5e8
    classDef SOL fill:#fff3e0
    classDef TRON fill:#fce4ec
```

### Core Component Design

#### 1. ChainListener (事件监听器 - 主API接口)
**核心职责**:
- 提供统一简洁的用户API接口
- 内部组合EventListener、EventProcessor、StateManager等组件
- 管理整个监听系统的生命周期和配置

**主要接口**:
```python
class ChainListener:
    def __init__(self, config: ChainListenerConfig)
    @classmethod
    def from_config_file(cls, config_path: str) -> 'ChainListener'

    # 生命周期管理
    async def start_listening(self) -> None
    async def stop_listening(self) -> None

    # 事件回调注册 - 用户友好API
    def on_event(self, chain_name: str, contract_address: str, event_name: str, callback: Callable) -> None

    # 系统管理
    async def get_system_status(self) -> Dict[str, Any]

    # 链管理
    def _add_chain_support(self, chain_name: str, config: ChainConfig) -> None
    async def get_latest_block(self, chain_name: str) -> int
```

**设计特点**:
- **门面模式**: 对外提供简洁统一的监听器API
- **组合模式**: 内部整合EventListener、EventProcessor、StateManager等专业组件
- **用户友好**: API名称和参数设计符合用户直觉
- **配置驱动**: 支持文件配置和代码配置两种方式

#### 2. EventListener (区块链事件监听器)
**核心职责**:
- 持续监听多条区块链的新区块和事件
- 管理与区块链节点的连接和轮询策略
- 检测网络异常和重连机制

**主要接口**:
```python
class EventListener:
    async def start_listening(self) -> None
    async def stop_listening(self) -> None
    async def add_chain(self, chain_type: ChainType, adapter: BaseAdapter) -> None
    async def remove_chain(self, chain_type: ChainType) -> None
    async def get_latest_block(self, chain_type: ChainType) -> int
    def is_listening(self, chain_type: ChainType) -> bool
```

**设计特点**:
- 专注于数据获取，不处理业务逻辑
- 支持多链并发监听
- 自动故障检测和恢复机制
- 智能轮询策略避免RPC超限

#### 3. AdapterRegistry (链适配器组册表)
**核心职责**:
- 管理不同区块链适配器的注册和获取
- 支持链类型映射和适配器复用
- 提供适配器生命周期管理

**主要接口**:
```python
class AdapterRegistry:
    def register_adapter(self, chain_type: ChainType, adapter_factory: Callable) -> None
    def get_adapter(self, chain_type: ChainType) -> BaseAdapter
    def list_supported_chains(self) -> List[ChainType]
    def remove_adapter(self, chain_type: ChainType) -> None
```

**设计特点**:
- 单例模式确保全局唯一性
- 延迟初始化优化启动性能
- 线程安全的注册和查找操作

#### 5. EventProcessor (事件处理器)
**核心职责**:
- 协调事件解码、回调执行和状态管理
- 处理区块链重组检测和恢复
- 管理事件处理的错误处理和重试机制

**主要接口**:
```python
class EventProcessor:
    async def process_events(self, raw_events: List[RawEvent]) -> List[ProcessResult]
    async def _detect_reorg(self, chain_type: ChainType) -> Optional[ReorgInfo]
```

**设计特点**:
- 流水线处理模式提高吞吐量
- 异步并发处理支持高TPS
- 可配置的重试和降级策略

#### 5. ChainAdapter (区块链适配器)
**核心职责**:
- 负责与特定区块链的连接和数据获取
- 实现区块链特定的事件解码逻辑
- 提供统一的适配器接口供注册表管理

**主要接口**:
```python
class BaseAdapter:
    # 连接管理
    async def connect(self) -> None
    async def disconnect(self) -> None
    async def is_connected(self) -> bool

    # 数据获取
    async def get_latest_block_number(self) -> int
    async def get_events(self, from_block: int, to_block: int,
                        addresses: List[str], signatures: List[str]) -> List[RawEvent]
    async def validate_block_hash(self, block_number: int, expected_hash: str) -> bool

    # 事件解码
    async def decode_event(self, raw_event: RawEvent) -> DecodedEvent
    async def load_contract_definitions(self, contracts: Dict[str, Any]) -> None

    # 链特定配置
    @property
    def chain_type(self) -> ChainType
    @property
    def config(self) -> ChainConfig
```

* **RawEvent** - 原始事件数据结构
```python
@dataclass
class RawEvent:
    chain_type: ChainType
    block_number: int
    block_hash: str
    transaction_hash: str
    log_index: int
    contract_address: str
    raw_data: Dict[str, Any]         # 链特定的原始数据
    timestamp: int
```

* **DecodedEvent** - 解码事件数据结构
```python
@dataclass
class DecodedEvent:
    chain_type: ChainType
    contract_address: str
    event_name: str
    parameters: Dict[str, Any]    # 解码后的事件参数
    block_number: int
    transaction_hash: str
    log_index: int
    timestamp: int
```

**具体实现**:
- **EthereumAdapter**: Web3.py集成，支持EVM兼容链
- **BSCAdapter**: 基于EthereumAdapter扩展，优化BSC特性
- **SolanaAdapter**: AsyncClient集成，Anchor IDL解码
- **TronAdapter**: HTTP客户端，TRC-20/TRC-721事件处理

**设计特点**:
- 统一接口抽象，支持多态操作
- 链类型映射机制，减少重复实现
- 内置连接池管理和故障恢复

#### 6. CallbackRegistry (回调注册表)
**核心职责**:
- 管理用户事件回调函数的注册和查找
- 基于"合约地址:事件名"的键值映射机制
- 支持回调函数的动态添加、移除和查询

**主要接口**:
```python
class CallbackRegistry:
    def register_callback(self, contract_address: str, event_name: str, callback: Callable) -> None
    def get_callback(self, contract_address: str, event_name: str) -> Optional[Callable]
    def remove_callback(self, contract_address: str, event_name: str) -> None
    def list_callbacks(self) -> Dict[str, Callable]
    def register_reorg_handler(self, handler: Callable) -> None
    def get_reorg_handler(self) -> Optional[Callable]
```

**设计特点**:
- 单例模式确保全局唯一性
- 高效的哈希表查找机制，O(1)时间复杂度
- 支持回调函数的版本管理和热更新
- 异常回调的隔离处理，不影响其他事件
- 线程安全的并发注册和调用
- 支持回调函数的优先级和分组

#### 7. StateManager (状态管理器)
**核心职责**:
- 统一管理区块处理状态和进度跟踪
- 提供多种存储后端的抽象接口
- 处理重组数据的查询和回滚操作

**主要接口**:
```python
class StateManager:
    async def save_block_state(self, state: BlockState) -> None
    async def get_latest_block(self, chain_type: ChainType) -> Optional[int]
    async def get_rollback_data(self, chain_type: ChainType, from_block: int) -> List[BlockState]
```

**设计特点**:
- 策略模式支持多种存储后端
- 批量操作优化I/O性能
- 原子性操作保证数据一致性

---

#### 组件协作机制

##### 1. **事件数据流协作**
- **ChainListener** → **EventListener**: 从EventListener拿到raw event
- **EventListener** → **AdapterRegister**: 从AdapterRegister拿到所有链适配器，并开始事件监听
- **ChainListener** → **EventProcessor**: 原始事件传递和处理
- **EventProcessor** → **StateManager**: 处理状态同步和存储
- **EventProcessor** → **ReorgDetector**: 重组检测
- **EventProcessor** → **CallbackRegistry**: 用户事件回调函数和重组回调函数查找和执行

##### 2. **生命周期协调**
- **启动顺序**: StateManager → AdapterRegistry → EventProcessor → EventListener
- **停止顺序**: EventListener → EventProcessor → AdapterRegistry → StateManager
- **优雅关闭**: 等待所有处理完成后再停止组件

##### 3. **配置级联管理**
- **用户配置** → ChainListener → 自动配置内部组件
- **不支持热重载支持**: 初始化时确定日志，不支持后续变更配置

##### 4. **错误处理协作**
- **EventListener错误** (连接失败、超限) → ChainListener决策重试/降级
- **EventProcessor错误** (解码失败、回调异常) → 记录日志并继续处理其他事件
- **StateManager错误** (存储失败) → 重试3次，期间打印错误日志。
- **错误传播机制**: 组件间错误传递和统一处理

##### 5. **性能和资源协调**
- **EventProcessor负载** → EventListener调整轮询频率
- **StateManager存储压力** → EventProcessor调整批处理大小
- **回调执行延迟** → EventProcessor动态调整并发数
- **内存使用监控** → 各组件自动调整缓存大小

##### 6. **状态同步机制**
- **实时状态同步**: 组件间定期交换健康状态和性能指标
- **配置一致性**: 确保所有组件使用相同的链配置和回调注册
- **进度协调**: EventListener的监听进度与EventProcessor的处理进度保持同步

##### 7. 时序图
```mermaid
sequenceDiagram
    participant User as User Callback
    participant Coordinator as ChainListener
    participant Registry as AdapterRegistry
    participant Adapter as ChainAdapter
    participant Processor as EventProcessor
    participant StateMgr as StateManager

    User->>Coordinator: start_listening()
    Coordinator->>Registry: get_adapter(chain_type)
    Registry->>Adapter: create_adapter(config)
    Coordinator->>StateMgr: get_last_processed_block()
    Coordinator->>Adapter: get_events(from_block, to_block)

    loop Event Processing
        Adapter->>Processor: raw_event
        Processor->>Registry: get_adapter(chain_type)
        Registry->>Adapter: return adapter_instance
        Processor->>Adapter: decode_event(raw_event)

        alt Decode Success
            Adapter->>Processor: decoded_event
            Processor->>Registry: get_callback(contract, event)
            Registry->>User: callback(decoded_event)
            User->>Processor: callback_result
            Processor->>StateMgr: update_processed_block()
        else Decode Failure
            Adapter->>Processor: DecodingError
            Processor->>Coordinator: halt_with_error()
        end
    end

    alt Reorg Detected
        Processor->>StateMgr: get_rollback_data()
        StateMgr->>Processor: rollback_states
        Processor->>Coordinator: reorg_detected(rollback_states)
        Coordinator->>User: reorg_handler(rollback_states)
        User->>Coordinator: handle_reorg()
    end
```

### Usage Example

```python
# 加载配置
config = ChainListenerConfig.from_file("config.yaml")

# 创建监听器
listener = ChainListener(config)

# 注册事件回调
def handle_transfer(event):
    print(f"Transfer detected: {event.parameters}")

listener.on_event(
    chain_name="ethereum",
    contract_address="0xA0b86a33E6441E6C8D19A5E5E5E5E5E5E5E5E5E5",
    event_name="Transfer",
    callback=handle_transfer
)

listener.set_reorg_handler(handle_reorg)

# 启动监听
await listener.start()
```
---

## Adapter Design

采用注册表模式统一管理不同区块链适配器，支持动态扩展和链类型映射。

### 链类型适配策略

**兼容链映射机制**:
- **EVM兼容链** (Ethereum, BSC, Polygon): 共享以太坊适配器实例
- **独立链** (Solana, Tron): 使用专用适配器

### 适配器实现策略

#### EVM适配器（以太坊及兼容链）

**连接管理**:
- Web3.py HTTP客户端 + aiohttp连接池
- 自动重连和健康检查

**事件获取**:
- 使用eth_getLogs批量获取
- 按合约地址和事件签名过滤
- 智能分块处理避免RPC超时

**事件解码**:
- 预加载合约ABI到内存缓存
- 基于事件签名匹配解码器
- 异常事件跳过并记录日志

#### Solana适配器

**连接管理**:
- AsyncClient连接到Solana RPC
- 连接断开自动重连机制

**事件获取**:
- logsSubscribe订阅程序日志
- 按Program ID过滤事件
- 支持历史区块事件查询

**事件解码**:
- Anchor IDL加载和解析
- 基于事件名称匹配解码逻辑
- 自定义事件类型处理

#### Tron适配器

**连接管理**:
- HTTP客户端连接TronGrid API
- API调用频率限制控制

**事件获取**:
- gettransactioninfobyid获取交易详情
- 按合约地址过滤日志事件
- 分页处理大量历史数据

**事件解码**:
- TRC-20/TRC-721标准事件解码
- 自定义ABI事件处理
- Tron特定数据类型转换

### 故障转移和轮询机制

#### 智能轮询策略
- **自适应间隔**: 根据RPC响应时间动态调整轮询频率
- **突发处理**: 检测到新区块时立即触发事件获取
- **速率限制**: 遵守各链的API调用限制，避免429错误

#### RPC端点故障转移
- **自动切换**: 主节点失败时自动切换到备用节点
- **端点权重**: 支持配置不同节点的优先级

## EventProcessor Design

**处理流程**:
1. **重组检测**: 对比当前区块哈希与存储的历史哈希
2. **事件解码**: 调用链适配器将原始事件转换为结构化数据
3. **回调路由**: 查找并执行匹配的用户回调函数
4. **状态更新**: 记录成功处理的区块状态

**错误处理策略**:
- **重组处理**: 触发用户定义的重组处理器或抛出异常
- **解码失败**: 跳过无法解码的事件，记录错误日志继续处理

---

## State Management & Persistence

状态管理采用分层设计，提供统一的存储抽象接口和多种存储后端实现。

### 核心数据结构

**BlockState** - 区块状态数据
```python
@dataclass
class BlockState:
    chain_type: ChainType
    block_number: int
    block_hash: str          # 用于重组检测
    processed_at: int        # 处理时间戳
```

### 存储抽象层

**StorageBackend** - 纯技术存储抽象（5个核心接口）
```python
class StorageBackend:
    # 基础存储操作
    async def save(self, key: str, value: Any) -> None
    async def get(self, key: str) -> Optional[Any]
    async def delete(self, key: str) -> None

    # 批量操作（性能优化）
    async def batch_save(self, data: Dict[str, Any]) -> None

    # 查询操作
    async def scan(self, prefix: str) -> Dict[str, Any]
```

**StateManager** - 业务逻辑层（使用StorageBackend）
- 封装区块链状态管理的业务逻辑
- 实现重组检测算法和回滚策略
- 提供业务语义的API给其他组件

**核心业务功能**:
- 区块状态管理：保存/获取区块处理状态
- 重组检测：对比当前区块哈希与历史哈希
- 回滚处理：获取重组数据并执行回滚操作
- 进度跟踪：计算处理延迟和同步状态

### StorageBackend 具体实现

#### Redis Storage (缓存存储）
**适用场景**: 高性能需求、跨进程状态共享
**特点**:
- 内存存储，毫秒级读写性能
- 原子性操作和事务支持
- 支持批量操作优化I/O性能

**实现策略**:
- 接收用户传入的异步Redis客户端实例
- 使用Redis Hash存储键值对数据，提高组织效率
- 使用Pipeline批量操作提高性能
- 利用用户客户端的内置连接池管理

**接口设计**:
```python
class RedisStorage(StorageBackend):
    def __init__(self, redis_client: aioredis.Redis, key_prefix: str = "chain_listener:"):

    async def save(self, key: str, value: Any) -> None:

    async def get(self, key: str) -> Optional[Any]:

    async def delete(self, key: str) -> None:

    async def batch_save(self, data: Dict[str, Any]) -> None:
        """使用Pipeline批量保存数据"""

    async def scan(self, prefix: str) -> Dict[str, Any]:
```

**使用示例**:
```python
import aioredis
from chain_listener.storage import RedisStorage

# 用户创建和管理Redis客户端
redis_client = aioredis.Redis.from_url("redis://localhost:6379")

# 传入客户端给存储后端
storage = RedisStorage(redis_client, key_prefix="my_app:")

# ChainListener使用存储
config = ChainListenerConfig(
    storage=StorageConfig(
        backend="redis",
        redis_client=redis_client,  # 传入客户端实例
        key_prefix="chain_listener:"
    )
)
```

---

## Configuration Management

### 单文件配置设计

采用YAML单配置文件设计，集成所有必要信息，包括链配置、存储设置和合约定义，最大化易用性和部署简便性。

#### 配置结构设计

**Global Settings** - 全局配置
- `max_concurrent_processing`: 最大并发处理数量
- `event_batch_size`: 事件批处理大小
- `callback_error_handling`: 错误处理策略 (ignore|retry|stop)
- `log_level`: 日志级别 (DEBUG|INFO|WARN|ERROR)

**Storage Configuration** - 存储配置
- `key_prefix`: key前缀

**Chain Configuration** - 链配置
```yaml
chains:
  ethereum:
    enabled: true
    chain_type: "ethereum"
    confirmation_blocks: 12
    polling_interval: 1000  # 毫秒
    rpc_urls:
      - url: "http://localhost:8545"
        priority: 1
      - url: "https://mainnet.infura.io/v3/xxx"
        priority: 2
    contracts:
      - name: "USDT"
        address: "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        abi: "..."  # EVM合约ABI JSON字符串
        events: ["Transfer", "Approval"]
      - name: "CustomERC20"
        address: "0x..."
        abi: "..."
        events: ["Transfer"]

  bsc:
    enabled: true
    chain_type: "evm"  # 使用Ethereum适配器
    chain_id: 56  # BSC主网
    confirmation_blocks: 10
    polling_interval: 3000
    rpc_urls:
      - url: "https://bsc-dataseed1.binance.org"
        priority: 1

  solana:
    enabled: true
    chain_type: "solana"
    confirmation_blocks: 32
    polling_interval: 800
    rpc_urls:
      - url: "https://api.mainnet-beta.solana.com"
        priority: 1
    contracts:
      - name: "TokenProgram"
        program_id: "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        idl: "..."  # Solana合约IDL JSON字符串
        events: ["Transfer", "Mint", "Burn"]

  tron:
    enabled: true
    chain_type: "tron"
    confirmation_blocks: 19
    polling_interval: 2000
    rpc_urls:
      - url: "https://api.trongrid.io"
        priority: 1
    contracts:
      - name: "TRC20USDT"
        address: "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
        abi: "..."  # TRC-20 ABI JSON字符串
        events: ["Transfer"]
```

**Reorg Configuration** - 重组处理配置
- `max_rollback_depth`: 最大回滚深度 (默认: 1000)
- `auto_rollback_enabled`: 是否自动回滚 (默认: true)
- `reorg_detection_interval`: 重组检测间隔 (默认: 30000ms)

#### 配置模型设计

使用Pydantic进行类型安全的配置管理:

```python
class ChainListenerConfig(BaseModel):
    """主配置模型，支持类型验证和默认值"""
    version: str = "1.0"
    global: GlobalConfig
    storage: StorageConfig
    chains: Dict[str, ChainConfig]

    @classmethod
    def from_file(cls, file_path: str) -> 'ChainListenerConfig':
        """从YAML文件加载配置"""

    def get_enabled_chains(self) -> Dict[str, ChainConfig]:
        """获取启用的链配置"""

    def get_contracts_for_chain(self, chain_name: str) -> Dict[str, ContractConfig]:
        """获取指定链的合约配置"""
```

#### 配置验证规则
- **地址格式验证**: EVM地址、Solana Program ID、Tron地址
- **ABI/IDL JSON格式验证**: 确保数据格式正确
- **数值范围验证**: 轮询间隔、确认区块数等
- **必需字段验证**: 确保配置完整性

#### 配置加载机制

* **文件格式**: YAML格式，易于阅读和版本控制
* **预加载**: ChainListener初始化阶段加载配置
* **配置验证**: 加载时自动验证配置完整性和正确性

---

## Error Handling & Reorg Protection

### Enhanced Error Handling Strategy

```python
class ChainListenerError(Exception):
    """基础异常类"""
    pass

class EventProcessingError(ChainListenerError):
    """事件处理异常"""
    pass

class EventDecodingError(ChainListenerError):
    """事件解码失败"""
    pass

class ReorgError(ChainListenerError):
    """链重组异常"""
    pass

class ConnectionError(ChainListenerError):
    """连接异常"""
    pass

class ConfigError(ChainListenerError):
    """配置异常"""
    pass

class UnsupportedChainError(ChainListenerError):
    """不支持的链异常"""
    pass

class StorageError(ChainListenerError):
    """存储异常"""
    pass

class ErrorHandler:
    """错误处理器"""

    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def handle_connection_error(self, error: Exception, attempt: int) -> bool:
        """处理连接错误，返回是否应该重试"""
        if attempt >= self.max_retries:
            return False

        # 指数退避
        delay = self.backoff_factor ** attempt
        await asyncio.sleep(delay)
        return True

    async def handle_rate_limit_error(self, headers: Dict[str, str]) -> float:
        """处理速率限制，返回需要等待的时间"""
        retry_after = headers.get('retry-after')
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

        # 默认退避策略
        return 5.0

    def classify_error(self, error: Exception) -> str:
        """错误分类"""
        if isinstance(error, SecurityError):
            return "security"
        elif isinstance(error, ConnectionError):
            return "connection"
        elif isinstance(error, DecodingError):
            return "decoding"
        elif isinstance(error, ReorgError):
            return "reorg"
        else:
            return "unknown"
```

### Reorg Detection and Handling

```python
class ReorgDetector:
    """重组检测器"""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.confirmed_blocks: Dict[ChainType, int] = {}

    async def verify_block(
        self, adapter: BaseAdapter, block_number: int, block_hash: str
    ) -> bool:
        """验证区块哈希"""
        return await adapter.validate_block_hash(block_number, block_hash)

    async def detect_reorg_chain(
        self, chain_type: ChainType, adapter: BaseAdapter
    ) -> Optional[int]:
        """检测重组点，返回需要回滚到的区块高度"""
        latest_block = await adapter.get_latest_block_number()
        confirmation_blocks = adapter.config.confirmation_blocks

        # 从最新区块开始检查
        for i in range(latest_block, max(0, latest_block - confirmation_blocks * 2), -1):
            stored_hash = await self.state_manager.get_block_hash(chain_type, i)
            if stored_hash:
                is_valid = await adapter.validate_block_hash(i, stored_hash)
                if not is_valid:
                    return i

        return None
```

---

## Implementation Plan

### 🚀 敏捷里程碑规划

#### **Milestone 1: MVP Demo (Week 2)**
**目标**: 能监听单个以太坊合约的基础事件
- **用户价值**: 验证技术可行性，获得早期用户反馈，确立核心架构方向

#### **Milestone 2: Single Chain Production (Week 4)**
**目标**: 生产级的单链事件监听（以太坊）
- **用户价值**: 可在以太坊主网部署，支持真实业务场景，稳定可靠的事件处理

#### **Milestone 3: Multi-Chain Alpha (Week 6)**
**目标**: 支持EVM兼容链的多链监听
- **用户价值**: 一套代码支持多条链，降低多链部署成本，数据一致性保证

#### **Milestone 4: Feature Complete Beta (Week 8)**
**目标**: 支持全部4条链的完整功能
- **用户价值**: 全链覆盖的监听解决方案，满足复杂业务需求，企业级稳定性

#### **Milestone 5: Production Ready (Week 10)**
**目标**: 生产就绪的完整SDK
- **用户价值**: 可直接用于生产环境，运维友好的工具链，安全可靠保障

---

### 📋 Sprint 实施计划

此计划涵盖从基础架构搭建到生产级多链发布的完整周期（Sprint 1-10）。

---

#### 🚀 Phase 1: Foundation & MVP Demo (Week 1-2)

**Sprint 1 (Week 1): 核心基础**

* **核心任务:**
    1.  **项目架构搭建**
        * 依赖管理和构建系统
        * 基础目录结构
        * CI/CD 管道
    2.  **核心模型定义**
        * RawEvent, DecodedEvent
        * ChainType 枚举
        * 基础异常类
    3.  **最小以太坊适配器**
        * Web3.py 基础连接
        * 简单事件获取
        * 基础事件解码

> **🏁 里程碑检查:**
> * ✅ 能连接以太坊节点
> * ✅ 能获取简单 Transfer 事件

**Sprint 2 (Week 2): MVP Demo**

* **核心任务:**
    1.  **回调注册表基础版**
        * 简单的键值映射
        * 基础回调调用
    2.  **ChainListener 基础版**
        * 简单的事件循环
        * 基础错误处理
    3.  **MVP 演示程序**
        * 监听 USDT Transfer 事件
        * 简单的控制台输出

> **🏁 里程碑检查:**
> * ✅ 可工作的以太坊事件监听演示
> * ✅ 里程碑 1 交付完成

---

#### 📦 Phase 2: Single Chain Production (Week 3-4)

**Sprint 3 (Week 3): 存储和配置**

* **核心任务:**
    1.  **StorageBackend 抽象层**
        * 5 个核心接口定义
        * Redis 基础实现
    2.  **StateManager 业务层**
        * 区块状态管理
        * 基础重组检测
    3.  **配置管理系统**
        * Pydantic 配置模型
        * YAML 文件加载

> **🏁 里程碑检查:**
> * ✅ Redis 状态存储工作
> * ✅ 配置文件可加载

**Sprint 4 (Week 4): 生产级单链**

* **核心任务:**
    1.  **完整以太坊适配器**
        * 连接池管理
        * 完整错误处理
        * 性能优化
    2.  **完整回调注册表**
        * 异常隔离
        * 并发安全
    3.  **基础监控**
        * 健康检查端点
        * 基础日志记录

> **🏁 里程碑检查:**
> * ✅ 可在以太坊主网部署
> * ✅ 里程碑 2 交付完成

---

#### 🔗 Phase 3: Multi-Chain Alpha (Week 5-6)

**Sprint 5 (Week 5): 多链适配器**

* **核心任务:**
    1.  **BaseAdapter 抽象化**
        * 统一接口定义
        * 链类型映射
    2.  **BSC 适配器**
        * 基于 Ethereum 扩展
        * BSC 特定优化
    3.  **适配器注册表**
        * 动态注册机制
        * 多链管理

> **🏁 里程碑检查:**
> * ✅ BSC 事件监听工作
> * ✅ 适配器框架可扩展

**Sprint 6 (Week 6): 多链协调**

* **核心任务:**
    1.  **多链配置管理**
        * 链特定配置
        * 批量配置加载
    2.  **完整重组处理**
        * 自动检测算法
        * 数据回滚机制
    3.  **性能监控**
        * 多链指标面板
        * 处理延迟统计

> **🏁 里程碑检查:**
> * ✅ 多链同时监听工作
> * ✅ 里程碑 3 交付完成

---

#### ⚡ Phase 4: Feature Complete Beta (Week 7-8)

**Sprint 7 (Week 7): 异构链支持**

* **核心任务:**
    1.  **Solana 适配器**
        * AsyncClient 集成
        * Anchor IDL 解码
        * Solana 特定优化
    2.  **Tron 适配器**
        * TronGrid API 集成
        * TRC-20/TRC-721 处理
        * Tron 特定错误处理

> **🏁 里程碑检查:**
> * ✅ Solana 事件监听工作
> * ✅ Tron 事件监听工作

**Sprint 8 (Week 8): 完整功能**

* **核心任务:**
    1.  **完整错误处理**
        * 分类错误处理
        * 重试和降级策略
    2.  **高级配置**
        * 热重载支持
        * 性能调优参数
    3.  **压力测试**
        * 100+ TPS 验证
        * 性能基准报告

> **🏁 里程碑检查:**
> * ✅ 4 条链全部支持
> * ✅ 里程碑 4 交付完成

---

#### 🛡️ Phase 5: Production Ready (Week 9-10)

**Sprint 9 (Week 9): 运维和文档**

* **核心任务:**
    1.  **完整文档**
        * API 文档生成
        * 使用示例
        * 最佳实践指南
    2.  **部署工具**
        * Docker 镜像
        * 配置模板
        * 部署脚本
    3.  **监控集成**
        * Prometheus 指标
        * Grafana 仪表板
        * 告警规则

> **🏁 里程碑检查:**
> * ✅ 部署文档完整
> * ✅ 监控系统工作

**Sprint 10 (Week 10): 安全和发布**

* **核心任务:**
    1.  **安全加固**
        * 依赖漏洞扫描
        * 代码安全审计
        * 安全配置检查
    2.  **最终集成测试**
        * 端到端场景测试
        * 兼容性测试
        * 性能回归测试
    3.  **发布准备**
        * 版本标签
        * 发布说明
        * 社区支持

> **🏁 里程碑检查:**
> * ✅ 安全审计通过
> * ✅ 里程碑 5 交付完成

### Testing Strategy

#### Unit Tests (每阶段必须完成)
```bash
# 单元测试覆盖率要求 >90%
pytest tests/unit/ -v --cov=chain_listener --cov-fail-under=90
```

#### Integration Tests
```bash
# 集成测试验证组件协作
pytest tests/integration/ -v --cov=chain_listener
```

#### Performance Tests
```bash
# 性能测试验证100+ TPS目标
pytest tests/performance/ -v
```

#### Quality Gates
- 代码覆盖率 >90%
- 所有测试通过
- Black, MyPy, Flake8 检查通过
- 性能基准测试通过

### Success Criteria

1. **功能完整性**: 支持Ethereum、BSC、Solana、Tron四个链
2. **性能指标**: 单实例处理能力 >100 TPS
3. **可靠性**: 99.9%的事件处理成功率
4. **易用性**: 简单的API设计，5行代码可启动监听
5. **安全性**: 所有输入经过验证，内存使用受控
6. **可扩展性**: 注册表模式支持动态扩展新链
7. **解耦性**: 组件间松耦合，易于测试和维护