# 变更提案: SSE 流式一致性优化（阶段十三）

> 编码: UTF-8

---

## 一、变更背景

阶段十/十二已完成多 Agent SSE 流式可视化与 Worker 步骤事件接入。但梳理发现单 Agent 与多 Agent 两条 SSE 链路存在不一致与冗余：

1. **单 Agent 缺少流式答案**：多 Agent 有 `answer_chunk`（按句拆分、打字机效果），单 Agent 只有一次性 `answer`，答案展示体验不一致。
2. **多 Agent 完成事件冗余**：`DelegateTool` 推送 `worker_complete`（前端不识别），`_stream_multi_agent` 推送 `workers_done`（前端不消费），与真正驱动前端的 `worker_done`（`StepCallback.on_done`）重叠，造成字段漂移隐患（阶段十二正是此类漂移的后果）。

## 二、变更目标

1. 单 Agent 答案补齐 `answer_chunk` 流式，与多 Agent 体验对齐。
2. 清理多 Agent 冗余完成事件：统一为 `worker_done`，删除前端不消费的 `worker_complete` 与 `workers_done`。

## 三、变更范围

- 后端：
  - `src/api_service.py`：新增 `_split_answer_chunks` 拆句函数；`_stream_single_agent` 补 `answer_chunk`；`_stream_multi_agent` 复用拆句函数并删除 `workers_done` 推送。
  - `src/tools/delegate_tool.py`：删除成功路径 `worker_complete` 推送；失败路径改为推送 `worker_done`（兜底）。
- 前端（类型清理）：
  - `frontend/src/types/chat.ts`：删除 `workers_done` 类型与 `worker_count` 字段。
  - `frontend/src/utils/agentEvent.ts`：`MULTI_AGENT_EVENT_TYPES` 删除 `workers_done`。

## 四、技术决策

1. **拆句逻辑提取为纯函数** `_split_answer_chunks(text)`，单 Agent 与多 Agent 复用，消除重复。
2. **单 Agent answer_chunk 时序**：在 `answer` 事件之前先推 `answer_chunk`，前端累积流式展示后由 `answer` 覆盖为完整答案（与多 Agent 一致）。
3. **成功路径不再推 `worker_complete`**：`run()` 已通过 `StepCallback.on_done` 推送 `worker_done`，DelegateTool 成功路径无需重复。
4. **失败路径兜底推 `worker_done(success=False)`**：当 Worker 超时/异常导致 `run()` 未走到 `on_done` 时，由 DelegateTool 兜底推送，保证前端 Worker 完成态正确。

## 五、测试策略（TDD 先红后绿）

- **SP13-A**：`_split_answer_chunks` 拆句（3 项）。
- **SP13-B**：单 Agent 流式推 `answer_chunk`（1 项）。
- **SP13-C**：DelegateTool 完成事件清理（2 项）。
- **SP13-D**：`api_service.py` 删除 `workers_done`（静态断言 1 项）。

合计 7 项，Python unittest，不依赖 LLM API。

## 六、验收标准

- `tests/tdd_multi_agent_step13.py` 全部 7 项通过。
- `python tests/run_all.py --skip-llm` 运行新测试且无回归。
- 前端单 Agent 与多 Agent 答案均具备 `answer_chunk` 流式效果。
- 多 Agent 完成事件统一为 `worker_done`，无 `worker_complete` / `workers_done` 残留。
