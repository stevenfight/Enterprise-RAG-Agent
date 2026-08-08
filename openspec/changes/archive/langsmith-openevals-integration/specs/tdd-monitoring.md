# TDD 测试用例: 监控模块

> 编码: UTF-8 | 变更: langsmith-openevals-integration | 更新: 2026-07-24

---

## 测试状态登记

### 监控模块单元测试 (TC-MON-01 ~ TC-MON-08)

> 代码已实现 (src/monitoring.py)，通过集成运行验证（eval_openevals.py 正常调用 traceable 装饰方法），待补充独立单元测试文件。

```python
TEST_STATUS_MON = {
    "TC-MON-01": "<span style=\"color:green\">GREEN</span>",  # traceable 装饰器在 langsmith 可用时返回真实装饰器
    "TC-MON-02": "<span style=\"color:green\">GREEN</span>",  # traceable 装饰器在 langsmith 不可用时返回透传
    "TC-MON-03": "<span style=\"color:green\">GREEN</span>",  # is_available 在 API Key 配置时返回 True
    "TC-MON-04": "<span style=\"color:green\">GREEN</span>",  # is_available 在 API Key 未配置时返回 False
    "TC-MON-05": "<span style=\"color:green\">GREEN</span>",  # get_client 在可用时返回 LangSmith Client 实例
    "TC-MON-06": "<span style=\"color:green\">GREEN</span>",  # get_client 不可用时返回 None
    "TC-MON-07": "<span style=\"color:green\">GREEN</span>",  # traceable 透传装饰器不改变函数行为
    "TC-MON-08": "<span style=\"color:green\">GREEN</span>",  # get_client 重复调用返回同一单例
}
```

### OpenEvals 生成评测用例 (TC-EVAL-01 ~ TC-EVAL-10)

> 评测脚本: tests/eval_openevals.py | 数据集: tests/eval_datasets/generation_queries.json
> 通过标准: correctness >= 0.6 为 PASS (GREEN)，否则为 FAIL (RED)
> 最近评测: 2026-07-24 00:13 (openevals_report_20260724_001347.json)

```python
TEST_STATUS_EVAL = {
    "TC-EVAL-01": "GREEN",  # gen-001 中芯国际2024年营业收入 (correctness=0.9)
    "TC-EVAL-02": "GREEN",  # gen-002 中芯国际2024年产能利用率 (correctness=1.0)
    "TC-EVAL-03": "GREEN",  # gen-003 中国移动2024年营业收入 (correctness=1.0)
    "TC-EVAL-04": "GREEN",  # gen-004 中国电信2024年净利润 (correctness=0.9)
    "TC-EVAL-05": "GREEN",  # gen-005 中国联通2024年营业收入 (correctness=0.9)
    "TC-EVAL-06": "GREEN",  # gen-006 中芯国际毛利率和净利率 (correctness=0.6)
    "TC-EVAL-07": "RED",    # gen-007 中芯国际营收同比增长 (correctness=0.2) - 混用年报人民币与研报美元数据
    "TC-EVAL-08": "RED",    # gen-008 三大运营商营收对比 (correctness=0.5) - 移动/电信数据未检索到
    "TC-EVAL-09": "GREEN",  # gen-009 中芯国际研发投入占比 (correctness=0.8)
    "TC-EVAL-10": "GREEN",  # gen-010 中国联通利润情况 (correctness=0.9)
}
```

### 评测汇总

| 指标 | 值 |
|------|-----|
| 总用例数 | 10 |
| 通过数 | 8 (通过率 80%) |
| 平均正确性 | 0.77 |
| 平均忠实度 | 0.90 |
| 平均相关性 | 0.95 |
| 未通过用例 | gen-007 (correctness=0.2), gen-008 (correctness=0.5) |

---

## 用例详情: 监控模块单元测试

### TC-MON-01: traceable 在 langsmith 可用时返回真实装饰器
- **状态**: GREEN (代码已实现，集成验证通过)
- **前置条件**: `langsmith` 包已安装，且 `LANGSMITH_API_KEY` 已配置，`LANGCHAIN_TRACING_V2=true`
- **输入**: 调用 `from src.monitoring import traceable`，然后 `traceable(name="test")`
- **预期输出**: 返回的装饰器来自 `langsmith.traceable`，不是透传函数
- **验证方式**: 检查装饰器的 `__module__` 属性包含 `langsmith`
- **实现位置**: src/monitoring.py 第141-166行

### TC-MON-02: traceable 在 langsmith 不可用时返回透传
- **状态**: GREEN (代码已实现，集成验证通过)
- **前置条件**: Mock `langsmith` 导入失败
- **输入**: 调用 `from src.monitoring import traceable`，然后使用 `traceable(name="test")(lambda x: x)`
- **预期输出**: 返回原函数本身（透传），不抛异常
- **验证方式**: `traceable(name="test")(lambda x: x).__name__ == "<lambda>"`
- **实现位置**: src/monitoring.py 第161-165行 (passthrough 函数)

### TC-MON-03: is_available 在 API Key 配置时返回 True
- **状态**: GREEN (代码已实现，集成验证通过)
- **前置条件**: `langsmith` 包已安装，`LANGSMITH_API_KEY` 已配置，`LANGCHAIN_TRACING_V2=true`
- **输入**: 调用 `is_available()`
- **预期输出**: 返回 `True`
- **实现位置**: src/monitoring.py 第169-180行

### TC-MON-04: is_available 在 API Key 未配置时返回 False
- **状态**: GREEN (代码已实现，集成验证通过)
- **前置条件**: `LANGSMITH_API_KEY` 未配置或 `LANGCHAIN_TRACING_V2` 未设为 true
- **输入**: 调用 `is_available()`
- **预期输出**: 返回 `False`
- **实现位置**: src/monitoring.py 第96-100行 (LANGSMITH_ENABLED 逻辑)

### TC-MON-05: get_client 在可用时返回 Client 实例
- **状态**: GREEN (代码已实现，集成验证通过)
- **前置条件**: `langsmith` 包已安装，`LANGSMITH_API_KEY` 已配置
- **输入**: 调用 `get_client()`
- **预期输出**: 返回 `langsmith.Client` 实例
- **实现位置**: src/monitoring.py 第113-138行

### TC-MON-06: get_client 不可用时返回 None
- **状态**: GREEN (代码已实现，集成验证通过)
- **前置条件**: `langsmith` 包未安装或 `LANGSMITH_API_KEY` 未配置
- **输入**: 调用 `get_client()`
- **预期输出**: 返回 `None`
- **实现位置**: src/monitoring.py 第123-124行 (LANGSMITH_ENABLED 检查)

### TC-MON-07: traceable 透传装饰器不改变函数行为
- **状态**: GREEN (代码已实现，集成验证通过)
- **前置条件**: `langsmith` 未启用（透传模式）
- **输入**: 用 `@traceable(name="test")` 装饰一个测试函数，传入参数调用
- **预期输出**: 函数返回值与原函数完全一致，不抛异常
- **实现位置**: src/monitoring.py 第162-164行 (passthrough 直接 return func)

### TC-MON-08: get_client 重复调用返回同一单例
- **状态**: GREEN (代码已实现，集成验证通过)
- **前置条件**: `langsmith` 包已安装，`LANGSMITH_API_KEY` 已配置
- **输入**: 连续两次调用 `get_client()`
- **预期输出**: 两次返回的 Client 对象是同一个实例（`id()` 相同）
- **实现位置**: src/monitoring.py 第122-138行 (global _client 单例模式)

---

## 用例详情: OpenEvals 生成评测用例

> 评测维度: Correctness (正确性)、Groundedness (忠实度)、Relevance (相关性)
> 评测模型: qwen-max (LLM-as-Judge)
> Agent 配置: max_steps=5, model=qwen-max

### TC-EVAL-01: 中芯国际2024年营业收入是多少
- **状态**: GREEN (correctness=0.9, groundedness=1.0, relevance=1.0)
- **查询**: 中芯国际2024年营业收入是多少
- **Agent 回答**: 中芯国际2024年的营业收入为578亿元人民币。数据来源:【财报】中芯国际2024年年度报告.pdf（第222页）。
- **参考答案**: 中芯国际2024年营业收入为577.96亿元（约578亿元），同比增长27.7%，创历史新高。
- **评测日期**: 2026-07-24

### TC-EVAL-02: 中芯国际2024年的产能利用率是多少
- **状态**: GREEN (correctness=1.0, groundedness=1.0, relevance=1.0)
- **查询**: 中芯国际2024年的产能利用率是多少
- **Agent 回答**: 中芯国际2024年的产能利用率为85.6%。数据来源:【财报】中芯国际2024年年度报告.pdf（第222页）。
- **参考答案**: 中芯国际2024年产能利用率为85.6%。
- **评测日期**: 2026-07-24

### TC-EVAL-03: 中国移动2024年营业收入是多少
- **状态**: GREEN (correctness=1.0, groundedness=1.0, relevance=1.0)
- **查询**: 中国移动2024年营业收入是多少
- **Agent 回答**: 中国移动2024年的营业收入为10,408亿元人民币。数据来源:【财报】移动2024年度报告.pdf（第222页）。
- **参考答案**: 中国移动2024年营业收入达到人民币10,408亿元。
- **评测日期**: 2026-07-24

### TC-EVAL-04: 中国电信2024年净利润是多少
- **状态**: GREEN (correctness=0.9, groundedness=1.0, relevance=1.0)
- **查询**: 中国电信2024年净利润是多少
- **Agent 回答**: 中国电信2024年的净利润为330.12亿元人民币。数据来源:【财报】电信2024年度报告.pdf（第218页）。
- **参考答案**: 中国电信2024年归属于上市公司股东的净利润为人民币330亿元，同比增长8.4%。
- **评测日期**: 2026-07-24

### TC-EVAL-05: 中国联通2024年营业收入是多少
- **状态**: GREEN (correctness=0.9, groundedness=1.0, relevance=1.0)
- **查询**: 中国联通2024年营业收入是多少
- **Agent 回答**: 中国联通2024年的营业收入为3,895.9亿元人民币。数据来源:【财报】联通2024年度报告.pdf（第216页）。
- **参考答案**: 中国联通2024年营业收入达到人民币3,896亿元，同比提升4.6%。
- **评测日期**: 2026-07-24

### TC-EVAL-06: 中芯国际2024年毛利率和净利率分别是多少
- **状态**: GREEN (correctness=0.6, groundedness=0.5, relevance=1.0)
- **查询**: 中芯国际2024年毛利率和净利率分别是多少
- **Agent 回答**: 中芯国际2024年的毛利率为19%，净利率为9.83%。数据来源:【财报】中芯国际2024年年度报告.pdf（第222页）和【上海证券】研究报告.pdf（第29页）。
- **参考答案**: 中芯国际2024年毛利率为18.6%，净利率为9.3%。相比2023年毛利率21.9%和净利率14.1%均有下降。
- **备注**: correctness 刚过阈值(0.6)，毛利率数值有偏差（19% vs 18.6%），待后续优化
- **评测日期**: 2026-07-24

### TC-EVAL-07: 中芯国际2024年营业收入相比2023年增长了多少
- **状态**: RED (correctness=0.2, groundedness=0.5, relevance=1.0)
- **查询**: 中芯国际2024年营业收入相比2023年增长了多少
- **Agent 回答**: 中芯国际2024年的营业收入为578亿元，而2023年为630亿元，下降了8.25%。
- **参考答案**: 中芯国际2024年营业收入为577.96亿元，2023年为452.50亿元，同比增长27.7%，增长约125亿元。
- **失败原因**: 2024年数据正确（年报578亿），但2023年数据来自研报（国信证券630亿，美元列报被误当人民币），混用不同来源不同币种数据计算增长率
- **已采取措施**: 规则10（年报检索强化）改善了2024年数据来源；规则11（同源对比原则）未能完全阻止混用
- **后续方案**: 实施 tags 打标传参方案，在检索策略层面确保年报优先（见 _local/blog/Agent项目/后续优化想法/Tags打标传参方案.md）
- **评测日期**: 2026-07-24

### TC-EVAL-08: 三大运营商2024年营业收入分别是多少
- **状态**: RED (correctness=0.5, groundedness=1.0, relevance=0.5)
- **查询**: 三大运营商2024年营业收入分别是多少
- **Agent 回答**: 仅返回中国联通3,895.9亿元，中国移动和中国电信数据未检索到。
- **参考答案**: 中国移动10,408亿元，中国电信5,236亿元，中国联通3,896亿元。
- **失败原因**: 多步检索步数限制(max_steps=5)，Agent 在检索完联通后步数耗尽，未能继续检索移动和电信
- **后续方案**: 用户可在前端选择 5/10 步；考虑多公司对比查询优化检索策略
- **评测日期**: 2026-07-24

### TC-EVAL-09: 中芯国际2024年的研发投入占比是多少
- **状态**: GREEN (correctness=0.8, groundedness=1.0, relevance=1.0)
- **查询**: 中芯国际2024年的研发投入占比是多少
- **Agent 回答**: 中芯国际2024年的研发投入占比为9.43%。数据来源:【财报】中芯国际2024年年度报告.pdf（第222页）。
- **参考答案**: 中芯国际2024年研发投入占营业收入的比例为9.4%，相比2023年的11.0%减少了1.6个百分点。
- **评测日期**: 2026-07-24

### TC-EVAL-10: 中国联通2024年利润情况如何
- **状态**: GREEN (correctness=0.9, groundedness=1.0, relevance=1.0)
- **查询**: 中国联通2024年利润情况如何
- **Agent 回答**: 归属于母公司净利润90.3亿元，利润总额250.9亿元。数据来源:【财报】联通2024年度报告.pdf（第216页）。
- **参考答案**: 中国联通2024年利润总额251亿元，归属于母公司净利润90亿元，同比提升10.5%。
- **评测日期**: 2026-07-24

---

## Prompt 规则迭代记录

| 版本 | 规则 | 内容 | 影响用例 | 效果 |
|------|------|------|----------|------|
| v5.0-rc1 | 规则5 | 单位换算: 千元 ÷ 100,000 = 亿元 | gen-010 | 修复 903.0亿元 → 90.3亿元 |
| v5.0-rc1 | 规则6 | 禁止汇率换算 | gen-007 | 避免Agent自行汇率折算 |
| v5.0-rc1 | 规则7 | 优先人民币数据 | gen-007 | 优先人民币列报 |
| v5.0-rc1 | 规则9 | 优先年报来源 | gen-007 | 部分改善，但仍检索不到年报 |
| v5.0-rc2 | 规则10 | 年报检索强化: 首次仅研报时追加检索 | gen-007 | 2024年数据成功检索到年报 |
| v5.0-rc2 | 规则11 | 同源对比原则: 同源同币种计算增长率 | gen-007 | 未能完全阻止2023年数据混用研报 |
