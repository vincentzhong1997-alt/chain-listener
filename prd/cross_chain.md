# Multi-Chain Event Listener Python SDK - PRD

| 文档版本 | 修改日期 | 修改人 | 备注 |
| :--- | :--- | :--- | :--- |
| v1.0 | 2025-11-29 | Vincent | 初始版本 |

## 1\. 项目背景与目标 (Background & Goal)

构建一个轻量级、高性能的 Python SDK，旨在为开发者提供统一的接口来监听不同区块链网络（EVM兼容链、Tron、Solana）上的合约事件。
该 SDK 作为连接链上数据与链下业务逻辑的“胶水层”，通过回调函数（Callback）机制，让开发者无需关注底层 RPC 通信、重连机制和区块解析，只需专注于业务逻辑处理。

## 2\. 核心范围 (Scope)

### 2.1 IN-SCOPE (包含)

  * **多链支持：**
      * **EVM Chains:** Ethereum, BSC, Polygon, Arbitrum 等（基于 JSON-RPC）。
      * **Tron:** 基于 TronGrid/FullNode HTTP API 或 GRPC。
      * **Solana:** 基于 RPC (`logsSubscribe` 或轮询 `getSignaturesForAddress`).
  * **核心功能：**
      * 监听指定合约地址的特定事件（Events/Logs）。
      * 自动解析合约 ABI/IDL，将原始 Hex 数据转换为可读的 Python 字典/对象。
      * **断点续传：** 记录已处理的区块高度，服务重启后不丢失数据。
      * **区块回滚处理 (Reorg Handling)：** 处理分叉和链重组情况。

### 2.2 OUT-OF-SCOPE (不包含)

  * 交易签名与发送（只读 SDK）。
  * 私钥管理与钱包功能。
  * 复杂的链下数据分析仪表盘（SDK 仅负责抛出数据）。
  * 不需要考虑分布式部署，仅支持单实例运行。

-----

## 3\. 详细功能需求 (Functional Requirements)

### 3.1 连接与配置 (Configuration)

  * **统一配置入口：** 支持通过 Python `dict` 或 YAML/JSON 文件配置 RPC 节点、重试次数、超时时间等。
  * **多节点轮询 (Failover)：** 允许为一条链配置多个 RPC Endpoint，当主节点挂掉时自动切换备用节点。

### 3.2 监听机制 (Listening Mechanism)

  * **模式支持：**
      * **轮询模式 (Polling):** 适用于 HTTP RPC，需智能控制轮询间隔，避免 429 Rate Limit。
  * **过滤规则：**
      * EVM/Tron: 支持按 `Contract Address` + `Event Signature` (Topics) 过滤。
      * Solana: 支持按 `Program ID` 过滤 Logs。

### 3.3 事件解码 (Decoding)

  * **EVM/Tron:** 输入合约 ABI (JSON)，SDK 自动将 `log.data` 和 `log.topics` 解码为 Key-Value 形式。
  * **Solana:** 支持解析常见的 Anchor IDL 产生的 Event，或返回原始 Log 供用户自定义解析。

### 3.4 状态管理 (State)

  * **Storage Interface:** 提供抽象存储接口（Driver），默认实现：
      * `MemoryDriver` (单机，不持久化)
      * `RedisDriver` (分布式储存持久化)
      * `FileDriver` (本地持久化)

### 3.5 错误处理与重试 (Robustness Logic)

  * **RPC 错误:** 遇到网络抖动、超时、5xx 错误时，执行指数退避重试 (Exponential Backoff)。
  * **链重组 (Reorg):**
      * **安全确认数 (Confirmations):** 用户可配置 `confirmation_block`（例如延迟 12 个区块再触发回调），以确保事件不可逆。
      * **回滚检测:** 检测到区块 Hash 不连续时，自动回滚游标并重新触发（或通知用户）。

-----

## 4\. 非功能需求 (Non-Functional Requirements)

  * **易用性 (Usability):**
      * **接口易用:** 提供合理的，用户友好的sdk接口。
      * **Type Hinting:** 全面支持 Python 类型注解，IDE 友好。
  * **可扩展性 (Extensibility):**
      * 未来可支持其他链的合约事件。
      * 用户事件处理可以通过接口实现解耦，未来可提供一些官方handler。
      * 能否对事件做抽象，为了是否可以衍生到除了合约事件外的交易事件，区块mint事件（这个是nice to have的）。
  * **性能 (Performance):**
      * **Async/Await:** 基于 `asyncio` 构建，支持高并发 I/O。
      * 单实例应能处理至少 100 TPS 的事件流（取决于 RPC 限制）。
