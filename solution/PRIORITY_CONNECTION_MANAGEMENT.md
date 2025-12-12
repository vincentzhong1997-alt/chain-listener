# 优先级连接管理方案

## 问题背景

### 当前问题
1. **优先级信息丢失**: 用户配置的 RPC URL 优先级在转换过程中丢失
2. **连接管理混乱**: HTTP RPC 不需要传统意义的连接管理，但需要端点选择
3. **故障转移不当**: 缺乏基于用户配置重试次数的智能故障转移

### 用户配置格式
```yaml
chains:
  ethereum:
    rpc_urls:
      - url: "https://eth.llamarpc.com"
        priority: 1      # 优先级 1 (最高)
      - url: "https://eth-mainnet.alchemyapi.io/v2/demo"
        priority: 2      # 优先级 2
```

## 解决方案：优先级感知的连接管理

### 设计原则
1. **保留优先级**: 完整保存用户配置的优先级信息
2. **智能故障转移**: 只有连续失败次数达到用户配置的重试次数才标记端点失败
3. **自动恢复**: 失败端点在冷却时间后自动恢复可用
4. **性能优化**: 复用 Web3 实例，避免重复创建

### 核心组件设计

#### 1. PriorityConnectionPool - 优先级连接池

```python
class PriorityConnectionPool:
    """支持优先级和智能故障转移的连接池"""

    def __init__(self, endpoints_with_priority, max_retries=3):
        """
        Args:
            endpoints_with_priority: [(url, priority), ...] 按优先级排序
            max_retries: 用户配置的最大重试次数
        """
        self.endpoints = sorted(endpoints_with_priority, key=lambda x: x[1])
        self.max_retries = max_retries

        # 端点统计信息
        self.endpoint_stats = {
            url: {
                'consecutive_failures': 0,      # 连续失败次数
                'total_failures': 0,           # 总失败次数
                'last_failure_time': None,     # 最后失败时间
                'marked_failed': False,        # 是否标记为失败
                'cooling_until': None,         # 冷却截止时间
                'success_count': 0             # 成功次数（用于健康评估）
            }
            for url, _ in self.endpoints
        }

    def get_best_endpoint(self) -> str:
        """获取当前可用的最佳端点"""
        now = time.time()

        for url, priority in self.endpoints:
            stats = self.endpoint_stats[url]

            # 检查是否在冷却期
            if stats['cooling_until'] and now < stats['cooling_until']:
                continue

            # 如果已标记为失败，跳过
            if stats['marked_failed']:
                continue

            # 这个端点可用
            return url

        # 所有端点都不可用，返回最高优先级的（强制使用）
        return self.endpoints[0][0]

    def mark_success(self, url: str) -> None:
        """标记请求成功，重置失败计数"""
        stats = self.endpoint_stats[url]
        stats['consecutive_failures'] = 0
        stats['success_count'] += 1

        # 从失败状态恢复
        if stats['marked_failed']:
            stats['marked_failed'] = False
            stats['cooling_until'] = None
            logger.info(f"RPC endpoint {url} recovered from failed state")

    def mark_failure(self, url: str) -> None:
        """标记请求失败"""
        stats = self.endpoint_stats[url]
        stats['consecutive_failures'] += 1
        stats['total_failures'] += 1
        stats['last_failure_time'] = time.time()

        # 只有连续失败次数达到用户配置的重试次数才标记为失败
        if stats['consecutive_failures'] >= self.max_retries:
            stats['marked_failed'] = True
            # 指数退避冷却时间（最大5分钟）
            failure_excess = stats['consecutive_failures'] - self.max_retries
            cooling_time = min(300, 30 * (2 ** failure_excess))
            stats['cooling_until'] = time.time() + cooling_time

            logger.warning(
                f"RPC endpoint {url} marked as failed after {self.max_retries} retries. "
                f"Cooling for {cooling_time} seconds"
            )

    def get_health_status(self) -> Dict[str, Dict]:
        """获取所有端点的健康状态"""
        return {
            url: {
                'priority': priority,
                'consecutive_failures': stats['consecutive_failures'],
                'total_failures': stats['total_failures'],
                'success_count': stats['success_count'],
                'marked_failed': stats['marked_failed'],
                'cooling_until': stats['cooling_until'],
                'success_rate': stats['success_count'] / max(1, stats['success_count'] + stats['total_failures'])
            }
            for (url, priority), stats in zip(self.endpoints, self.endpoint_stats.values())
        }
```

#### 2. 改进的 EthereumAdapter

```python
class EthereumAdapter(BaseAdapter):
    """支持优先级连接管理的以太坊适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        # 提取 RPC 端点和优先级
        self.rpc_endpoints = config.get("rpc_endpoints", [])
        self.max_retries = config.get("rpc", {}).get("retries", 3)

        # 创建优先级连接池
        self._connection_pool = PriorityConnectionPool(
            self.rpc_endpoints,
            self.max_retries
        )

        # Web3 实例缓存
        self._web3_instances: Dict[str, Web3] = {}

        # 其他初始化...
        self._contract_cache: Dict[str, Any] = {}
        self._filter_cache: Dict[str, Any] = {}

    def _get_or_create_web3_instance(self, url: str) -> Web3:
        """获取或创建 Web3 实例（带缓存）"""
        if url not in self._web3_instances:
            self._web3_instances[url] = Web3(Web3.HTTPProvider(
                url,
                request_kwargs={
                    "timeout": self.rpc_config.get("timeout", 30)
                }
            ))
        return self._web3_instances[url]

    async def _execute_with_priority_routing(self, operation: Callable, *args, **kwargs) -> Any:
        """使用优先级路由执行操作"""
        last_exception = None

        # 尝试所有端点，最多 max_retries 次
        for attempt in range(self.max_retries + 1):
            # 获取当前最佳端点
            url = self._connection_pool.get_best_endpoint()

            # 获取 Web3 实例
            w3 = self._get_or_create_web3_instance(url)

            try:
                # 执行操作
                result = await self._execute_with_rate_limit(
                    lambda: operation(w3, *args, **kwargs)
                )

                # 标记成功
                self._connection_pool.mark_success(url)
                return result

            except Exception as e:
                last_exception = e
                # 标记失败
                self._connection_pool.mark_failure(url)

                # 如果不是最后一次尝试，记录日志并继续
                if attempt < self.max_retries:
                    logger.warning(
                        f"RPC endpoint {url} failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                    )
                    continue

        # 所有重试都失败了
        raise BlockchainAdapterError(
            f"All RPC endpoints failed after {self.max_retries} retries",
            last_error=last_exception
        )

    # 业务方法示例
    async def get_latest_block_number(self) -> int:
        """获取最新区块号（使用优先级路由）"""
        return await self._execute_with_priority_routing(
            lambda w3: w3.eth.block_number
        )

    async def get_logs(self, address: Optional[Union[str, List[str]]] = None,
                      topics: Optional[List[str]] = None,
                      from_block: Optional[int] = None,
                      to_block: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取日志（使用优先级路由）"""
        def get_logs_operation(w3):
            filter_params = {}
            if address:
                filter_params["address"] = address
            if topics:
                filter_params["topics"] = topics
            if from_block is not None:
                filter_params["fromBlock"] = from_block
            if to_block is not None:
                filter_params["toBlock"] = to_block

            return w3.eth.get_logs(filter_params)

        logs = await self._execute_with_priority_routing(get_logs_operation)
        return [self._convert_log_to_standard_format(log) for log in logs]
```

#### 3. 配置转换逻辑

```python
# listener.py 中的 _build_adapter_config 方法
def _build_adapter_config(self, chain_config: ChainConfig) -> Dict[str, Any]:
    """构建适配器配置（保留优先级信息）"""
    user_overrides = chain_config.adapter_config or {}

    # 提取 RPC URL 和优先级信息
    rpc_endpoints = [
        (rpc_item["url"], rpc_item.get("priority", 999))
        for rpc_item in chain_config.rpc_urls
    ]

    # 按优先级排序
    rpc_endpoints.sort(key=lambda x: x[1])

    adapter_config = {
        "name": f"{chain_config.chain_type}_adapter",
        "network": "mainnet",
        "rpc_endpoints": rpc_endpoints,  # 保留优先级信息
        "rpc": {
            "timeout": 30,
            "retries": 3  # 用户可配置的重试次数
        },
        "confirmation_blocks": chain_config.confirmation_blocks,
        "polling_interval": chain_config.polling_interval,
        "contracts": [
            {
                "name": contract.name,
                "address": contract.address,
                "abi_path": contract.abi_path,
                "events": contract.events
            }
            for contract in chain_config.contracts
        ]
    }

    # 应用用户覆盖
    for key, value in user_overrides.items():
        if key == "rpc" and isinstance(value, dict) and isinstance(adapter_config.get("rpc"), dict):
            adapter_config["rpc"].update(value)
        else:
            adapter_config[key] = value

    return adapter_config
```

## 方案优势

### 1. 精确的优先级控制
- 完全保留用户配置的优先级信息
- 每次请求都从最高优先级的可用端点开始
- 支持动态优先级调整

### 2. 智能故障转移
- 基于用户配置的重试次数，避免过于激进的故障转移
- 指数退避的冷却时间，给端点恢复时间
- 自动从失败状态恢复

### 3. 性能优化
- Web3 实例缓存，避免重复创建开销
- 连接状态统计，支持健康监控
- 按需创建，减少资源消耗

### 4. 可观测性
- 详细的端点健康状态统计
- 成功率和失败次数追踪
- 冷却时间和恢复状态监控

### 5. 用户友好
- 用户可配置重试次数
- 透明的故障转移日志
- 优雅的错误处理

## 使用示例

```python
# 配置示例
config_data = {
    "chains": {
        "ethereum": {
            "chain_type": "ethereum",
            "rpc_urls": [
                {"url": "https://eth.llamarpc.com", "priority": 1},
                {"url": "https://eth-mainnet.alchemyapi.io/v2/demo", "priority": 2},
                {"url": "https://backup-rpc.com", "priority": 3}
            ],
            "adapter_config": {
                "rpc": {
                    "retries": 5,  # 用户配置重试次数
                    "timeout": 60
                }
            }
        }
    }
}

# 使用
listener = ChainListener(ChainListenerConfig(**config_data))

# 业务调用会自动使用优先级路由
block = await listener.get_latest_block("ethereum")
```

## 实施步骤

1. **创建 PriorityConnectionPool 类**
2. **修改 EthereumAdapter 支持优先级路由**
3. **更新配置转换逻辑保留优先级信息**
4. **添加健康状态监控接口**
5. **完善错误处理和日志记录**
6. **编写单元测试和集成测试**

这个方案既解决了优先级问题，又提供了智能的故障转移机制，同时保持了良好的性能和可维护性。