"""RAG 提示词的财务金额单位换算回归测试。"""

import unittest

from src.retrieval import RAGGenerator


class TestRAGPromptUnitConversion(unittest.TestCase):
    """确保普通 RAG 不会将人民币百万元误按千元处理。"""

    def setUp(self):
        self.generator = RAGGenerator("data/stock_data/databases/vector_dbs")

    def test_prompts_require_reading_the_source_unit_before_conversion(self):
        """不同年报单位混用时，提示词必须给出完整换算规则。"""
        prompts = [
            self.generator._build_prompt("测试", "上下文"),
            self.generator._build_comparison_prompt("测试", "上下文"),
            self.generator._build_financial_data_prompt("测试", "上下文"),
        ]

        for prompt in prompts:
            self.assertIn("百万元 → 亿元：数值 ÷ 100", prompt)
            self.assertIn("1,040,759百万元 = 10,407.59亿元", prompt)
            self.assertNotIn("财务数据原始单位为「千元」", prompt)


if __name__ == "__main__":
    unittest.main()
