# 任务清单: 数据来源页码映射修复（阶段十四）

> 编码: UTF-8

---

## 任务列表

| 序号 | 任务 | 产出 | 状态 |
|:--:|------|------|:--:|
| 1 | 创建 OpenSpec 变更记录 | proposal.md / design.md / tasks.md / specs/tdd-step14.md | 已完成 |
| 2 | 编写 TDD 用例规格（全线标红） | specs/tdd-step14.md | 已完成 |
| 3 | 编写后端单元测试（预期先红） | tests/tdd_multi_agent_step14.py | 已完成 |
| 4 | 运行测试确认红 | 测试输出 | 已完成 |
| 5 | 修复 build_line_page_map 路径 | src/text_splitter.py | 已完成 |
| 6 | 运行测试转绿 | 测试输出 | 已完成 |
| 7 | 纳入 run_all.py 回归 | tests/run_all.py | 已完成 |
| 8 | TDD 转绿 + 更新文档 | specs/tdd-step14.md 状态更新 | 已完成 |

---

## 验收标准

- `tests/tdd_multi_agent_step14.py` 全部 4 项用例通过：
  - SP14-A 路径修复 3 项
  - SP14-B 单调性 1 项
- `python tests/run_all.py --skip-llm` 可运行新测试且无回归
- 与阶段十五（tags 打标）共享一次 `text_splitter.py + ingestion.py --rebuild` 重建
