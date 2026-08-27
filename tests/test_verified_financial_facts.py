"""受限财务事实注册表契约测试。"""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.api_service import api_charts_list, api_verified_comparison
from src.verified_financial_facts import VerifiedFinancialFactRegistry


class TestVerifiedFinancialFactRegistry(unittest.TestCase):
    def test_returns_verified_operator_revenue_with_item_sources(self):
        registry = VerifiedFinancialFactRegistry()

        comparison = registry.get_comparison(
            metric_key="operating_revenue",
            fiscal_year=2024,
            companies=["中国移动", "中国联通", "中国电信"],
        )

        self.assertTrue(comparison["available"])
        self.assertEqual(comparison["unit"], "亿元")
        self.assertEqual(
            {item["company_name"]: item["value"] for item in comparison["items"]},
            {"中国移动": 10408, "中国联通": 3896, "中国电信": 5236},
        )
        self.assertTrue(all(item["source_file"] and item["pages"] and item["excerpt"] for item in comparison["items"]))

    def test_does_not_return_workspace_for_unregistered_metric(self):
        registry = VerifiedFinancialFactRegistry()

        comparison = registry.get_comparison(
            metric_key="net_profit",
            fiscal_year=2024,
            companies=["中国移动", "中国联通", "中国电信"],
        )

        self.assertFalse(comparison["available"])
        self.assertEqual(comparison["items"], [])

    def test_comparison_api_only_returns_registered_facts(self):
        available = asyncio.run(api_verified_comparison("operating_revenue", 2024, "中国移动,中国联通,中国电信"))
        unavailable = asyncio.run(api_verified_comparison("net_profit", 2024, "中国移动,中国联通,中国电信"))

        self.assertTrue(available["available"])
        self.assertFalse(unavailable["available"])

    def test_only_supported_question_returns_answer_level_comparison(self):
        registry = VerifiedFinancialFactRegistry()

        comparison = registry.get_comparison_for_query("对比三大运营商2024年的营业收入")
        unsupported = registry.get_comparison_for_query("对比三大运营商2024年的净利润")

        self.assertTrue(comparison["available"])
        self.assertEqual(comparison["fact_ids"], [
            "operating-revenue-2024-中国移动",
            "operating-revenue-2024-中国联通",
            "operating-revenue-2024-中国电信",
        ])
        self.assertFalse(unsupported["available"])

    def test_registered_comparison_builds_a_unit_consistent_answer(self):
        registry = VerifiedFinancialFactRegistry()

        answer = registry.build_comparison_answer(
            registry.get_comparison_for_query("对比三大运营商2024年的营业收入")
        )

        self.assertIn("中国移动：10,408亿元", answer)
        self.assertIn("中国联通：3,896亿元", answer)
        self.assertIn("中国电信：5,236亿元", answer)
        self.assertNotIn("104.08亿元", answer)

    def test_chart_list_projects_registered_comparison_from_verified_facts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chart_dir = Path(temp_dir)
            (chart_dir / "chart_bar_2024年三大运营商营业收入对比.json").write_text(
                json.dumps({
                    "chart_type": "bar",
                    "title": "2024年三大运营商营业收入对比",
                    "xlabel": "公司",
                    "ylabel": "营业收入(亿元)",
                    "labels": ["中国移动", "中国电信", "中国联通"],
                    "values": [8500, 4200, 3000],
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            (chart_dir / "table_对比三大运营商2024年的营业收入.json").write_text(
                json.dumps({
                    "chart_type": "table",
                    "title": "对比三大运营商2024年的营业收入",
                    "columns": ["公司", "营收"],
                    "rows": [["中国移动", "104.08"], ["中国联通", "3896"], ["中国电信", "5235.7"]],
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            (chart_dir / "chart_bar_未登记问题.json").write_text(
                json.dumps({
                    "chart_type": "bar",
                    "title": "未登记问题",
                    "labels": ["甲", "乙"],
                    "values": [1, 2],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch("src.api_service._charts_dir", chart_dir):
                charts = asyncio.run(api_charts_list())["charts"]

        charts_by_title = {chart["title"]: chart for chart in charts}
        bar_chart = charts_by_title["2024年三大运营商营业收入对比"]
        table_chart = charts_by_title["对比三大运营商2024年的营业收入"]
        untouched_chart = charts_by_title["未登记问题"]

        self.assertEqual(bar_chart["labels"], ["中国移动", "中国联通", "中国电信"])
        self.assertEqual(bar_chart["values"], [10408, 3896, 5236])
        self.assertEqual(table_chart["rows"][0], ["中国移动", "10,408", "P3"])
        self.assertEqual(table_chart["rows"][2], ["中国电信", "5,236", "P10、P11"])
        self.assertEqual(untouched_chart["values"], [1, 2])


if __name__ == "__main__":
    unittest.main()
