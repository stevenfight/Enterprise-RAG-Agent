# -*- coding: utf-8 -*-
"""
TDD 测试: 修复多公司检索 top_n 过小导致公司被顶掉

对应 TDD: openspec/changes/fix-retrieval-topn-coverage/specs/tdd-fix-retrieval-topn.md
涵盖: TC-01 ~ TC-06

运行方式: python tests/tdd_retrieval_topn_fix.py
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---- 关键：在 import src.retrieval 之前 mock tiktoken，避免 SSL 下载错误 ----
try:
    import tiktoken as _real_tiktoken
    _real_tiktoken.get_encoding("cl100k_base")
except Exception:
    _mock_tiktoken = MagicMock()
    _mock_encoding = MagicMock()
    _mock_encoding.encode = lambda text, *a, **kw: text.split()
    _mock_encoding.decode = lambda tokens, *a, **kw: " ".join(tokens) if isinstance(tokens, list) else str(tokens)
    _mock_tiktoken.get_encoding = MagicMock(return_value=_mock_encoding)
    sys.modules['tiktoken'] = _mock_tiktoken

# 待测函数（实现前为 None，测试将标红）
try:
    from src.retrieval import _adjust_top_n_for_companies
except ImportError:
    _adjust_top_n_for_companies = None


class TestTopNAdjustment(unittest.TestCase):
    """top_n 扩容逻辑测试"""

    def _call(self, top_n, companies):
        """调用待测函数，函数未实现时明确失败"""
        self.assertIsNotNone(
            _adjust_top_n_for_companies,
            "src.retrieval._adjust_top_n_for_companies 尚未实现",
        )
        return _adjust_top_n_for_companies(top_n, companies)

    def test_tc01_multi_company_small_topn(self):
        """TC-01: 多公司 + top_n 偏小 → 扩容到公司数"""
        companies = ["中国移动", "中国电信", "中国联通", "中芯国际"]
        self.assertEqual(self._call(3, companies), 4)

    def test_tc02_multi_company_enough_topn(self):
        """TC-02: 多公司 + top_n 充足 → 不变"""
        companies = ["中国移动", "中国电信", "中国联通"]
        self.assertEqual(self._call(5, companies), 5)

    def test_tc03_single_company(self):
        """TC-03: 单公司不扩容"""
        self.assertEqual(self._call(3, ["中国移动"]), 3)

    def test_tc04_empty_companies(self):
        """TC-04: 空公司列表不扩容"""
        self.assertEqual(self._call(3, []), 3)

    def test_tc05_topn_equals_company_count(self):
        """TC-05: top_n 等于公司数 → 不变"""
        companies = ["中国移动", "中国电信", "中国联通", "中芯国际"]
        self.assertEqual(self._call(4, companies), 4)

    def test_tc06_topn_one_multi_company(self):
        """TC-06: top_n=1 且多公司 → 扩容到公司数"""
        self.assertEqual(self._call(1, ["中国移动", "中国电信"]), 2)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestTopNAdjustment)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print("\n" + "=" * 60)
    print("TDD 测试总计: %d 项" % total)
    print("通过: %d 项" % passed)
    print("失败: %d 项" % len(result.failures))
    print("错误: %d 项" % len(result.errors))
    if result.wasSuccessful():
        print("所有测试通过!")
    else:
        print("存在未通过的测试，请检查上方输出。")
