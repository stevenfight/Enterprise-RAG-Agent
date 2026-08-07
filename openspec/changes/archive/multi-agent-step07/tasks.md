# 任务清单: 多 Agent 升级 - 阶段四 API 端点统一

> 编码: UTF-8
> 日期: 2026-08-07
> 状态: 已完成

---

## 步骤 4.1：POST 端点参数扩展

- [x] `AgentQueryRequest` 新增 `company_name: Optional[str] = None` 字段
- [x] `AgentQueryRequest` 新增 `mode: str = "auto"` 字段（取值 auto/single/multi）
- [x] POST `/api/agent/query` 支持 `mode="multi"` 直接执行多 Agent（不依赖 router）
- [x] POST `/api/agent/query` 支持 `mode="single"` 强制执行单 Agent（跳过 router）
- [x] POST `/api/agent/query` 多 Agent 模式传递 `company_name` 给 OrchestratorAgent
- [x] 验证：TDD 参数扩展 5 项全部转绿

## 步骤 4.2：GET SSE 端点参数扩展 + 代码结构化

- [x] GET `/api/agent/stream` 新增 `mode` 查询参数（auto/single/multi）
- [x] 提取 `_stream_single_agent()` 独立 async generator 函数
- [x] 提取 `_stream_multi_agent()` 独立 async generator 函数
- [x] `event_generator()` 闭包改为调用 `_stream_multi_agent()` / `_stream_single_agent()`
- [x] 验证：TDD mode 路由 5 项全部转绿

## 步骤 4.3：多 Agent SSE 事件补全

- [x] 新增 `delegating` 事件：含 agent 列表占位信息
- [x] 新增 `workers_done` 事件：从 shared_memory 读取 worker_count
- [x] 新增 `answer_chunk` 事件：按句子拆分流式推送
- [x] `reflection` 改为独立事件（当前嵌套在 `answer` payload 内）
- [x] POST/SSE 多 Agent 模式传递 `company_name` 给 `orchestrator.run()`（无需改文件，仅加调用参）
- [x] 验证：TDD SSE 事件 5 项全部转绿

## 验证（全部步骤完成后）

- [x] 运行新增 15 项 TDD 测试全部通过
- [x] 运行阶段三 30 项 TDD 测试全部通过（回归）
- [x] 运行阶段二 28 项 TDD 测试全部通过（回归）
- [x] 运行阶段一 15 项 TDD 测试全部通过（回归）
- [x] 运行阶段零 109 项 + 其他 7 项测试全部通过（回归）
- [x] 手动 curl POST `{"mode":"multi","query":"..."}` 验证直接执行多 Agent
- [x] 手动 curl GET SSE `mode=multi` 验证新事件类型推送

---

## 实施记录

| 日期 | 步骤 | 文件 | 操作 | 说明 |
|------|------|------|:--:|------|
| 2026-08-07 | 4.1 | `src/api_service.py:L336-347` | 修改 | AgentQueryRequest 新增 mode + company_name + field_validator |
| 2026-08-07 | 4.2 | `src/api_service.py:L748-828` | 新增 | _handle_multi_agent_query 独立函数 (POST mode 路由) |
| 2026-08-07 | 4.2 | `src/api_service.py:L830-993` | 新增 | _stream_single_agent + _stream_multi_agent (代码结构化) |
| 2026-08-07 | 4.2 | `src/api_service.py:L1098-1131` | 修改 | GET endpoint 签名加 mode 参数 + event_generator 简化 |
| 2026-08-07 | 4.3 | `src/api_service.py` | 新增 | delegating / workers_done / answer_chunk / reflection 独立事件 |
| 2026-08-07 | 4.3 | `src/api_service.py` | 修改 | orchestrator.run() 调用传入 company_name (POST + SSE) |
| 2026-08-07 | 验证 | `tests/tdd_multi_agent_step07.py` | 新增 | 15 项 TDD 全部通过 |
| 2026-08-07 | 回归 | 7 个 TDD 文件 | 验证 | 194 passed + 5 skipped, 零回归 |
| 2026-08-07 | 手动验证 | `src/api_service.py:L806-807, L976-977` | 修改 | 发现并修复 reflection 事件属性 bug: `ref_result.score/issues` → `ref_result.overall_confidence/suggestions`（ReflectionResult 无 score/issues 属性，导致 POST/SSE 多 Agent 返回 500） |
| 2026-08-07 | 手动验证 | curl POST + GET SSE | 验证 | POST mode=multi 直接执行多 Agent 通过；GET SSE mode=multi 8 种事件完整推送（connected/orchestrator_start/delegating/workers_done/answer_chunk/answer/reflection/done） |
