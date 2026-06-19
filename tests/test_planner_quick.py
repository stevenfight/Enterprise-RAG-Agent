# -*- coding: utf-8 -*-
"""planner 快速验证"""

import sys
sys.path.insert(0, "src")

from planner import TaskPlanner

p = TaskPlanner()

print("=" * 60)
print("1. 单公司单指标 → 不拆解 (retrieve → verify)")
print("=" * 60)
plan = p.plan("中芯国际2024年营收是多少")
print("  category=%s" % plan.category.category)
print("  subtasks=%d" % len(plan.subtasks))
for st in plan.subtasks:
    print("    %s: type=%s, tool=%s, deps=%s" % (st.task_id, st.task_type.value, st.tool_name, st.depends_on))
print("  execution_order: %s" % plan.execution_order)

print("\n2. 多公司对比 → compare_tool (内部检索) → verify")
plan = p.plan("中国移动和中国联通2024年营收对比")
print("  category=%s" % plan.category.category)
print("  companies=%s" % plan.category.company_names)
print("  subtasks: %d" % len(plan.subtasks))
for st in plan.subtasks:
    print("    %s: type=%s, tool=%s, deps=%s" % (st.task_id, st.task_type.value, st.tool_name, st.depends_on))
print("  execution_order: %s" % plan.execution_order)

print("\n3. 趋势分析 → retrieve → calculate → chart")
plan = p.plan("中芯国际近几年的营收增长趋势")
print("  category=%s" % plan.category.category)
print("  need_chart=%s, need_calculate=%s" % (plan.category.need_chart, plan.category.need_calculate))
for st in plan.subtasks:
    print("    %s: type=%s, tool=%s, deps=%s" % (st.task_id, st.task_type.value, st.tool_name, st.depends_on))
print("  execution_order: %s" % plan.execution_order)

print("\n4. 复合计算 → retrieve → calculate")
plan = p.plan("中芯国际毛利率同比增长率")
print("  category=%s" % plan.category.category)
for st in plan.subtasks:
    print("    %s: type=%s, tool=%s, deps=%s" % (st.task_id, st.task_type.value, st.tool_name, st.depends_on))
print("  execution_order: %s" % plan.execution_order)

print("\n5. decompose() 便捷方法")
subs = p.decompose("中国移动和中国联通2024年营收对比")
print("  拆解为 %d 个: %s" % (len(subs), [s["task_id"] for s in subs]))

print("\n6. build_dag() 执行顺序")
order = p.build_dag(subs)
print("  执行批次: %s" % order)

print("\n7. 三公司对比 (全部公司)")
plan = p.plan("中国移动、中国联通、中国电信2024年净利润对比")
print("  category=%s" % plan.category.category)
print("  companies=%s" % plan.category.company_names)
for st in plan.subtasks:
    print("    %s: type=%s, tool=%s, deps=%s" % (st.task_id, st.task_type.value, st.tool_name, st.depends_on))

print("\n8. 无公司名模糊查询")
plan = p.plan("2024年营收增长了么")
print("  category=%s" % plan.category.category)
print("  companies=%s, metrics=%s" % (plan.category.company_names, plan.category.metric_names))

print("\n9. 模块共存验证")
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
print("  5工具 + planner 模块共存正常")

print("\n全部验证完成")
