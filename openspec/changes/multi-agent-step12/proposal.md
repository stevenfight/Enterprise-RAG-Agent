# 变更提案: 多 Agent SSE 流式进展接入 Worker 步骤事件（阶段十二）

> 编码: UTF-8

---

## 一、变更背景

阶段十已完成前端多 Agent 流式可视化（`applyAgentEvent` 纯函数 reducer + `MessageBubble` 展示）。但在浏览器实测中发现：多 Agent 运行时，界面上 5 个 Worker 均停留在「运行中 / 0 步」，既不显示每一步调用的 Agent 与工具，也没有流式进展。

## 二、根因分析

问题不在前端，而在后端 SSE 事件流从未推送 `worker_step`：

1. 多 Agent 模式下，`DelegateTool._run_worker_task` 调用的是 `worker.run()`（同步），而非 `run_stream()`（流式生成器）。
2. `ReActAgent.run()` 方法**没有**任何 `step_callback` 调用（对比 `run_stream()` 有完整的 `on_step("thought"/"action"/"observation")` 与 `on_done`）。
3. `DelegateTool._create_agent(cap, step_callback=None)` 的 `step_callback` 参数是「预留」状态，创建 Worker 时从未注入 `StepCallback`。

连锁结果：SSE 流只有 `orchestrator_start`（注册 Worker）与 `delegating`，之后没有任何 `worker_step`，前端每个 Worker 永远停在「运行中 / 0 步」。

附带问题：Worker 完成时 `DelegateTool` 推送的事件类型是 `worker_complete`，而前端 `applyAgentEvent` 只识别 `worker_done`，因此完成状态同样不会更新。

## 三、变更目标

让多 Agent 模式下的 Worker 在执行过程中，通过 `StepCallback` 将每一步（thought / action / observation）与完成状态推送到 SSE，使前端能够实时展示「每个 Worker 当前调用了哪个工具、进展到第几步」。

## 四、变更范围

仅改后端两处：

1. `src/agent_core.py` 的 `ReActAgent.run()`：接入 `step_callback`（推送 `thought` / `action` / `observation` / `answer` / `on_done`），与 `run_stream()` 保持一致。
2. `src/tools/delegate_tool.py` 的 `_run_worker_task`：在 `event_queue` 存在时构造 `StepCallback`，并注入到 Worker 的 `_step_callback`。

不改动：前端（阶段十已就绪）、Worker 构造函数签名（避免破坏既有调用点）、`run_stream()` 既有逻辑。

## 五、技术决策

1. **在 `run()` 中复用 `run_stream()` 的 step_callback 语义**：`on_step("thought"/"action"/"observation")` + `on_step("answer")` + `on_done`。
2. **注入方式**：在 `_run_worker_task` 创建 Worker 后，直接设置 `worker._step_callback = StepCallback(...)`，不修改 5 个 Worker 构造函数，遵循最小变更。
3. **StepCallback 的 agent_name 使用纯 Agent 名**（如 `DataAgent`），与 `delegating` 事件中 `agent_registry.list_all()` 返回的名称一致，保证前端能正确关联 Worker。
4. **保留 DelegateTool 既有 `worker_complete` 推送**：它前端虽不识别但无害；真正的完成状态由 `StepCallback.on_done` 推送的 `worker_done` 驱动。

## 六、测试策略（TDD 先红后绿）

- **SP12-A**：`ReActAgent.run()` 的 step_callback 行为（mock LLM 与工具执行），共 4 项。
- **SP12-B**：`DelegateTool` 注入 StepCallback 逻辑，共 3 项。

合计 7 项，Python unittest，不依赖 LLM API。

## 七、验收标准

- `tests/tdd_multi_agent_step12.py` 全部 7 项通过。
- `python tests/run_all.py --skip-llm` 运行新测试且无回归。
- 前端多 Agent 运行时，每个 Worker 能实时看到 `worker_step`（含工具调用）并最终变为完成态。
