# 变更提案: 多 Agent 升级 - 阶段四 API 端点统一

> 编码: UTF-8
> 状态: 已完成
> 日期: 2026-08-07

---

## 1. 变更背景

阶段零 ~ 阶段三已完成多 Agent 核心链路（Orchestrator + 5 Worker + 并行调度 + Reflector 接入）。当前 api_service.py 存在三个与总体规划的偏差：

1. **POST 端点参数不完整**：`AgentQueryRequest` 缺少 `mode`（用户手动指定模式）和 `company_name` 字段。当前只能通过 router 自动路由到 multi_agent，用户无法显式指定模式。
2. **GET SSE 端点缺少 mode 参数**：`/api/agent/stream` 无 `mode` 查询参数，同样只能依赖自动路由。
3. **SSE 事件类型不完整**：总体规划定义了 6 种多 Agent 专属 SSE 事件（`orchestrator_start`/`delegating`/`worker_step`/`workers_done`/`answer_chunk`/`reflection`），当前实现了 `orchestrator_start` 和 `worker_step`，缺少 `delegating`/`workers_done`/`answer_chunk`/独立的 `reflection` 事件。

此外，当前 multi_agent 流式逻辑内联在 `event_generator()` 闭包中（~100 行），与总体规划中 `_stream_multi_agent` / `_stream_single_agent` 独立函数的期望不符，代码可读性和可测试性差。

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| POST 参数统一 | `AgentQueryRequest` 新增 `mode` 和 `company_name`，与 GET 端点一致 |
| GET 参数统一 | `/api/agent/stream` 新增 `mode` 参数，支持 `auto`/`single`/`multi` |
| 显式 mode 支持 | `mode="multi"` 绕开 router 直接执行多 Agent 链路；`mode="single"` 强制执行单 Agent |
| SSE 事件补全 | 新增 `delegating`/`workers_done`/`answer_chunk` 事件，`reflection` 独立于 `answer` |
| 代码结构化 | 提取 `_stream_multi_agent` 和 `_stream_single_agent` 独立异步生成器函数 |
| company_name 传递 | POST/SSE 多 Agent 模式将 `company_name` 传递给 OrchestratorAgent |
| 向后兼容 | 不加 mode 参数时行为保持不变；阶段一~三 184 项测试（179 通过 + 5 跳过），零回归失败 |

## 3. 变更范围

### 3.1 修改模块

| 模块 | 文件 | 说明 |
|------|------|------|
| API 端点 | `src/api_service.py` | POST/GET 参数扩展、多 Agent SSE 事件补全、代码结构化 |

### 3.2 不修改模块

| 模块 | 说明 |
|------|------|
| `src/agent_core.py` | ReActAgent 核心不变（SSE 事件由 api_service 层生成） |
| `src/orchestrator_agent.py` | 逻辑完全不变（`ReActAgent.run()` 早已有 `company_name` 参数，OrchestratorAgent 继承即可用，仅需在 api_service 调用时传入） |
| `src/tools/delegate_tool.py` | DelegateTool 事件推送不变（`delegating`/`workers_done` 由 api_service 层在调用 DelegateTool 前后包装） |
| `src/shared_memory.py` / `src/agent_registry.py` | 阶段二已实现，不变 |
| 5 个 Worker Agent | 阶段一/三已实现，不变 |
| `src/reflector.py` | 反思核心逻辑不变 |
| `src/router.py` | 路由逻辑不变 |
| 前端 / 部署脚本 | 不变 |

## 4. 前置依赖

- 步骤 0.3: 三层路由已标记 multi_agent 模式
- 步骤 2.3: DelegateTool 依赖注入（agent_registry / shared_memory / event_queue）
- 步骤 2.4: OrchestratorAgent 已实现 run() 方法
- 步骤 3.1: DelegateTool 并行执行 + StepCallback event_queue
- 步骤 3.6: Reflector 接入验证已通过

## 5. 关键设计决策

| 决策 | 说明 |
|------|------|
| 不改 RunCommandRun | api_service 的 `delegating`/`workers_done` 事件在调用 delegate_tool.run() 前后由 api_service 层包装，不改动 delegate_tool.py |
| answer_chunk 拆分 | Orchestrator 最终 answer 按句子拆分流式推送，每个句子一个 `answer_chunk` 事件，最后推送完整 `answer` 事件 |
| reflection 独立事件 | 当前 `reflection` 嵌套在 `answer` payload 内，改为独立 `reflection` 事件，清晰隔离 |
| 不引入新依赖 | 不新增第三方库，仅用标准库 + 已有 FastAPI/threading |
| company_name 传递链 | api_service → OrchestratorAgent.run(company_name=...) （`ReActAgent.run()` 早已支持 `company_name` 参数，在 api_service 调用时传入即可） |

## 6. 关联风险

| 风险 | 等级 | 缓解 |
|------|:--:|------|
| 流式逻辑重组可能引入并发问题 | 中 | 保持现有 threading.Thread + event_queue 轮询模式不变，仅从闭包提取为独立 async generator |
| 现有 SSE 前端消费者可能不识别新事件类型 | 低 | 新增事件类型采用增量方式，前端不识别时自动忽略（SSE 标准行为） |
| mode 参数验证 | 低 | Pydantic Field 加 Literal 约束，非法值拒绝 |

## 7. 验证策略

- TDD: 新增 15 项测试（参数扩展 5 项 + mode 路由 5 项 + SSE 事件 5 项），先标红后转绿
- 回归: 阶段一~三共 184 项测试全部通过
- 手动: curl 验证 POST `mode="multi"` 直接执行多 Agent；SSE 端点验证新事件类型
