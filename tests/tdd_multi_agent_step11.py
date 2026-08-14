# -*- coding: utf-8 -*-
"""
TDD 测试: 多 Agent 升级 - 阶段十一 回答来源标注具体页码

对应 TDD 规格: openspec/changes/multi-agent-step11/specs/tdd-step11.md
测试总计: 8 项
  - SP11-A 页码格式化回归 (RetrieveTool._format_results): 3 项
  - SP11-B prompt 页码标注规则静态断言: 5 项

编码: UTF-8
"""

import sys
import unittest
from pathlib import Path

# 将项目根目录加入 sys.path，使直接运行本脚本时 `import src` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_YAML_PATH = PROJECT_ROOT / "config" / "agent_prompts.yaml"


def _load_prompt_yaml():
    """读取 config/agent_prompts.yaml，返回解析后的字典"""
    import yaml

    with open(PROMPT_YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _make_retrieve_result(pages):
    """构造一条模拟的 HybridRetriever 检索结果"""
    return {
        "pages": pages,
        "company_name": "中国移动",
        "source_file": "中国移动2024年度报告.pdf",
        "parent_text": "营业收入 10,408 亿元",
        "scores": {"rerank": 8.5, "confidence": "high"},
    }


class TestPageNumberFormatting(unittest.TestCase):
    """SP11-A: 页码格式化回归"""

    def _format(self, pages):
        from src.tools.retrieve_tool import RetrieveTool

        tool = RetrieveTool()
        data = tool._format_results(
            [_make_retrieve_result(pages)], query="测试", company_name=None
        )
        return data["results"][0]["pages"]

    def test_a01_empty_pages(self):
        """TC-11-A-01: 空页码 → 页码未知"""
        self.assertEqual(self._format([]), "页码未知")

    def test_a02_single_page(self):
        """TC-11-A-02: 单页 → 第23页"""
        self.assertEqual(self._format([23]), "第23页")

    def test_a03_multiple_pages(self):
        """TC-11-A-03: 多页区间 → 第23-25页"""
        self.assertEqual(self._format([23, 24, 25]), "第23-25页")


class TestPromptPageRule(unittest.TestCase):
    """SP11-B: prompt 页码标注规则静态断言"""

    @classmethod
    def setUpClass(cls):
        cls._prompts = _load_prompt_yaml()

    def _assert_has_page(self, section):
        template = self._prompts.get(section, {}).get("template", "")
        self.assertIn(
            "页码",
            template,
            f"{section} 节 template 缺少「页码」标注规则",
        )

    def test_b01_default(self):
        self._assert_has_page("default")

    def test_b02_data_agent(self):
        self._assert_has_page("data_agent")

    def test_b03_compare_agent(self):
        self._assert_has_page("compare_agent")

    def test_b04_verify_agent(self):
        self._assert_has_page("verify_agent")

    def test_b05_orchestrator(self):
        self._assert_has_page("orchestrator")


if __name__ == "__main__":
    unittest.main()
