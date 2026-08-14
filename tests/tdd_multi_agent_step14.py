# -*- coding: utf-8 -*-
"""
TDD 测试: 多 Agent 升级 - 阶段十四 数据来源页码映射修复

对应 TDD 规格: openspec/changes/multi-agent-step14/specs/tdd-step14.md
测试总计: 4 项
  - SP14-A build_line_page_map 路径修复: 3 项
  - SP14-B line_to_page 页码单调性: 1 项

编码: UTF-8
"""

import sys
import unittest
from pathlib import Path

# 将项目根目录加入 sys.path，使直接运行本脚本时 `import src` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 测试数据路径（本地真实数据）
_PDF_PATH = PROJECT_ROOT / "data" / "stock_data" / "pdf_reports" / "电信2024年度报告.pdf"
_MD_PATH = PROJECT_ROOT / "data" / "stock_data" / "debug_data" / "03_reports_markdown" / "电信2024年度报告.md"
_LAST_PAGE = 218


def _load_line_to_page():
    """加载 line_to_page 闭包与 markdown 行列表；数据缺失时返回 (None, None)"""
    if not _PDF_PATH.exists() or not _MD_PATH.exists():
        return None, None
    from src.text_splitter import build_line_page_map
    line_to_page = build_line_page_map(str(_PDF_PATH))
    lines = _MD_PATH.read_text(encoding="utf-8").splitlines()
    return line_to_page, lines


# ============================================================
# SP14-A: build_line_page_map 路径修复（3 项）
# ============================================================


class TestBuildLinePageMapFix(unittest.TestCase):
    """TC-14-A: 修复 md 路径后 line_to_page 不再恒返回最后一页"""

    @classmethod
    def setUpClass(cls):
        line_to_page, lines = _load_line_to_page()
        cls._line_to_page = staticmethod(line_to_page)
        cls._lines = lines

    def _require_data(self):
        if self._line_to_page is None:
            self.skipTest("缺少本地测试数据（PDF/markdown）")

    def test_a01_not_always_last_page(self):
        self._require_data()
        total = len(self._lines)
        # 排除首行：首行 char_offset=0，在 bug 下也会正确映射到第 1 页，无法暴露缺陷
        sample_lines = [total // 4, total // 2, total * 3 // 4]
        pages = [self._line_to_page(ln, self._lines) for ln in sample_lines]
        self.assertFalse(
            all(p == _LAST_PAGE for p in pages),
            "修复后页码不应全部等于最后一页 %d，实际: %s" % (_LAST_PAGE, pages),
        )

    def test_a02_first_line_maps_first_page(self):
        self._require_data()
        first = self._line_to_page(1, self._lines)
        self.assertEqual(first, 1, "首行 char_offset=0 应映射到第 1 页，实际: %s" % first)

    def test_a03_last_line_near_last_page(self):
        self._require_data()
        total = len(self._lines)
        last = self._line_to_page(total, self._lines)
        self.assertGreaterEqual(last, _LAST_PAGE - 5, "末行应接近最后一页，实际: %s" % last)
        self.assertLessEqual(last, _LAST_PAGE, "末行页码不应超过总页数，实际: %s" % last)


# ============================================================
# SP14-B: line_to_page 页码单调性（1 项）
# ============================================================


class TestLineToPageMonotonic(unittest.TestCase):
    """TC-14-B: 行号递增时页码单调不减"""

    @classmethod
    def setUpClass(cls):
        line_to_page, lines = _load_line_to_page()
        cls._line_to_page = staticmethod(line_to_page)
        cls._lines = lines

    def test_b01_monotonic_non_decreasing(self):
        if self._line_to_page is None:
            self.skipTest("缺少本地测试数据（PDF/markdown）")
        total = len(self._lines)
        sample_lines = [1, total // 4, total // 2, total * 3 // 4, total]
        pages = [self._line_to_page(ln, self._lines) for ln in sample_lines]
        self.assertEqual(
            pages,
            sorted(pages),
            "页码应随行号单调不减，实际: %s" % pages,
        )


if __name__ == "__main__":
    unittest.main()
