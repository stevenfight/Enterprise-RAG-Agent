# -*- coding: utf-8 -*-
"""calculator_tool 快速验证"""

import sys
sys.path.insert(0, "src")

from tools.calculator_tool import CalculatorTool

c = CalculatorTool()

print("=" * 50)
print("1. 同比增长率 (yoy_growth)")
r = c.run(operation="yoy_growth", current=89.7, previous=63.2)
print("  success=%s" % r.success)
if r.success:
    print("  " + r.data["calculation"].replace("\n", "\n  "))
else:
    print("  错误: %s" % r.error)

print("\n2. 复合年增长率 (cagr)")
r = c.run(operation="cagr", start_value=53.4, end_value=89.7, years=3)
print("  success=%s" % r.success)
if r.success:
    print("  " + r.data["calculation"].replace("\n", "\n  "))
else:
    print("  错误: %s" % r.error)

print("\n3. 利润率 (margin)")
r = c.run(operation="margin", numerator=7.3, denominator=89.7, margin_type="净利率")
print("  success=%s" % r.success)
if r.success:
    print("  " + r.data["calculation"].replace("\n", "\n  "))
else:
    print("  错误: %s" % r.error)

print("\n4. 增减百分比 (pct_change)")
r = c.run(operation="pct_change", new_value=1250, old_value=1200, label="营收")
print("  success=%s" % r.success)
if r.success:
    print("  " + r.data["calculation"].replace("\n", "\n  "))
else:
    print("  错误: %s" % r.error)

print("\n5. 错误: 不支持的操作")
r = c.run(operation="invalid_op")
print("  success=%s, error=%s" % (r.success, r.error[:50]))

print("\n6. 错误: 缺少参数")
r = c.run(operation="yoy_growth", current=100)
print("  success=%s, error=%s" % (r.success, r.error[:60]))

print("\n7. 错误: 分母为零")
r = c.run(operation="yoy_growth", current=100, previous=0)
print("  success=%s, error=%s" % (r.success, r.error[:40]))

print("\n8. 组合测试: 中芯国际营收增速")
r = c.run(operation="yoy_growth", current=578.21, previous=492.17)
print("  success=%s" % r.success)
if r.success:
    print("  " + r.data["calculation"].replace("\n", "\n  "))

print("\n" + "=" * 50)
print("全部验证完成")
