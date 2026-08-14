# 任务清单: SSE 流式一致性优化（阶段十三）

> 编码: UTF-8

---

## 任务列表

| 序号 | 任务 | 产出 | 状态 |
|:--:|------|------|:--:|
| 1 | 创建 OpenSpec 变更记录 | proposal.md / design.md / tasks.md / specs/tdd-step13.md | 已完成 |
| 2 | 编写 TDD 用例规格（全线标红） | specs/tdd-step13.md | 已完成 |
| 3 | 编写后端单元测试（预期先红） | tests/tdd_multi_agent_step13.py | 已完成 |
| 4 | 运行测试确认红 | 测试输出 | 已完成 |
| 5 | 单 Agent 补 answer_chunk 流式 | src/api_service.py | 已完成 |
| 6 | 清理冗余完成事件 | src/tools/delegate_tool.py + src/api_service.py + 前端类型 | 已完成 |
| 7 | 运行测试转绿 | 测试输出 | 已完成 |
| 8 | 纳入 run_all.py 回归 | tests/run_all.py | 已完成 |
| 9 | TDD 转绿 + 更新文档 | specs/tdd-step13.md 状态更新 | 已完成 |

---

## 验收标准

- `tests/tdd_multi_agent_step13.py` 全部 7 项用例通过：
  - SP13-A 拆句函数 3 项
  - SP13-B 单 Agent 流式 1 项
  - SP13-C DelegateTool 完成事件清理 2 项
  - SP13-D 删除 workers_done 静态断言 1 项
- `python tests/run_all.py --skip-llm` 可运行新测试且无回归
- 单 Agent 与多 Agent 均具备 `answer_chunk` 流式答案
- 多 Agent 完成事件统一为 `worker_done`
