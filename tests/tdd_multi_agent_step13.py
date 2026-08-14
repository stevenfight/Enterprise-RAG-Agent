# -*- coding: utf-8 -*-
"""
TDD 测试: 多 Agent 升级 - 阶段十三 SSE 流式一致性优化

对应 TDD 规格: openspec/changes/multi-agent-step13/specs/tdd-step13.md
测试总计: 7 项
  - SP13-A _split_answer_chunks 拆句: 3 项
  - SP13-B 单 Agent 流式推 answer_chunk: 1 项
  - SP13-C DelegateTool 完成事件清理: 2 项
  - SP13-D 删除 workers_done (静态断言): 1 项

编码: UTF-8
"""

import asyncio
import json
import queue as std_queue
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# 将项目根目录加入 sys.path，使直接运行本脚本时 `import src` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============================================================
# SP13-A: _split_answer_chunks 拆句函数（3 项）
# ============================================================


class TestSplitAnswerChunks(unittest.TestCase):
    """TC-13-A: _split_answer_chunks 按句拆分的纯函数行为"""

    def _split(self, text):
        from src.api_service import _split_answer_chunks
        return _split_answer_chunks(text)

    def test_a01_empty_string(self):
        self.assertEqual(self._split(""), [])

    def test_a02_single_sentence_no_punct(self):
        self.assertEqual(self._split("营收100亿元"), ["营收100亿元"])

    def test_a03_multiple_sentences(self):
        self.assertEqual(
            self._split("中国移动营收最高。其次是中国电信。"),
            ["中国移动营收最高。", "其次是中国电信。"],
        )


# ============================================================
# SP13-B: 单 Agent 流式推 answer_chunk（1 项）
# ============================================================


class TestSingleAgentAnswerChunk(unittest.TestCase):
    """TC-13-B: _stream_single_agent 在 answer 前推送 answer_chunk"""

    def test_b01_answer_chunk_before_answer(self):
        from src.api_service import _stream_single_agent

        def _run_stream(query, company_name=None):
            yield {"type": "answer", "content": "营收100亿元。"}

        agent = MagicMock()
        agent.run_stream = _run_stream
        cm = MagicMock()

        async def _collect():
            events = []
            async for data in _stream_single_agent(agent, "查询", None, cm):
                if isinstance(data, str) and data.startswith("data: "):
                    payload = data[len("data: "):].strip()
                    if payload:
                        try:
                            events.append(json.loads(payload))
                        except json.JSONDecodeError:
                            pass
            return events

        events = asyncio.run(_collect())
        types = [e["type"] for e in events]

        self.assertIn("answer_chunk", types, "单 Agent 应推送 answer_chunk")
        self.assertIn("answer", types)
        self.assertLess(
            types.index("answer_chunk"), types.index("answer"),
            "answer_chunk 应先于 answer 推送",
        )


# ============================================================
# SP13-C: DelegateTool 完成事件清理（2 项）
# ============================================================


class TestDelegateCompletionCleanup(unittest.TestCase):
    """TC-13-C: DelegateTool 完成事件统一为 worker_done"""

    def _make_tool(self, event_queue):
        from src.tools.delegate_tool import DelegateTool
        from src.agent_registry import AgentRegistry, AgentCapability
        from src.shared_memory import SharedMemory

        registry = AgentRegistry()
        registry.register(AgentCapability(
            name="DataAgent", description="检索", tools=["retrieve"]
        ))
        sm = SharedMemory()
        tool = DelegateTool(
            agent_registry=registry,
            shared_memory=sm,
            event_queue=event_queue,
        )
        return tool

    def _drain_types(self, q):
        types = []
        while True:
            try:
                evt = q.get_nowait()
                types.append(evt.get("type"))
            except std_queue.Empty:
                break
        return types

    def test_c01_no_worker_complete_on_success(self):
        q = std_queue.Queue()
        tool = self._make_tool(event_queue=q)

        fake_worker = MagicMock()
        fake_result = MagicMock(
            success=True, answer="营收100亿元", total_steps=2, total_tokens=50, sources=[]
        )
        fake_worker.run.return_value = fake_result
        tool._create_agent = MagicMock(return_value=fake_worker)

        tool._run_worker_task(
            {"agent": "DataAgent", "task": "查询营收", "company_name": "中国移动"},
            worker_timeout=5,
            max_retries=0,
        )

        types = self._drain_types(q)
        self.assertNotIn("worker_complete", types, "成功路径不应再推 worker_complete")

    def test_c02_worker_done_on_failure(self):
        q = std_queue.Queue()
        tool = self._make_tool(event_queue=q)

        fake_worker = MagicMock()
        fake_worker.run.side_effect = Exception("boom")
        tool._create_agent = MagicMock(return_value=fake_worker)

        tool._run_worker_task(
            {"agent": "DataAgent", "task": "查询营收", "company_name": "中国移动"},
            worker_timeout=5,
            max_retries=0,
        )

        types = self._drain_types(q)
        self.assertIn("worker_done", types, "失败路径应推 worker_done 兜底")


# ============================================================
# SP13-D: 删除 workers_done（1 项）
# ============================================================


class TestNoWorkersDone(unittest.TestCase):
    """TC-13-D: api_service.py 不再推送 workers_done"""

    def test_d01_no_workers_done_in_source(self):
        src_path = Path(__file__).resolve().parent.parent / "src" / "api_service.py"
        text = src_path.read_text(encoding="utf-8")
        self.assertNotIn("workers_done", text, "api_service.py 不应再出现 workers_done")


if __name__ == "__main__":
    unittest.main()
