# 任务清单: 多 Agent 回答来源标注具体页码（阶段十一）

> 编码: UTF-8

---

## 任务列表

| 序号 | 任务 | 产出 | 状态 |
|:--:|------|------|:--:|
| 1 | 创建 OpenSpec 变更记录 | proposal.md / design.md / tasks.md / specs/tdd-step11.md | 已完成 |
| 2 | 编写 TDD 用例规格（全线标红） | specs/tdd-step11.md | 已完成 |
| 3 | 编写后端单元测试（预期先红） | tests/tdd_multi_agent_step11.py | 已完成 |
| 4 | 运行测试确认红（SP11-B 红） | 测试输出 | 已完成 |
| 5 | 强化 prompt 页码标注规则 | config/agent_prompts.yaml + src/agent_core.py | 已完成 |
| 6 | 运行测试转绿 | 测试输出 | 已完成 |
| 7 | 纳入 run_all.py 回归 | tests/run_all.py | 已完成 |
| 8 | TDD 转绿 + 更新文档 | specs/tdd-step11.md 状态更新 | 已完成 |

---

## 验收标准

- `tests/tdd_multi_agent_step11.py` 全部 8 项用例通过：
  - SP11-A 页码格式化回归 3 项
  - SP11-B prompt 页码规则静态断言 5 项
- `python tests/run_all.py --skip-llm` 可运行新测试且无回归
- `config/agent_prompts.yaml` 中 `default / data_agent / compare_agent / verify_agent / orchestrator` 均含「页码」标注规则
- `src/agent_core.py` 硬编码默认 prompt 与 yaml `default` 节保持一致
