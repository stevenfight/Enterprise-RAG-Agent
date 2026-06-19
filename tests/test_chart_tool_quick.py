# -*- coding: utf-8 -*-
"""chart_tool 快速验证"""

import sys
sys.path.insert(0, "src")

from tools.chart_tool import ChartTool

c = ChartTool()

print("=" * 60)
print("1. 柱状图: 三公司营收对比")
print("=" * 60)
r = c.run(
    data={"中国移动": 12500, "中国联通": 9930, "中国电信": 11000},
    chart_type="bar",
    title="2024年营收对比(亿元)",
    xlabel="公司",
    ylabel="营收(亿元)",
)
if r.success:
    print("  成功: %s (%.1f KB)" % (r.data["file_name"], r.data["file_size_kb"]))
else:
    print("  失败: %s" % r.error)

print("\n2. 横向柱状图: 研发费用对比")
r = c.run(
    data={"中芯国际": 89.53, "中国移动": 218.0, "中国联通": 98.5, "中国电信": 135.0},
    chart_type="hbar",
    title="研发费用对比(亿元)",
)
if r.success:
    print("  成功: %s (%.1f KB)" % (r.data["file_name"], r.data["file_size_kb"]))
else:
    print("  失败: %s" % r.error)

print("\n3. 折线图: 中芯国际营收趋势")
r = c.run(
    data={"2021": 356.0, "2022": 495.0, "2023": 492.0, "2024": 578.0},
    chart_type="line",
    title="中芯国际营收趋势(亿元)",
    ylabel="营收(亿元)",
)
if r.success:
    print("  成功: %s (%.1f KB)" % (r.data["file_name"], r.data["file_size_kb"]))
else:
    print("  失败: %s" % r.error)

print("\n4. 饼图: 收入结构")
r = c.run(
    data={"通信服务": 65.0, "移动业务": 20.0, "固网业务": 10.0, "其他": 5.0},
    chart_type="pie",
    title="中国移动收入结构",
)
if r.success:
    print("  成功: %s (%.1f KB)" % (r.data["file_name"], r.data["file_size_kb"]))
else:
    print("  失败: %s" % r.error)

print("\n5. 错误: 空数据")
r = c.run(data={}, chart_type="bar", title="测试")
print("  success=%s, error=%s" % (r.success, r.error[:50] if r.error else ""))

print("\n6. 错误: 不支持的类型")
r = c.run(data={"a": 1}, chart_type="scatter", title="测试")
print("  success=%s, error=%s" % (r.success, r.error[:50] if r.error else ""))

print("\n7. 四工具共存验证")
from tools import ToolRegistry
from tools.retrieve_tool import RetrieveTool
from tools.calculator_tool import CalculatorTool
from tools.compare_tool import CompareTool
registry = ToolRegistry()
registry.register(RetrieveTool())
registry.register(CalculatorTool())
registry.register(CompareTool())
registry.register(c)
print("  工具列表: %s" % registry.list_all())

print("\n全部验证完成")
