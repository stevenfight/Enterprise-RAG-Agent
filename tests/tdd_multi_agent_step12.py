# -*- coding: utf-8 -*-
"""
TDD 测试: 多 Agent 升级 - 阶段十二 SSE 流式进展接入 Worker 步骤事件

对应 TDD 规格: openspec/changes/multi-agent-step12/specs/tdd-step12.md
测试总计: 7 项
  - SP12-A ReActAgent.run() 的 step_callback 行为: 4 项
  - SP12-B DelegateTool 注入 StepCallback: 3 项

编码: UTF-8
"""

import queue as std_queue
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# 将项目根目录加入 sys.path，使直接运行本脚本时 `import src` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class AgentTestCase(unittest.TestCase):
    """需要构造 ReActAgent（及其子类）的测试基类

    ReActAgent.__init__ 会调用 get_api_key()，无环境变量时会抛 ValueError，
    因此统一 patch 掉，避免测试依赖运行环境。
    """

    def setUp(self):
        self._api_patcher = patch(
            "src.agent_core.get_api_key", return_value="test-api-key"
        )
        self._api_patcher.start()

    def tearDown(self):
        self._api_patcher.stop()


# ============================================================
# SP12-A: ReActAgent.run() 的 step_callback 行为（4 项）
# ============================================================


class TestRunStepCallback(AgentTestCase):
    """TC-12-A: run() 在注入 step_callback 时推送 worker_step / worker_done"""

    def _run_with_callback(self):
        """构造 ReActAgent 并 mock LLM / 工具执行，返回 (agent, callback)"""
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry

        callback = MagicMock()
        agent = ReActAgent(tool_registry=ToolRegistry(), step_callback=callback)

        # 首轮返回 thought + action，次轮返回 Final Answer
        agent._call_llm = MagicMock(side_effect=[
            "Thought: 需要检索\nAction: retrieve\nAction Input: {\"query\": \"营收\"}",
            "Thought: 已收集足够信息\nFinal Answer: 营收100亿元",
        ])
        agent._execute_action = MagicMock(return_value="检索到营收 100 亿元")

        agent.run("查询营收")
        return agent, callback

    def test_a01_thought_step_pushed(self):
        _, callback = self._run_with_callback()

        step_types = [c.args[0] for c in callback.on_step.call_args_list]
        self.assertIn("thought", step_types, "run() 应推送 thought 步骤事件")

    def test_a02_action_step_pushed_with_tool_name(self):
        _, callback = self._run_with_callback()

        action_calls = [c for c in callback.on_step.call_args_list if c.args[0] == "action"]
        self.assertTrue(action_calls, "run() 应推送 action 步骤事件")
        self.assertEqual(action_calls[0].args[2], "retrieve", "action 内容应为工具名")

    def test_a03_observation_step_pushed(self):
        _, callback = self._run_with_callback()

        step_types = [c.args[0] for c in callback.on_step.call_args_list]
        self.assertIn("observation", step_types, "run() 应推送 observation 步骤事件")

    def test_a04_on_done_pushed_with_success(self):
        _, callback = self._run_with_callback()

        callback.on_done.assert_called_once()
        result = callback.on_done.call_args.args[0]
        self.assertTrue(result.success, "Final Answer 完成后应推送 success=True 的 on_done")


# ============================================================
# SP12-B: DelegateTool 注入 StepCallback（3 项）
# ============================================================


class TestDelegateInjectsCallback(AgentTestCase):
    """TC-12-B: DelegateTool 在 _run_worker_task 中注入 StepCallback"""

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

        fake_worker = MagicMock()
        fake_result = MagicMock(
            success=True,
            answer="营收 100 亿元",
            total_steps=2,
            total_tokens=50,
            sources=[],
        )
        fake_worker.run.return_value = fake_result
        tool._create_agent = MagicMock(return_value=fake_worker)
        return tool, fake_worker

    def test_b01_inject_step_callback_when_queue_present(self):
        from src.step_callback import StepCallback

        tool, fake_worker = self._make_tool(event_queue=std_queue.Queue())
        tool._run_worker_task(
            {"agent": "DataAgent", "task": "查询营收", "company_name": "中国移动"},
            worker_timeout=5,
            max_retries=0,
        )

        self.assertIsInstance(
            fake_worker._step_callback, StepCallback,
            "有 event_queue 时应向 Worker 注入 StepCallback",
        )
        self.assertEqual(
            fake_worker._step_callback.agent_name, "DataAgent",
            "StepCallback 的 agent_name 应为纯 Agent 名",
        )

    def test_b02_no_inject_when_queue_absent(self):
        tool, fake_worker = self._make_tool(event_queue=None)
        tool._run_worker_task(
            {"agent": "DataAgent", "task": "查询营收", "company_name": "中国移动"},
            worker_timeout=5,
            max_retries=0,
        )

        self.assertIsNone(
            fake_worker._step_callback,
            "无 event_queue 时不应注入 StepCallback",
        )

    def test_b03_worker_step_event_fields_complete(self):
        from src.step_callback import StepCallback

        q = std_queue.Queue()
        callback = StepCallback(agent_name="DataAgent", event_queue=q)
        callback.on_step("action", 1, "retrieve")

        event = q.get_nowait()
        self.assertEqual(event["type"], "worker_step")
        self.assertEqual(event["agent"], "DataAgent")
        self.assertEqual(event["step_type"], "action")
        self.assertEqual(event["step"], 1)
        self.assertEqual(event["content"], "retrieve")


if __name__ == "__main__":
    unittest.main()
