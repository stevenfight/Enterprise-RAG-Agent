"""受限财务事实注册表契约测试。"""

import asyncio
import unittest

from src.api_service import api_verified_comparison
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


if __name__ == "__main__":
    unittest.main()
