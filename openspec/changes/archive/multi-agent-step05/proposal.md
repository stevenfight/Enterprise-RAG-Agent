# 变更提案: 多 Agent 升级 - 阶段二 Orchestrator + 委托

> 编码: UTF-8
> 状态: 方案编制中
> 日期: 2026-08-06
> 对应步骤: 2.1（AgentRegistry）、2.2（SharedMemory）、2.3（DelegateTool）、2.4（OrchestratorAgent）

---

## 1. 变更背景

阶段零（0.1/0.2/0.3）已完成基础设施：ReActAgent 改造、Prompt 配置化、三层路由。阶段一（1.1）已创建 DataAgent（第一个 Worker Agent）。阶段二的 4 个步骤紧密关联，合并为一个变更实施：

- 2.1 AgentRegistry：注册 Worker 能力描述
- 2.2 SharedMemory：跨 Worker 共享中间结果
- 2.3 DelegateTool：Orchestrator 委托 Worker 的工具
- 2.4 OrchestratorAgent：主控 Agent + api_service 集成

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| Agent 注册表 | AgentRegistry 可注册/查找 Worker，生成 LLM 可读的描述文本 |
| 共享记忆 | SharedMemory 写入隔离、读取合并、来源聚合、Token 聚合 |
| 委托工具 | DelegateTool 可委托 DataAgent 执行检索任务 |
| 主控 Agent | OrchestratorAgent 继承 ReActAgent，通过 delegate 工具调度 Worker |
| API 集成 | POST 和 SSE 端点 multi_agent 分支真正执行多 Agent 链路 |
| 向后兼容 | 不改动现有工具、planner、DataAgent；现有 126 项测试全部通过 |

---

## 3. 变更范围

### 3.1 新增模块

| 模块 | 文件名 | 行数 | 职责 |
|------|--------|:--:|------|
| Agent 注册表 | `src/agent_registry.py` | ~70 | 管理 Worker Agent 能力描述 |
| 共享记忆 | `src/shared_memory.py` | ~130 | 跨 Worker 共享中间结果 |
| 委托工具 | `src/tools/delegate_tool.py` | ~170 | 委托 Worker 执行子任务 |
| 主控 Agent | `src/orchestrator_agent.py` | ~110 | 分析→委托→汇总 |

### 3.2 修改模块

| 模块 | 行数 | 说明 |
|------|:--:|------|
| `src/api_service.py` | ~40 | 初始化多 Agent 组件；POST/SSE 端点 multi_agent 分支 |

---

## 4. 前置依赖

- 步骤 0.1: ReActAgent 改造（llm_provider / prompt_name / shared_context 支持）
- 步骤 0.2: Prompt 配置化（orchestrator 节定义）
- 步骤 0.3: 三层路由（multi_agent 标记）
- 步骤 1.1: DataAgent 已创建

## 5. 关联风险

| 风险等级 | 数量 | 说明 |
|:--:|:--:|------|
| 高危 | 0 | 全部高危风险已在步骤 0.1 消解 |
| 中危 | 1 | R-13: DelegateTool 依赖注入方式（已在方案中明确构造函数注入） |
| 低危 | 4 | Worker API Key 获取、SSE 事件队列、agent_descriptions 注入、Token 消耗 |

## 6. 成功标准

- 28 项新增 TDD 测试通过（其中 2 项需 API Key 时 skip）
- 现有 126 项测试全部通过（无回归）
- "三大运营商2024年营收对比" 查询走 multi_agent 链路
- SSE 流正确推送 `orchestrator_start` 和 `worker_step` 事件
