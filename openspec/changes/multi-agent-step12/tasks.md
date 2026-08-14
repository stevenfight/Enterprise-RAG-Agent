# 任务清单: 多 Agent SSE 流式进展接入 Worker 步骤事件（阶段十二）

> 编码: UTF-8

---

## 任务列表

| 序号 | 任务 | 产出 | 状态 |
|:--:|------|------|:--:|
| 1 | 创建 OpenSpec 变更记录 | proposal.md / design.md / tasks.md / specs/tdd-step12.md | 已完成 |
| 2 | 编写 TDD 用例规格（全线标红） | specs/tdd-step12.md | 已完成 |
| 3 | 编写后端单元测试（预期先红） | tests/tdd_multi_agent_step12.py | 已完成 |
| 4 | 运行测试确认红 | 测试输出 | 已完成 |
| 5 | run() 接入 step_callback | src/agent_core.py | 已完成 |
| 6 | DelegateTool 注入 StepCallback | src/tools/delegate_tool.py | 已完成 |
| 7 | 运行测试转绿 | 测试输出 | 已完成 |
| 8 | 纳入 run_all.py 回归 | tests/run_all.py | 已完成 |
| 9 | TDD 转绿 + 更新文档 | specs/tdd-step12.md 状态更新 | 已完成 |

---

## 验收标准

- `tests/tdd_multi_agent_step12.py` 全部 7 项用例通过：
  - SP12-A `run()` step_callback 行为 4 项
  - SP12-B `DelegateTool` 注入 StepCallback 3 项
- `python tests/run_all.py --skip-llm` 可运行新测试且无回归
- `src/agent_core.py` 的 `run()` 与 `run_stream()` 的 step_callback 调用点语义一致
- `src/tools/delegate_tool.py` 在有 `event_queue` 时向 Worker 注入 `StepCallback`
