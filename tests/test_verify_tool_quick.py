# -*- coding: utf-8 -*-
"""verify_tool 快速验证"""

import sys
sys.path.insert(0, "src")

from tools.verify_tool import VerifyTool

v = VerifyTool()

print("=" * 60)
print("1. 数据匹配: 正常验证")
print("=" * 60)
r = v.run(
    claim="中芯国际2024年营收为578.21亿元",
    source_text="2024年度公司实现营业收入578.21亿元，同比增长17.5%。",
    claim_label="营收",
)
print("  valid=%s, confidence=%.2f" % (r.data["valid"], r.data["confidence"]))
print("  message: %s" % r.data["message"])
for d in r.data["match_details"]:
    print("  %s → %s" % ("匹配" if d["matched"] else "不匹配", d["detail"][:80]))

print("\n2. 数据不匹配: 幻觉检测")
r = v.run(
    claim="中国移动2024年净利润为2000亿元",
    source_text="2024年归属于母公司股东的净利润为1,384亿元。",
    claim_label="净利润",
)
print("  valid=%s, confidence=%.2f" % (r.data["valid"], r.data["confidence"]))
print("  message: %s" % r.data["message"])

print("\n3. 多重数值匹配")
r = v.run(
    claim="中国联通2024年营收389.89亿元，净利润90.3亿元",
    source_text="2024年营业收入389.89亿元，同比增长4.6%。归属于母公司股东的净利润90.30亿元。",
)
print("  valid=%s, confidence=%.2f, matched=%d/%d" % (
    r.data["valid"], r.data["confidence"], r.data["matched_count"], r.data["total_claims"]))
for d in r.data["match_details"]:
    print("  %s → rel_err=%s" % ("匹配" if d["matched"] else "不匹配", d["relative_error"]))

print("\n4. 来源不足")
r = v.run(claim="中芯国际营收578亿", source_text="   ")
print("  valid=%s, confidence=%.2f" % (r.data["valid"], r.data["confidence"]))

print("\n5. 来源无数字")
r = v.run(claim="营收578亿", source_text="公司经营情况良好，持续稳健发展。")
print("  valid=%s, confidence=%.2f" % (r.data["valid"], r.data["confidence"]))

print("\n6. claim 无数字 (定性陈述)")
r = v.run(claim="公司经营状况良好", source_text="2024年营收578亿")
print("  valid=%s, confidence=%.2f" % (r.data["valid"], r.data["confidence"]))

print("\n7. 单位不一致但匹配")
r = v.run(
    claim="营收1250万",
    source_text="营业收入为0.125亿",
    claim_label="营收",
)
print("  valid=%s, confidence=%.2f" % (r.data["valid"], r.data["confidence"]))

print("\n8. 部分匹配 (2/3)")
r = v.run(
    claim="中芯国际营收578亿，净利润120亿，总资产2000亿",
    source_text="2024年营收578.21亿元，净利润36.99亿元",
)
print("  valid=%s, confidence=%.2f, matched=%d/%d" % (
    r.data["valid"], r.data["confidence"], r.data["matched_count"], r.data["total_claims"]))

print("\n9. 五工具共存")
from tools import ToolRegistry
from tools.retrieve_tool import RetrieveTool
from tools.calculator_tool import CalculatorTool
from tools.compare_tool import CompareTool
from tools.chart_tool import ChartTool
registry = ToolRegistry()
registry.register(RetrieveTool())
registry.register(CalculatorTool())
registry.register(CompareTool())
registry.register(ChartTool())
registry.register(v)
print("  工具列表: %s" % registry.list_all())

print("\n全部验证完成")
