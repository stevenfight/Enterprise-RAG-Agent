# -*- coding: utf-8 -*-
"""
TDD 测试: Planner 运营商别名识别（三大运营商）

对应 TDD: openspec/changes/planner-operator-alias-recognition/specs/tdd-planner-alias.md
涵盖: AL-01 ~ AL-05

运行方式: python tests/tdd_planner_alias.py
"""

import sys
import unittest
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.planner import TaskPlanner  # noqa: E402

# 期望的三家运营商（保持固定顺序）
THREE_OPERATORS = ["中国移动", "中国联通", "中国电信"]


class TestPlannerOperatorAlias(unittest.TestCase):
    """三大运营商别名识别测试"""

    def setUp(self):
        self.planner = TaskPlanner()

    def test_al01_alias_expand_three_operators(self):
        """AL-01: 别名「三大运营商」展开为三家"""
        plan = self.planner.plan("对比三大运营商2024年的营业收入")
        self.assertEqual(plan.category.company_names, THREE_OPERATORS)

    def test_al02_alias_category_multi_compare(self):
        """AL-02: 别名查询分类为 multi_compare"""
        plan = self.planner.plan("对比三大运营商2024年的营业收入")
        self.assertEqual(plan.category.category, "multi_compare")

    def test_al03_compare_task_carries_companies(self):
        """AL-03: compare 子任务携带完整公司列表"""
        plan = self.planner.plan("对比三大运营商2024年的营业收入")
        compare_tasks = [st for st in plan.subtasks if st.task_type.value == "compare"]
        self.assertEqual(len(compare_tasks), 1)
        self.assertEqual(compare_tasks[0].tool_params["companies"], THREE_OPERATORS)

    def test_al04_explicit_companies_unchanged(self):
        """AL-04: 精确公司名查询不受影响"""
        plan = self.planner.plan("中国移动和中国联通2024年营收对比")
        self.assertEqual(plan.category.company_names, ["中国移动", "中国联通"])

    def test_al05_vague_query_companies_empty(self):
        """AL-05: 模糊查询公司仍为空"""
        plan = self.planner.plan("2024年营收增长了么")
        self.assertEqual(plan.category.company_names, [])

    def test_al06_chart_calc_multi_compare_full(self):
        """AL-06: 多公司+涨幅+图表 → multi_compare 且包含完整子任务链"""
        plan = self.planner.plan("三大运营商2024年营收分别是多少，涨幅是多少，使用图表展示")
        self.assertEqual(plan.category.category, "multi_compare")
        self.assertEqual(plan.category.company_names, THREE_OPERATORS)
        tool_names = [st.tool_name for st in plan.subtasks]
        self.assertEqual(tool_names, ["retrieve", "compare", "calculator", "chart", "verify"])

    def test_al07_calc_task_params(self):
        """AL-07: 涨幅计算子任务携带 calculator 与 yoy_growth"""
        plan = self.planner.plan("三大运营商2024年营收分别是多少，涨幅是多少，使用图表展示")
        calc_task = next(st for st in plan.subtasks if st.tool_name == "calculator")
        self.assertEqual(calc_task.task_type.value, "calculate")
        self.assertEqual(calc_task.tool_params["operation"], "yoy_growth")
        self.assertIn(calc_task.tool_params.get("current"), [0, None])

    def test_al08_chart_task_params(self):
        """AL-08: 图表子任务携带 chart 与 bar 类型"""
        plan = self.planner.plan("三大运营商2024年营收分别是多少，涨幅是多少，使用图表展示")
        chart_task = next(st for st in plan.subtasks if st.tool_name == "chart")
        self.assertEqual(chart_task.task_type.value, "chart")
        self.assertEqual(chart_task.tool_params["chart_type"], "bar")

    def test_al09_plain_compare_unchanged(self):
        """AL-09: 无涨幅无图表的对比查询仍为 retrieve+compare+verify (不回归)"""
        plan = self.planner.plan("对比三大运营商2024年的营业收入")
        tool_names = [st.tool_name for st in plan.subtasks]
        self.assertEqual(tool_names, ["retrieve", "compare", "verify"])

    def test_al10_single_company_chart_keeps_trend(self):
        """AL-10: 单公司+趋势仍按趋势分类 (多公司优先不误伤)"""
        plan = self.planner.plan("中国移动2024年营收增长趋势图")
        self.assertEqual(plan.category.category, "trend")

    def test_al11_single_company_change_chart_trend(self):
        """AL-11: 单公司+变化+图表 → trend (连接词'及'不误判为对比)"""
        plan = self.planner.plan("中芯国际近几年主营业务及营收变化，图表展示")
        self.assertEqual(plan.category.category, "trend")
        tool_names = [st.tool_name for st in plan.subtasks]
        self.assertEqual(tool_names, ["retrieve", "calculator", "chart"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
