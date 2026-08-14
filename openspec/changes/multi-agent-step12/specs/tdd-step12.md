# TDD 测试用例: 多 Agent SSE 流式进展接入 Worker 步骤事件（阶段十二）

> 编码: UTF-8
> 约定: <span style="color:red">红色</span> = 未通过, <span style="color:green">绿色</span> = 已通过

---

## 一、测试文件规划

| 文件 | 测试范围 |
|------|---------|
| `tests/tdd_multi_agent_step12.py` | SP12-A / SP12-B（Python unittest，不依赖 LLM API） |

---

## 二、测试用例

### SP12-A: `ReActAgent.run()` 的 step_callback 行为（mock LLM）

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-12-A-01 | thought 事件推送 | mock `_call_llm` 返回 thought+action，注入 callback，调用 `run()` | callback 收到 `step_type="thought"` | <span style="color:green">GREEN</span> |
| TC-12-A-02 | action 事件推送 | 同上 | callback 收到 `step_type="action"` 且 content 为工具名 | <span style="color:green">GREEN</span> |
| TC-12-A-03 | observation 事件推送 | 同上，mock `_execute_action` 返回固定结果 | callback 收到 `step_type="observation"` | <span style="color:green">GREEN</span> |
| TC-12-A-04 | on_done 推送 | mock 第二轮回 Final Answer | callback 收到 `on_done` 且 success=True | <span style="color:green">GREEN</span> |

---

### SP12-B: `DelegateTool` 注入 StepCallback

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-12-B-01 | 注入 StepCallback | 带 event_queue 调用 `_run_worker_task` | Worker 的 `_step_callback` 非 None 且 agent_name 正确 | <span style="color:green">GREEN</span> |
| TC-12-B-02 | 无 queue 不注入 | 不带 event_queue 调用 `_run_worker_task` | Worker 的 `_step_callback` 为 None | <span style="color:green">GREEN</span> |
| TC-12-B-03 | worker_step 字段完整 | `StepCallback.on_step` 推送到 queue | 事件含 `type/agent/step_type/step/content` | <span style="color:green">GREEN</span> |

---

## 三、测试统计

| 规范 | 测试用例数 | 已通过 | 未通过 |
|------|:--:|:--:|:--:|
| SP12-A | 4 | 4 | 0 |
| SP12-B | 3 | 3 | 0 |
| **合计** | **7** | **7** | **0** |
