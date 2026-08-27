# -*- coding: utf-8 -*-
"""图表工具对 Agent 的公开图片地址契约测试。"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")

from tools.chart_tool import ChartTool


class TestChartPublicImageReference(unittest.TestCase):
    """确保 Agent 不会取得浏览器不可访问的本地文件路径。"""

    def test_chart_result_exposes_canonical_public_markdown_only(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            tool = ChartTool()
            tool._output_dir = Path(temporary_directory)

            result = tool.run(
                data={"中国移动": 10408, "中国联通": 3896, "中国电信": 5235.7},
                chart_type="bar",
                title="2024年三大运营商营业收入对比",
                xlabel="公司",
                ylabel="营业收入（亿元）",
            )

        self.assertTrue(result.success, result.error)
        self.assertTrue(result.data["url"].startswith("/api/charts/images/"))
        self.assertEqual(
            result.data["markdown_image"],
            "![2024年三大运营商营业收入对比](%s)" % result.data["url"],
        )
        self.assertNotIn("file_path", result.data)
        self.assertNotIn("relative_path", result.data)


if __name__ == "__main__":
    unittest.main()
