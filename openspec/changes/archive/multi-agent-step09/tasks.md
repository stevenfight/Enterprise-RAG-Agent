# 任务清单: 多 Agent 升级 - 阶段九 启用/运行验证 + 可靠性回归补测

> 编码: UTF-8

---

## 任务列表

| 序号 | 任务 | 产出 | 状态 |
|:--:|------|------|:--:|
| 1 | 创建 OpenSpec 变更记录 | proposal.md / tasks.md / specs/tdd-step09.md | 已完成 |
| 2 | 编写 TDD 用例规格（全线标红） | specs/tdd-step09.md | 已完成 |
| 3 | 编写单元测试文件 | tests/tdd_multi_agent_step09.py | 已完成 |
| 4 | 运行单元测试（预期先红后绿） | 测试输出 | 已完成 |
| 5 | 通过后 TDD 转绿 | specs/tdd-step09.md 状态更新 | 已完成 |
| 6 | 纳入 run_all.py 一键回归 | tests/run_all.py | 已完成 |

---

## 验收标准

- `tests/tdd_multi_agent_step09.py` 全部 25 项用例通过（不依赖 LLM）：
  - SP9-A 启用验证 6 项
  - SP9-B 运行链路验证 4 项
  - SP9-C 修复点回归 15 项
- `tests/run_all.py` 能识别并运行新测试
- 生产代码（`src/`、`config/`）零改动
