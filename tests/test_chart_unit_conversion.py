"""图表工件金额单位回归测试。"""

import unittest

from src.verified_financial_facts import VerifiedFinancialFactRegistry


class TestChartUnitConversion(unittest.TestCase):
    def test_latest_operator_revenue_table_uses_hundred_million_yuan(self):
        chart = {
            "chart_type": "table",
            "title": "对比三大运营商2024年的营业收入",
            "labels": ["中国移动", "中国联通", "中国电信"],
            "rows": [["中国移动", "104.08", "P3"]],
        }

        projected_chart = VerifiedFinancialFactRegistry().project_chart_artifact(chart)
        mobile_row = next(row for row in projected_chart["rows"] if row[0] == "中国移动")

        self.assertEqual(mobile_row[1], "10,408")


if __name__ == "__main__":
    unittest.main()
