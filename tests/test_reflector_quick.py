# -*- coding: utf-8 -*-
"""reflector 快速验证"""

import sys
sys.path.insert(0, "src")

from reflector import AnswerReflector

r = AnswerReflector()

print("=" * 60)
print("1. 无幻觉: 数据点与来源一致")
print("=" * 60)
result = r.verify(
    answer="中芯国际2024年营收为578.21亿元，同比增长17.48%。",
    sources=[
        {"text": "2024年度公司实现营业收入578.21亿元"},
        {"text": "同比增长17.48%，盈利能力持续提升"},
    ],
)
print("  has_hallucination=%s" % result.has_hallucination)
print("  confidence=%.2f" % result.overall_confidence)
print("  hallucination_count=%d/%d" % (result.hallucination_count, result.total_datapoints))

print("\n2. 幻觉检测: 数据与来源不一致")
result = r.verify(
    answer="中国移动2024年净利润为2000亿元",
    sources=[{"text": "归属于母公司股东的净利润为1,384亿元"}],
)
print("  has_hallucination=%s" % result.has_hallucination)
print("  hallucinations=%d/%d" % (result.hallucination_count, result.total_datapoints))
for d in result.details:
    if d["is_hallucination"]:
        print("  [幻觉] %s → 建议修正: %s" % (d["claim_raw"], d.get("correction", "无")))

print("\n3. 多数据点逐条验证 (1/3 幻觉)")
result = r.verify(
    answer="中芯国际营收578亿，净利润120亿，总资产2000亿",
    sources=[
        {"text": "2024年营收578.21亿元，净利润36.99亿元"},
    ],
)
print("  has_hallucination=%s, count=%d/%d" % (result.has_hallucination,
      result.hallucination_count, result.total_datapoints))
for d in result.details:
    status = "[幻觉]" if d["is_hallucination"] else "[正常]"
    print("  %s %s → best_distance=%.4f" % (status, d["claim_raw"], d.get("best_distance", 0)))

print("\n4. 来源完整性检查 (部分有来源)")
result = r.verify(
    answer="中芯国际营收578亿，净利润120亿",
    sources=[{"text": "营业收入578亿"},{},{}],
)
print("  source_completeness=%.2f" % result.source_completeness)

print("\n5. 回答完整性: 缺少公司")
result = r.verify(
    answer="中国移动2024年营收为1250亿元。",
    sources=[{"text": "营收1250亿元"}],
    user_query="中国移动和中国联通2024年营收对比",
)
print("  answer_completeness=%.2f" % result.answer_completeness)

print("\n6. 自动修正: 替换幻觉值")
result = r.verify(
    answer="中芯国际2024年营收2000亿，净利润500亿",
    sources=[{"text": "营收578.21亿元，净利润36.99亿元"}],
)
print("  原始答案: '%s'" % result.details[0]["context"][:50])
if result.corrected_answer:
    print("  修正后: '%s'..." % result.corrected_answer[:60])

print("\n7. check_hallucination 便捷方法")
r2 = r.check_hallucination(
    answer="中芯国际营收578亿",
    sources=[{"text": "营收578亿"}],
)
print("  has_hallucination=%s, confidence=%.2f" % (r2["has_hallucination"], r2["confidence"]))

print("\n8. suggest_correction 修正建议")
suggestions = r.suggest_correction(
    answer="中国移动净利润3000亿元",
    sources=[{"text": "净利润1,384亿元"}],
)
for s in suggestions:
    print("  %s" % s[:80])

print("\n9. 管道回归 + 模块导入验证")
from tools import ToolRegistry
from tools.retrieve_tool import RetrieveTool
from tools.calculator_tool import CalculatorTool
from tools.compare_tool import CompareTool
from tools.chart_tool import ChartTool
from tools.verify_tool import VerifyTool
registry = ToolRegistry()
registry.register(RetrieveTool())
registry.register(CalculatorTool())
registry.register(CompareTool())
registry.register(ChartTool())
registry.register(VerifyTool())
print("  5工具 + reflector 模块共存正常")

print("\n10. 阈值边界测试（0.05 边界）")
print("-" * 40)

# 以 1000 为基准，精确计算边界值
BASE = 1000.0
MARGIN_049 = 1049.0  # 误差 = 49/1000 = 0.049
MARGIN_050 = 1050.0  # 误差 = 50/1000 = 0.050
MARGIN_051 = 1051.0  # 误差 = 51/1000 = 0.051

# 10.1 边界内（0.049）
result = r.verify(
    answer="营收为%.2f亿元" % MARGIN_049,
    sources=[{"text": "营收%.2f亿元" % BASE}],
)
detail = result.details[0]
assert not detail["is_hallucination"], \
    "0.049 误差应判定为非幻觉，实际 best_distance=%.4f" % detail.get("best_distance", -1)
print("  [PASS] 0.049 边界内 → 非幻觉 (best_distance=%.4f)" % detail.get("best_distance", 0))

# 10.2 边界上（0.050）
result = r.verify(
    answer="营收为%.2f亿元" % MARGIN_050,
    sources=[{"text": "营收%.2f亿元" % BASE}],
)
detail = result.details[0]
assert not detail["is_hallucination"], \
    "0.050 边界上应判定为非幻觉，实际 best_distance=%.4f" % detail.get("best_distance", -1)
print("  [PASS] 0.050 边界上 → 非幻觉 (best_distance=%.4f)" % detail.get("best_distance", 0))

# 10.3 边界外（0.051）
result = r.verify(
    answer="营收为%.2f亿元" % MARGIN_051,
    sources=[{"text": "营收%.2f亿元" % BASE}],
)
detail = result.details[0]
assert detail["is_hallucination"], \
    "0.051 误差应判定为幻觉，实际 best_distance=%.4f" % detail.get("best_distance", -1)
print("  [PASS] 0.051 边界外 → 幻觉 (best_distance=%.4f)" % detail.get("best_distance", 0))

# 10.4 单位换算（千元 vs 亿元）
result = r.verify(
    answer="营收为1250.38亿元",
    sources=[{"text": "营业收入125038000千元"}],
)
detail = result.details[0]
assert not detail["is_hallucination"], \
    "单位换算应通过，实际 best_distance=%.4f" % detail.get("best_distance", -1)
print("  [PASS] 125038000千元 vs 1250.38亿元 → 非幻觉 (best_distance=%.4f)" % detail.get("best_distance", 0))

# 10.5 跨数量级幻觉（10倍）
result = r.verify(
    answer="营收为12503.8亿元",
    sources=[{"text": "营业收入1250.38亿元"}],
)
detail = result.details[0]
assert detail["is_hallucination"], \
    "10倍误差应判定为幻觉，实际 best_distance=%.4f" % detail.get("best_distance", -1)
print("  [PASS] 12503.8 vs 1250.38（10倍）→ 幻觉 (best_distance=%.4f)" % detail.get("best_distance", 0))

print("-" * 40)
print("  5/5 边界测试全部通过")

print("\n全部验证完成")
