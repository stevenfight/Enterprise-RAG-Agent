# TDD 规格: 多 Agent 升级 - 阶段五 调优（第一轮）

> 编码: UTF-8
> 日期: 2026-08-07
> 状态: 已通过（12/12 ✅，全线转绿，阶段五实施完成）

---

## 测试组 TC-80: 工具描述嵌套参数展示（4 项）

### TC-80-01: delegate 工具描述包含 agent 字段说明
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 创建 DelegateTool 实例（Mock agent_registry / shared_memory）
  2. 注册到 ToolRegistry
  3. 调用 `get_tool_descriptions()`
  4. 检查返回文本包含 "agent" 字段说明
- **预期结果**: 工具描述中 `tasks` 参数展开 `agent` 子字段
- **状态**: ✅ 通过

### TC-80-02: delegate 工具描述包含 task 字段说明
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 创建 DelegateTool 实例并注册
  2. 调用 `get_tool_descriptions()`
  3. 检查返回文本包含 "task" 字段说明
- **预期结果**: 工具描述中 `tasks` 参数展开 `task` 子字段
- **状态**: ✅ 通过

### TC-80-03: 普通工具（无嵌套参数）描述格式不变
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 创建 RetrieveTool（无嵌套 items）并注册
  2. 调用 `get_tool_descriptions()`
  3. 检查返回文本格式与改动前一致（不包含"每项含"字样）
- **预期结果**: 无嵌套参数的工具描述格式不回归
- **状态**: ✅ 通过

### TC-80-04: 嵌套参数描述包含 company_name 字段
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 创建 DelegateTool 实例并注册
  2. 调用 `get_tool_descriptions()`
  3. 检查返回文本包含 "company_name" 字段说明
- **预期结果**: `tasks` 参数展开 `company_name` 子字段
- **状态**: ✅ 通过

---

## 测试组 TC-81: orchestrator 提示词 delegate 调用示例（2 项）

### TC-81-01: orchestrator prompt 包含 delegate 单任务调用示例
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 加载 `config/agent_prompts.yaml` orchestrator 节
  2. 检查模板文本包含 "tasks" 数组格式示例（含 `"agent"` 与 `"task"` 键）
- **预期结果**: orchestrator 模板含 delegate 调用示例
- **状态**: ✅ 通过

### TC-81-02: orchestrator prompt 包含多任务并行示例
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 加载 `config/agent_prompts.yaml` orchestrator 节
  2. 检查模板文本包含多任务示例（含两个以上 task 元素或 company_name 键）
- **预期结果**: orchestrator 模板含多任务并行调用示例
- **状态**: ✅ 通过

---
## 测试组 TC-82: DelegateTool 并行批次统计（3 项）

### TC-82-01: 单任务批次 parallel_batch_count=1
- **类型**: 单元测试（Mock）
- **前置条件**: AgentRegistry 注册 DataAgent
- **Mock 对象**: Worker Agent 执行
- **测试步骤**:
  1. 构造 `tool.run(tasks=[{"agent":"DataAgent","task":"查询营收"}])`
  2. 检查 `result.data["parallel_batch_count"] == 1`
- **预期结果**: 单任务返回并行批次数 1
- **状态**: ✅ 通过

### TC-82-02: 多任务同批并行 parallel_batch_count=1
- **类型**: 单元测试（Mock）
- **前置条件**: AgentRegistry 注册 DataAgent
- **Mock 对象**: Worker Agent 执行
- **测试步骤**:
  1. 构造两个 DataAgent 任务（同批并行）
  2. 调用 `tool.run(tasks=[...])`
  3. 检查 `result.data["parallel_batch_count"] == 1`
- **预期结果**: 并行批数为 1（同批并行）
- **状态**: ✅ 通过

### TC-82-03: 检索+分析混合任务 parallel_batch_count=2
- **类型**: 单元测试（Mock）
- **前置条件**: AgentRegistry 注册 DataAgent + CompareAgent
- **Mock 对象**: Worker Agent 执行
- **测试步骤**:
  1. 构造 DataAgent 任务 + CompareAgent 任务
  2. 调用 `tool.run(tasks=[...])`
  3. 检查 `result.data["parallel_batch_count"] == 2`
- **预期结果**: 检索批与下游分析批共 2 批
- **状态**: ✅ 通过

---
## 测试组 TC-83: api_service 观测日志 + 路由回归（3 项）

### TC-83-01: multi_agent 日志包含 total_tokens 字段
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化
- **Mock 对象**: OrchestratorAgent.run 返回 total_tokens
- **测试步骤**:
  1. Mock orchestrator 返回 `total_tokens=1234`
  2. 调用 `_handle_multi_agent_query()`（mode=multi）
  3. 捕获 logger 输出，检查包含 "total_tokens=1234"
- **预期结果**: 日志记录 token 消耗
- **状态**: ✅ 通过

### TC-83-02: multi_agent 日志包含 workers 数量
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化
- **Mock 对象**: OrchestratorAgent.run, shared_memory.agent_outputs
- **测试步骤**:
  1. Mock shared_memory.agent_outputs 含 2 条记录
  2. 调用 `_handle_multi_agent_query()`（mode=multi）
  3. 捕获 logger 输出，检查包含 "workers=2"
- **预期结果**: 日志记录 worker 数量
- **状态**: ✅ 通过

### TC-83-03: 简单查询路由不误判 multi_agent
- **类型**: 回归测试
- **前置条件**: QueryRouter 已初始化（turbo_llm Mock）
- **Mock 对象**: turbo_llm.chat
- **测试步骤**:
  1. 调用 `router.route("中芯国际2024年营收是多少")`（与阶段三 TC-31-01 同款断言）
  2. 检查 `result.mode == "rag"`
- **预期结果**: 单公司简单查询不误路由 multi_agent（回归保障）
- **状态**: ✅ 通过

---

## 测试统计

| 测试组 | 项数 | 说明 |
|--------|:--:|------|
| TC-80: 工具描述嵌套展示 | 4 | agent/task/company_name 字段可见 + 普通工具不回归 |
| TC-81: orchestrator 提示词 | 2 | delegate 单任务/多任务调用示例 |
| TC-82: DelegateTool 统计 | 3 | 并行批次数观测 |
| TC-83: api_service 观测 | 3 | token/worker 日志 + 路由回归 |
| **合计** | **12** | |
