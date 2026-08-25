"""图表工件金额单位回归测试。"""

import json
import unittest
from pathlib import Path


class TestChartUnitConversion(unittest.TestCase):
    def test_latest_operator_revenue_table_uses_hundred_million_yuan(self):
        chart_path = Path("data/charts/table_对比三大运营商2024年的营业收入_1787643173312.json")
        chart = json.loads(chart_path.read_text(encoding="utf-8"))
        mobile_row = next(row for row in chart["rows"] if row[0] == "中国移动")

        self.assertEqual(mobile_row[1], "10,408")


if __name__ == "__main__":
    unittest.main()
