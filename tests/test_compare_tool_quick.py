# -*- coding: utf-8 -*-
"""compare_tool 快速验证脚本"""

import sys
sys.path.insert(0, "src")

from tools.compare_tool import CompareTool

c = CompareTool()

print("=" * 60)
print("1. 三公司营收对比 (正常场景)")
print("=" * 60)
r = c.run(companies=["中国移动", "中国联通", "中国电信"], metric="营收", year="2024", top_n=3)
if r.success:
    print(r.data["table"])
    print("  覆盖率: %d/%d" % (r.data["companies_with_data"], r.data["companies_compared"]))
else:
    print("  失败: %s" % r.error)

print("\n" + "=" * 60)
print("2. 错误: 只有一家公司")
print("=" * 60)
r = c.run(companies=["中芯国际"], metric="营收", year="2024")
print("  success=%s, error=%s" % (r.success, r.error[:60] if r.error else "无"))

print("\n" + "=" * 60)
print("3. 错误: 所有公司都无效")
print("=" * 60)
r = c.run(companies=["特斯拉", "苹果"], metric="营收", year="2024")
print("  success=%s, error=%s" % (r.success, r.error[:80] if r.error else "无"))

print("\n" + "=" * 60)
print("4. 错误: 缺少指标参数")
print("=" * 60)
r = c.run(companies=["中国移动", "中国联通"])
print("  success=%s, error=%s" % (r.success, r.error[:60] if r.error else "无"))

print("\n" + "=" * 60)
print("5. 指定中芯国际 + 中国移动 对比 (含保底测试)")
print("=" * 60)
r = c.run(companies=["中芯国际", "中国移动"], metric="净利润", year="2024", top_n=3)
if r.success:
    print(r.data["table"])
    print("  覆盖率: %d/%d" % (r.data["companies_with_data"], r.data["companies_compared"]))
else:
    print("  失败: %s" % r.error)

print("\n" + "=" * 60)
print("6. 工具注册兼容性测试")
print("=" * 60)
from tools import ToolRegistry
registry = ToolRegistry()
try:
    from tools.retrieve_tool import RetrieveTool
    from tools.calculator_tool import CalculatorTool
    registry.register(RetrieveTool())
    registry.register(CalculatorTool())
    registry.register(c)
    print("  三工具共存: %s" % registry.list_all())
except Exception as e:
    print("  失败: %s" % e)

print("\n全部验证完成")
