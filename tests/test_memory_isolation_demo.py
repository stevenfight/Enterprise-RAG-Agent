# -*- coding: utf-8 -*-
"""验证 AgentMemory 会话隔离效果"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import unittest
from agent_memory import AgentMemory


class TestAgentMemoryIsolation(unittest.TestCase):
    """验证：两个独立 AgentMemory 实例之间数据不交叉污染"""

    def setUp(self):
        self.mem_a = AgentMemory(working_memory_limit=10, episodic_memory_turns=3)
        self.mem_b = AgentMemory(working_memory_limit=10, episodic_memory_turns=3)

    def test_working_memory_isolated(self):
        """TC-01: 工作记忆隔离 — 会话A写入不会出现在会话B"""
        self.mem_a.add("检索中芯国际营收", "retrieve",
                       {"query": "中芯国际营收"}, "中芯国际营收577.96亿元", elapsed_ms=120)
        self.mem_a.add("数据齐全", "Final Answer", None, "中芯国际营收577.96亿元", elapsed_ms=80)

        self.assertEqual(len(self.mem_a.working_memory), 2, "会话A应有2步")
        self.assertEqual(len(self.mem_b.working_memory), 0, "会话B不应被污染")

    def test_episodic_memory_isolated(self):
        """TC-02: 情景记忆隔离 — 摘要不会混入其他会话"""
        self.mem_a.add("检索中芯国际", "retrieve", {}, "中芯国际营收577.96亿元")
        self.mem_a.add("完成", "Final Answer", None, "中芯国际营收577.96亿元")
        self.mem_a.summarize_to_episodic("中芯国际营收", "中芯国际营收577.96亿元")

        self.mem_b.add("检索中国移动", "retrieve", {}, "中国移动营收9373亿元")
        self.mem_b.add("完成", "Final Answer", None, "中国移动营收9373亿元")
        self.mem_b.summarize_to_episodic("中国移动营收", "中国移动营收9373亿元")

        ep_a = self.mem_a.get_episodic_context(max_turns=3)
        ep_b = self.mem_b.get_episodic_context(max_turns=3)

        self.assertIn("中芯国际", ep_a)
        self.assertNotIn("中国移动", ep_a)   # 关键断言：A 里没有 B 的数据
        self.assertIn("中国移动", ep_b)
        self.assertNotIn("中芯国际", ep_b)   # 关键断言：B 里没有 A 的数据

    def test_reset_not_cross_contaminate(self):
        """TC-03: reset_working 隔离 — 清空操作不影响其他会话"""
        self.mem_a.add("检索中芯国际", "retrieve", {}, "中芯国际营收577.96亿元")
        self.mem_b.add("检索中国移动", "retrieve", {}, "中国移动营收9373亿元")

        self.mem_a.reset_working()

        self.assertEqual(len(self.mem_a.working_memory), 0)
        self.assertEqual(len(self.mem_b.working_memory), 1, "会话B不应被reset")


if __name__ == "__main__":
    unittest.main(verbosity=2)
