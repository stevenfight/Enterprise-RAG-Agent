# TDD 测试用例: 多 Agent 回答来源标注具体页码（阶段十一）

> 编码: UTF-8
> 约定: <span style="color:red">红色</span> = 未通过, <span style="color:green">绿色</span> = 已通过

---

## 一、测试文件规划

| 文件 | 测试范围 |
|------|---------|
| `tests/tdd_multi_agent_step11.py` | SP11-A / SP11-B（Python unittest，不依赖 LLM API） |

---

## 二、测试用例

### SP11-A: 页码格式化回归（RetrieveTool._format_results）

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-11-A-01 | 空页码 | 对 `pages=[]` 调用 `_format_results` | `pages` 字段为「页码未知」 | <span style="color:green">GREEN</span> |
| TC-11-A-02 | 单页 | 对 `pages=[23]` 调用 `_format_results` | `pages` 字段为「第23页」 | <span style="color:green">GREEN</span> |
| TC-11-A-03 | 多页区间 | 对 `pages=[23,24,25]` 调用 `_format_results` | `pages` 字段为「第23-25页」 | <span style="color:green">GREEN</span> |

---

### SP11-B: prompt 页码标注规则静态断言

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-11-B-01 | default 含页码规则 | 读取 yaml `default.template`，断言含「页码」 | 通过 | <span style="color:green">GREEN</span> |
| TC-11-B-02 | data_agent 含页码规则 | 读取 yaml `data_agent.template`，断言含「页码」 | 通过 | <span style="color:green">GREEN</span> |
| TC-11-B-03 | compare_agent 含页码规则 | 读取 yaml `compare_agent.template`，断言含「页码」 | 通过 | <span style="color:green">GREEN</span> |
| TC-11-B-04 | verify_agent 含页码规则 | 读取 yaml `verify_agent.template`，断言含「页码」 | 通过 | <span style="color:green">GREEN</span> |
| TC-11-B-05 | orchestrator 含页码规则 | 读取 yaml `orchestrator.template`，断言含「页码」 | 通过 | <span style="color:green">GREEN</span> |

---

## 三、测试统计

| 规范 | 测试用例数 | 已通过 | 未通过 |
|------|:--:|:--:|:--:|
| SP11-A | 3 | 3 | 0 |
| SP11-B | 5 | 5 | 0 |
| **合计** | **8** | **8** | **0** |
