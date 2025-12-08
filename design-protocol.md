# Technical Design Protocol (TDP) for Claude Code

## 🛑 Phase 0: 核心设计哲学 (Guiding Philosophy)
**决策优先级：可用性 > 简洁性 (KISS) > 可扩展性 (OCP)**
1.  **YAGNI**: 除非用户明确要求，否则不要为“未来”写代码。
2.  **KISS**: 即使符合设计模式，如果代码难以阅读，也是失败的设计。
3.  **Safety First**: 任何输入输出都必须考虑边界情况和安全性。

---

## 🔄 Phase 1: 深度分析与盘问 (Context Analysis)
**🛑 STOP! Do not generate the solution yet.** 首先分析相关的需求文档或其他上下文，然后执行以下步骤：
1.  **资产扫描**: 检查现有 `schema`, `types`, 和 `utils`，列出可复用的具体代码片段。
2.  **约束识别**: 识别技术栈限制（如：Next.js App Router vs Pages Router, SQL vs NoSQL）。
3.  **澄清问题**: 列出 3-5 个关键问题，特别是关于**边缘情况 (Edge Cases)** 和 **错误处理** 的预期。

**(输出上述内容并等待用户确认，再进入 Phase 2)**

---

## 📝 Phase 2: 技术方案草案 (Drafting the Tech Spec)
收到用户回复后，生成技术方案文档 (Tech Spec)，该文档输出为markdown文件。
* **架构可视化**: 针对复杂交互，必须提供 Mermaid Sequence/Flowchart；简单 CRUD 可跳过。
* **接口定义**: 定义函数签名/API 路径，包括 Request/Response 类型。
* **数据层**: 具体的 SQL DDL 或 Prisma/ORM Schema 变更代码。
* **错误处理**: 定义可能出现的异常及 HTTP 状态码或错误提示。
* **避免过度详细（非常重要）**: 对于复杂算法，使用 **自然语言步骤** 或 **伪代码 (Pseudo-code)** 描述，严禁直接贴代码块。

---

## ⚖️ Phase 3: 对抗性审计 (Adversarial Audit)
**切换角色：现在你是一位“挑剔的资深架构师”和“安全专家”。**
请对 Phase 2 的草案进行攻击性审查，而非简单的确认。

**审查清单 (Pass/Fail):**

1.  **[S/O/D] 架构解耦**:
    * *Check*: 核心业务逻辑是否与框架/数据库实现强耦合？（依赖倒置检查）
    * *Check*: 修改业务规则是否需要修改大量无关代码？（单一职责/开闭检查）
2.  **[Security] 安全性**:
    * *Check*: 是否存在 SQL 注入、IDOR (越权访问) 或数据泄露风险？
    * *Check*: 所有的输入参数是否都进行了验证 (Validation)？
3.  **[Performance] 性能陷阱**:
    * *Check*: 是否存在 N+1 查询？是否存在大对象加载？
4.  **[KISS] 过度设计**:
    * *Check*: 是否引入了不必要的 Factory/Strategy 模式？能否用更简单的函数组合代替？
5.  **[Completeness] 完备性**:
    * *Check*: 方案是否完整，是否有未明确的部分?

**输出要求**:
* 如果所有项 Pass，输出 "✅ Architecture Approved"。
* 如果有 Fail，输出 **“⚠️ Refactoring Required”**，并给出具体的修正后的代码片段或逻辑调整。

**修改方案**:
* 如果有 Fail，询问用户是否针对此输出的Fail对方案文档进行修改，如是请进行必要的，最小程度的技术方案修改。

---

## ✅ Phase 4: 开发执行计划 (Implementation Plan)
将方案转化为**原子化**的开发步骤（每步代码变更是可独立 commit 的）：
1.  [ ] **Step 1 (Core)**: 定义类型与数据库 Schema。
2.  [ ] **Step 2 (Logic)**: 实现核心 Service/Logic 层（包含单元测试）。
3.  [ ] **Step 3 (API/UI)**: 实现接口层或 UI 组件。
4.  [ ] **Step 4 (Verify)**: 手动验证或集成测试步骤。

## 技术方案输出要求
* **文档结构**: 文档需要有清晰，层次合理的章节结构。
* **输出内容控制**: 不要输出与技术方案无关的内容。