"""回答级证据摘要回归测试。"""

import unittest
from unittest.mock import MagicMock

from src.retrieval import ENCODING, RAGGenerator


class TestSourceExcerpt(unittest.TestCase):
    def test_excerpt_is_limited_normalized_and_redacted(self):
        generator = RAGGenerator("data/stock_data/databases/vector_dbs")
        source = generator._build_sources_summary([{
            "source_file": "移动2024年度报告.pdf",
            "pages": [17],
            "company_name": "中国移动",
            "parent_text": "营业收入 1,040,759 百万元。\napi_key=sk-secret-value " + "数据" * 300,
            "scores": {"hybrid": 0.9, "rerank": 8.0},
        }])[0]

        self.assertLessEqual(len(source["excerpt"]), 240)
        self.assertIn("营业收入 1,040,759 百万元。", source["excerpt"])
        self.assertNotIn("sk-secret-value", source["excerpt"])
        self.assertNotIn("\n", source["excerpt"])

    def test_context_reports_only_the_results_used_for_answer(self):
        generator = RAGGenerator("data/stock_data/databases/vector_dbs")
        generator.MAX_CONTEXT_TOKENS = 300
        results = [
            {
                "source_file": "来源一.pdf",
                "pages": [1],
                "company_name": "中国移动",
                "parent_text": "甲" * 400,
                "scores": {},
            },
            {
                "source_file": "来源二.pdf",
                "pages": [2],
                "company_name": "中国移动",
                "parent_text": "乙" * 400,
                "scores": {},
            },
        ]

        _, used_count, used_indices, used_texts = generator._build_context(results)

        self.assertEqual(used_count, 1)
        self.assertEqual(used_indices, {0})
        expected_text = ENCODING.decode(ENCODING.encode("甲" * 400)[:300])
        self.assertEqual(used_texts[0], expected_text)

    def test_excerpt_never_contains_text_after_context_truncation(self):
        generator = RAGGenerator("data/stock_data/databases/vector_dbs")
        generator.MAX_CONTEXT_TOKENS = 450
        retriever = MagicMock()
        retriever.search.return_value = [
            {
                "source_file": "来源一.pdf",
                "pages": [1],
                "company_name": "中国移动",
                "parent_text": "甲" * 80,
                "scores": {},
            },
            {
                "source_file": "来源二.pdf",
                "pages": [2],
                "company_name": "中国电信",
                "parent_text": "乙" * 220 + "未进入模型的尾部文本" + "丙" * 100,
                "scores": {},
            },
        ]
        generator._get_retriever = MagicMock(return_value=retriever)
        generator._generate_answer = MagicMock(return_value="测试回答")

        result = generator.query("测试问题")

        self.assertEqual(len(result["sources"]), 2)
        self.assertNotIn("未进入模型的尾部文本", result["sources"][1]["excerpt"])

    def test_sources_keep_original_context_indexes_after_filtering(self):
        generator = RAGGenerator("data/stock_data/databases/vector_dbs")
        generator.MAX_CONTEXT_TOKENS = 450
        retriever = MagicMock()
        retriever.search.return_value = [
            {
                "source_file": "移动.pdf",
                "pages": [1],
                "company_name": "中国移动",
                "parent_text": "甲" * 80,
                "scores": {},
            },
            {
                "source_file": "移动补充.pdf",
                "pages": [2],
                "company_name": "中国移动",
                "parent_text": "乙" * 400,
                "scores": {},
            },
            {
                "source_file": "电信.pdf",
                "pages": [3],
                "company_name": "中国电信",
                "parent_text": "丙" * 400,
                "scores": {},
            },
        ]
        generator._get_retriever = MagicMock(return_value=retriever)
        generator._generate_answer = MagicMock(return_value="[来源1] 与 [来源3]")

        result = generator.query("比较问题")

        self.assertEqual([source["index"] for source in result["sources"]], [1, 3])

    def test_supported_question_attaches_only_registered_comparison(self):
        generator = RAGGenerator("data/stock_data/databases/vector_dbs")
        retriever = MagicMock()
        retriever.search.return_value = [{
            "source_file": "移动2024年度报告.pdf",
            "pages": [3],
            "company_name": "中国移动",
            "parent_text": "2024 年，营业收入达到人民币 10,408 亿元。",
            "scores": {},
        }]
        generator._get_retriever = MagicMock(return_value=retriever)
        generator._generate_answer = MagicMock(return_value="测试回答")

        result = generator.query("对比三大运营商2024年的营业收入")

        self.assertEqual(result["comparison"]["items"][0]["value"], 10408)
        self.assertEqual(result["comparison"]["items"][0]["source_file"], "移动2024年度报告.pdf")


if __name__ == "__main__":
    unittest.main()
