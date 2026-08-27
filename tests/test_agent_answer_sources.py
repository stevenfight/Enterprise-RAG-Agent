# -*- coding: utf-8 -*-
"""Agent 回答级证据契约测试。"""

import unittest

from src.api_service import _build_agent_answer_sources


class AgentAnswerSourcesTest(unittest.TestCase):
    """只允许实际检索结果成为 Agent 回答级证据。"""

    def test_normalizes_deduplicates_and_limits_retrieved_sources(self):
        sources = _build_agent_answer_sources([
            {
                "source": "移动2024年度报告.pdf",
                "pages": "P3, P4",
                "company_name": "中国移动",
                "content": "营业收入为10408亿元。" * 30,
            },
            {
                "source": "移动2024年度报告.pdf",
                "pages": [3, 4],
                "company_name": "中国移动",
                "content": "重复来源不应再次返回。",
            },
            {"content": "缺少文件名的原始内容不得成为证据。"},
        ])

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["index"], 1)
        self.assertEqual(sources[0]["source_file"], "移动2024年度报告.pdf")
        self.assertEqual(sources[0]["pages"], [3, 4])
        self.assertEqual(sources[0]["company_name"], "中国移动")
        self.assertEqual(sources[0]["scores"], {})
        self.assertLessEqual(len(sources[0]["excerpt"]), 240)

    def test_returns_empty_for_no_retrieved_sources(self):
        self.assertEqual(_build_agent_answer_sources([]), [])


if __name__ == "__main__":
    unittest.main()
