# 设计文档: 多 Agent SSE 流式进展接入 Worker 步骤事件（阶段十二）

> 编码: UTF-8

---

## 一、问题链路

```
OrchestratorAgent.run()
  └─ DelegateTool.run(tasks)
       └─ _run_worker_task(task)
            └─ worker.run(query, ...)   ← 同步执行，无 step_callback
                 └─ ReActAgent.run()    ← 未调用 self._step_callback
                      → 无 worker_step 事件 → 前端 Worker 停在 0 步
```

前端侧（阶段十已完成）：
- `orchestrator_start` → 注册 5 个 Worker（初始「运行中 / 0 步」）
- `delegating` → 创建 Worker 状态
- `worker_step` → 追加步骤（**当前缺失**）
- `worker_done` → 标记完成（**当前缺失，且后端推送的是前端不识别的 `worker_complete`**）

## 二、修复设计

### 2.1 `ReActAgent.run()` 接入 step_callback

在 `run()` 的 ReAct 主循环中，参照 `run_stream()` 的调用点加入：

| 位置 | 回调调用 |
|------|---------|
| 解析 LLM 响应后 | `on_step("thought", step+1, thought)` |
| 执行工具前 | `on_step("action", step+1, action)` |
| 执行工具后 | `on_step("observation", step+1, observation[:500])` |
| Final Answer 分支 | `on_step("answer", step+1, final_answer[:500])` + `on_done(AgentResult(success=True, ...))` |
| 达到 max_steps 强制答案 | `on_step("answer", self.max_steps, forced_answer[:500])` + `on_done(...)` |
| LLM 调用失败 | `on_done(AgentResult(success=False, ...))` |

所有调用前判断 `if self._step_callback:`，兼容单 Agent 直接调用（callback 为 None）。

### 2.2 `DelegateTool._run_worker_task` 注入 StepCallback

在方法开头读取 `agent_name` 后构造回调：

```python
step_callback = None
if self._event_queue is not None:
    from src.step_callback import StepCallback
    step_callback = StepCallback(agent_name=agent_name, event_queue=self._event_queue)
```

在创建 Worker 后注入：

```python
worker = self._create_agent(cap)
if worker is None:
    return self._build_failure_entry(task, f"Agent '{agent_name}' 创建失败")
if step_callback is not None:
    worker._step_callback = step_callback
```

### 2.3 StepCallback 事件形态

`StepCallback.on_step` 推送 `worker_step`：

```json
{"type": "worker_step", "agent": "DataAgent", "step_type": "action", "step": 1, "content": "retrieve", "timestamp": ...}
```

`StepCallback.on_done` 推送 `worker_done`：

```json
{"type": "worker_done", "agent": "DataAgent", "success": true, "total_steps": 2, "total_elapsed_ms": 1234, "timestamp": ...}
```

前端 `applyAgentEvent` 已能消费上述两种事件（`worker_step` 追加步骤、`worker_done` 标记完成）。

## 三、测试设计

### SP12-A: `ReActAgent.run()` 的 step_callback 行为（4 项）

通过 mock `_call_llm`（首轮返回 thought+action，次轮返回 Final Answer）与 `_execute_action`（返回固定 observation），注入 mock `step_callback`，验证：

1. thought 事件被推送（`step_type="thought"`）
2. action 事件被推送（`step_type="action"`，`content` 为工具名）
3. observation 事件被推送（`step_type="observation"`）
4. on_done 被推送且 `success=True`

### SP12-B: `DelegateTool` 注入 StepCallback（3 项）

1. 有 `event_queue` 时，Worker 被注入 `_step_callback`（非 None，agent_name 正确）
2. 无 `event_queue` 时，Worker 不被注入（`_step_callback` 为 None）
3. `StepCallback.on_step` 推送到 queue 的事件字段完整（含 `type/agent/step_type/step/content`）

## 四、一致性保证

- `run()` 与 `run_stream()` 的 step_callback 调用点语义一致。
- `StepCallback` 的 agent_name 与 `delegating` 事件中的 agent 列表一致（纯 Agent 名）。
- 单 Agent 模式（`callback=None`）行为不变。
