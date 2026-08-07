# 变更提案: 多 Agent 升级 - 阶段五 调优（第一轮）

> 编码: UTF-8
> 状态: 已完成（代码实施 + 12/12 TDD 全部通过，206+5 回归零失败）
> 日期: 2026-08-07

---

## 1. 变更背景

阶段零 ~ 阶段四已完成多 Agent 核心链路（Orchestrator + 5 Worker + 并行调度 + Reflector + API 端点统一）。阶段四手动验证（curl POST/GET `mode=multi`）发现以下影响实际使用的问题与优化点：

1. **Orchestrator 委派任务参数格式错误（核心问题）**：手动验证中 Orchestrator 委派 DataAgent 时，LLM 输出了 `{"agent":"DataAgent","tool":"retrieve","params":{...}}` 格式而非 DelegateTool 要求的 `{"tasks":[{"agent":"DataAgent","task":"..."}]}` 格式，导致 DataAgent 收到空任务（`task=""`），回答"请提供您需要查询的财务数据内容"。根因：`ToolRegistry.get_tool_descriptions()` 对嵌套参数（`tasks.items.properties`）只展示第一层 `tasks(要委托的子任务列表)`，LLM 无法理解 tasks 数组内必须包含 `agent`/`task` 字段。
2. **并行加速比与 API 成本无观测**：多 Agent 升级方案"阶段五：观察与调优"明确要求收集并行加速比数据、评估 API 调用成本，当前 `DelegateTool.run()` 未返回并行批次统计，api_service 未记录 token 消耗。
3. **路由准确率待观测**：需要验证简单查询是否被误路由到 multi_agent。

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 修复 delegate 委派空任务 | Orchestrator 委派时能正确生成 `tasks[].task` 字段，DataAgent 收到具体查询而非空串 |
| 增强 delegate 工具描述 | `ToolRegistry.get_tool_descriptions()` 支持嵌套参数展示，LLM 能看到 `agent`/`task`/`company_name` 字段说明 |
| 并行加速比观测 | `DelegateTool.run()` 返回数据含 `parallel_batch_count`（并行批次数）与 `estimated_serial_ms`（预估串行耗时） |
| API 成本观测 | api_service 日志记录 multi_agent 执行的 `total_tokens`（来自 AgentResult） |
| 路由准确率观测 | `QueryRouter.get_stats()` 已有统计能力（阶段零实现），阶段五通过回归测试验证简单查询不误路由到 multi_agent |
| 向后兼容 | 不改变任何现有 API 响应契约与 SSE 事件结构，零回归失败 |

## 3. 变更范围

### 3.1 修改模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 工具注册表 | `src/tools/__init__.py` | `get_tool_descriptions()` 支持嵌套参数（items.properties）展示 |
| 委托工具 | `src/tools/delegate_tool.py` | `run()` 返回并行批次统计字段（parallel_batch_count / estimated_serial_ms） |
| 调度器提示词 | `config/agent_prompts.yaml` | orchestrator 节补充 delegate 调用 JSON 示例 |
| API 端点 | `src/api_service.py` | multi_agent 执行后记录 total_tokens 与 workers 数量日志 |

### 3.2 不修改模块

| 模块 | 说明 |
|------|------|
| `src/agent_core.py` | ReActAgent 核心不变 |
| `src/orchestrator_agent.py` | 逻辑不变（delegate 参数修复依赖工具描述/prompt 增强，不涉及此文件） |
| `src/router.py` | 路由逻辑不变（已有 get_stats 观测能力） |
| `src/shared_memory.py` / `src/agent_registry.py` | 阶段二已实现，不变 |
| 5 个 Worker Agent | 阶段一/三已实现，参数已合理，不变 |
| `src/reflector.py` | 反思核心逻辑不变 |
| 前端 / 部署脚本 | 不变 |

## 4. 前置依赖

- 阶段四已完成：POST/GET 端点支持 `mode` 参数，SSE 事件完整
- `ToolRegistry.get_tool_descriptions()` 当前实现（tools/__init__.py）
- `DelegateTool.run()` 当前实现（tools/delegate_tool.py）

## 5. 关键设计决策

| 决策 | 说明 |
|------|------|
| 工具描述嵌套展示 | `get_tool_descriptions()` 对 `properties` 中值为数组类型（含 `items.properties`）的参数，递归展开 `items` 字段说明，使 delegate 的 `tasks[].agent/task/company_name` 对 LLM 可见 |
| delegate 调用示例注入 | 在 `agent_prompts.yaml` orchestrator 节的调度规则中增加 delegate 的 Action Input JSON 示例（few-shot），引导 LLM 正确生成 `tasks` 数组 |
| 并行批数观测 | `DelegateTool.run()` 返回 data 增加 `parallel_batch_count`（实际并行批次）与 `estimated_serial_ms`（预估串行耗时），不改 API 响应契约（data 为自由结构） |
| 成本观测 | api_service 在 multi_agent 完成后记录 `result.total_tokens` 与 `shared_memory.agent_outputs` 数量（worker 数）到日志 |
| 最小变更 | 不新增第三方依赖；不改动现有响应模型与 SSE 事件结构 |

## 6. 关联风险

| 风险 | 等级 | 缓解 |
|------|:--:|------|
| get_tool_descriptions 改动影响其他工具描述 | 低 | 递归展示仅在参数值为数组且含 items.properties 时触发，普通工具（retrieve/calculator 等）无嵌套参数，描述格式不变 |
| delegate 参数格式仍不稳定（LLM 行为） | 中 | 双重缓解：工具描述嵌套展示 + orchestrator prompt 显式 JSON 示例；TDD 验证描述文本包含 `agent`/`task` 字段说明 |
| 并行批数统计引入额外逻辑 | 低 | 统计复用现有 `_group_by_dependency()` 的分组结果，仅追加 2 个字段，不改变执行逻辑 |
| token 日志字段不存在 | 低 | `AgentResult.total_tokens` 已在阶段零实现，直接引用 |

## 7. 验证策略

- TDD: 新增 12 项测试（工具描述 4 项 + orchestrator prompt 2 项 + delegate 统计 3 项 + api_service 日志与路由回归 3 项），先标红后转绿
- 回归: 阶段一~四全部 TDD 测试通过（194 passed + 5 skipped 基础上扩展），零回归失败
- 手动: curl POST/GET `mode=multi` 验证委派任务非空、DataAgent 正常回答
