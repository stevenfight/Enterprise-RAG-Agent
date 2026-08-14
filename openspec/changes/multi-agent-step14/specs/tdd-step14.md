# TDD 测试用例: 数据来源页码映射修复（阶段十四）

> 编码: UTF-8
> 约定: <span style="color:red">红色</span> = 未通过, <span style="color:green">绿色</span> = 已通过

---

## 一、测试文件规划

| 文件 | 测试范围 |
|------|---------|
| `tests/tdd_multi_agent_step14.py` | SP14-A / SP14-B（Python unittest，依赖本地 PDF/markdown 测试数据，不依赖 LLM API） |

---

## 二、测试用例

### SP14-A: `build_line_page_map` 路径修复

使用本地真实数据：`data/stock_data/pdf_reports/电信2024年度报告.pdf`（218 页）与 `data/stock_data/debug_data/03_reports_markdown/电信2024年度报告.md`。

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-14-A-01 | 不恒为最后一页 | 抽样前 1/4、1/2、3/4、末尾行号调用 `line_to_page` | 结果不全部等于 218 | <span style="color:green">GREEN</span> |
| TC-14-A-02 | 首行映射第 1 页 | 对第 1 行调用 `line_to_page` | 返回第 1 页 | <span style="color:green">GREEN</span> |
| TC-14-A-03 | 末行接近末页 | 对最后一行调用 `line_to_page` | 返回接近 218 的页码 | <span style="color:green">GREEN</span> |

---

### SP14-B: `line_to_page` 页码单调性

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-14-B-01 | 行号递增页码不减 | 对递增行号序列调用 `line_to_page` | 页码序列单调不减 | <span style="color:green">GREEN</span> |

---

## 三、测试统计

| 规范 | 测试用例数 | 已通过 | 未通过 |
|------|:--:|:--:|:--:|
| SP14-A | 3 | 3 | 0 |
| SP14-B | 1 | 1 | 0 |
| **合计** | **4** | **4** | **0** |
