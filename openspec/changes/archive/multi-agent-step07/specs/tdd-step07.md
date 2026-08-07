# TDD 规格: 多 Agent 升级 - 阶段四 API 端点统一

> 编码: UTF-8
> 日期: 2026-08-07
> 状态: 已通过（15/15 ✅）

---

## 测试组 TC-70: AgentQueryRequest 参数扩展（5 项）

### TC-70-01: AgentQueryRequest 包含 mode 字段
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 实例化 `AgentQueryRequest(query="测试", mode="multi")`
  2. 检查 `request.mode == "multi"`
- **预期结果**: mode 字段存在且值正确
- **状态**: ✅ 通过

### TC-70-02: AgentQueryRequest 包含 company_name 字段
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 实例化 `AgentQueryRequest(query="测试", company_name="中芯国际")`
  2. 检查 `request.company_name == "中芯国际"`
- **预期结果**: company_name 字段存在且值正确
- **状态**: ✅ 通过

### TC-70-03: AgentQueryRequest mode 默认值为 auto
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 实例化 `AgentQueryRequest(query="测试")`（不传 mode）
  2. 检查 `request.mode == "auto"`
- **预期结果**: mode 默认值为 "auto"
- **状态**: ✅ 通过

### TC-70-04: mode 非法值应被拒绝
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 尝试实例化 `AgentQueryRequest(query="测试", mode="invalid")`
  2. 捕获 ValidationError
- **预期结果**: Pydantic 验证拒绝非法 mode 值
- **状态**: ✅ 通过

### TC-70-05: company_name 默认值为 None
- **类型**: 单元测试
- **前置条件**: 无
- **测试步骤**:
  1. 实例化 `AgentQueryRequest(query="测试")`（不传 company_name）
  2. 检查 `request.company_name is None`
- **预期结果**: company_name 默认值为 None
- **状态**: ✅ 通过

---

## 测试组 TC-71: mode 路由控制（5 项）

### TC-71-01: mode="single" 时不调用 router
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化
- **Mock 对象**: router
- **测试步骤**:
  1. 设置 `request.mode = "single"`
  2. 调用 `api_agent_query` 端点
  3. 确认 router.route() 未被调用
- **预期结果**: 跳过 router，直接走单 Agent 流程
- **状态**: ✅ 通过

### TC-71-02: mode="multi" 时不调用 router
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化，AgentRegistry 已注册
- **Mock 对象**: router, OrchestratorAgent
- **测试步骤**:
  1. 设置 `request.mode = "multi"`
  2. 调用 `api_agent_query` 端点
  3. 确认 router.route() 未被调用
  4. 确认 OrchestratorAgent.run() 被调用
- **预期结果**: 跳过 router，直接执行多 Agent 链路
- **状态**: ✅ 通过

### TC-71-03: mode="auto" 且 router 不可用时 fallback 到 single
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化，router 不可用
- **Mock 对象**: shared_state 中 query_router 为 None
- **测试步骤**:
  1. 设置 router 为 None
  2. 设置 `request.mode = "auto"`
  3. 调用 `api_agent_query` 端点
  4. 确认走了单 Agent 流程
- **预期结果**: fallback 到单 Agent，不抛异常
- **状态**: ✅ 通过

### TC-71-04: mode="multi" 下 company_name 传递给 Orchestrator
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化
- **Mock 对象**: OrchestratorAgent.run
- **测试步骤**:
  1. 设置 `request.mode = "multi"`, `request.company_name = "中芯国际"`
  2. 调用 `api_agent_query` 端点
  3. 确认 `OrchestratorAgent.run` 被调用时 `company_name="中芯国际"`
- **预期结果**: company_name 正确传递到 OrchestratorAgent
- **状态**: ✅ 通过

### TC-71-05: GET /api/agent/stream mode 参数解析
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化
- **测试步骤**:
  1. 发起 GET `/api/agent/stream?query=测试&mode=multi`
  2. 检查 SSE 流中第一个事件的 `type` 字段
- **预期结果**: mode 参数正确解析，进入 multi_agent 流式分支
- **状态**: ✅ 通过

---

## 测试组 TC-72: 多 Agent SSE 事件完整性（5 项）

> 说明：`orchestrator_start` 已在阶段二实现并验证，属于回归保障范畴，不纳入本轮新增 TDD。
> TC-72 聚焦阶段四新增的 4 种事件（delegating / workers_done / answer_chunk / reflection）
> 加通用回归项 connected（验证重构未破坏现有行为）。

### TC-72-01: SSE 流中包含 delegating 事件
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化，mode="multi"
- **Mock 对象**: OrchestratorAgent.run, shared_memory
- **测试步骤**:
  1. 发起 SSE 流请求 mode=multi
  2. 收集所有事件类型
  3. 检查事件类型列表中包含 `delegating`
- **预期结果**: delegating 事件存在
- **状态**: ✅ 通过

### TC-72-02: SSE 流中包含 workers_done 事件
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化，mode="multi"
- **Mock 对象**: OrchestratorAgent.run, shared_memory
- **测试步骤**:
  1. 发起 SSE 流请求 mode=multi
  2. 收集所有事件类型
  3. 检查事件类型列表中包含 `workers_done`
- **预期结果**: workers_done 事件存在
- **状态**: ✅ 通过

### TC-72-03: answer_chunk 事件按句子拆分
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化，mode="multi"
- **Mock 对象**: OrchestratorAgent.run 返回多句答案
- **测试步骤**:
  1. Mock Orchestrator 返回 `"中芯国际营收增长10%。中国移动营收增长5%。"`
  2. 发起 SSE 流请求 mode=multi
  3. 收集所有 `answer_chunk` 事件
  4. 检查至少有 2 个 answer_chunk 事件
- **预期结果**: answer 被正确拆分，多个 answer_chunk 事件
- **状态**: ✅ 通过

### TC-72-04: reflection 为独立事件（非嵌套在 answer 内）
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化，mode="multi"，reflector 可用
- **Mock 对象**: OrchestratorAgent.run, reflector.verify
- **测试步骤**:
  1. 发起 SSE 流请求 mode=multi
  2. 收集所有事件
  3. 检查存在独立的 `reflection` 事件（type="reflection"）
  4. 检查 `answer` 事件中不含 `reflection` 字段
- **预期结果**: reflection 为独立 SSE 事件，不出现在 answer payload 中
- **状态**: ✅ 通过

### TC-72-05: SSE 流中应包含 connected 事件
- **类型**: 集成测试（Mock）
- **前置条件**: api_service 已初始化，mode="multi"
- **测试步骤**:
  1. 发起 SSE 流请求 mode=multi
  2. 检查第一个事件的 type 为 "connected"
- **预期结果**: connected 事件存在且为首个事件
- **状态**: ✅ 通过



---

## 测试统计

| 测试组 | 项数 | 说明 |
|--------|:--:|------|
| TC-70: 参数扩展 | 5 | mode/company_name 字段、默认值、验证 |
| TC-71: mode 路由 | 5 | single/multi/auto 路由逻辑、company_name 传递 |
| TC-72: SSE 事件 | 5 | delegating/workers_done/answer_chunk/reflection/connected |
| **合计** | **15** | |
