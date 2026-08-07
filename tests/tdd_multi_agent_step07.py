# -*- coding: utf-8 -*-
"""
TDD 测试: 步骤 4.1 ~ 4.3 多 Agent 升级 - 阶段四 API 端点统一

对应 TDD 规格: openspec/changes/multi-agent-step07/specs/tdd-step07.md
测试总计: 15 项
  - TC-70 AgentQueryRequest 参数扩展: 5 项
  - TC-71 mode 路由控制: 5 项
  - TC-72 多 Agent SSE 事件完整性: 5 项

编码: UTF-8
"""

import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError


# ============================================================
# TC-70: AgentQueryRequest 参数扩展（5 项）
# ============================================================


class TestAgentQueryRequestFields(unittest.TestCase):
    """TC-70: AgentQueryRequest 参数扩展"""

    @classmethod
    def setUpClass(cls):
        from src.api_service import AgentQueryRequest
        cls.AgentQueryRequest = AgentQueryRequest

    def test_mode_field_exists(self):
        """TC-70-01: AgentQueryRequest 包含 mode 字段"""
        req = self.AgentQueryRequest(query="test", mode="multi")
        self.assertEqual(req.mode, "multi")

    def test_company_name_field_exists(self):
        """TC-70-02: AgentQueryRequest 包含 company_name 字段"""
        req = self.AgentQueryRequest(query="test", company_name="CompanyA")
        self.assertEqual(req.company_name, "CompanyA")

    def test_mode_default_value(self):
        """TC-70-03: AgentQueryRequest mode 默认值为 auto"""
        req = self.AgentQueryRequest(query="test")
        self.assertEqual(req.mode, "auto")

    def test_mode_rejects_invalid_value(self):
        """TC-70-04: mode 非法值应被拒绝"""
        with self.assertRaises(ValidationError):
            self.AgentQueryRequest(query="test", mode="invalid")

    def test_company_name_default_none(self):
        """TC-70-05: company_name 默认值为 None"""
        req = self.AgentQueryRequest(query="test")
        self.assertIsNone(req.company_name)


# ============================================================
# TC-71: mode 路由控制（5 项）
# ============================================================


class TestModeRouting(unittest.TestCase):
    """TC-71: mode 路由控制"""

    @classmethod
    def setUpClass(cls):
        from src.api_service import AgentQueryRequest
        cls.AgentQueryRequest = AgentQueryRequest

    def setUp(self):
        """准备 mock 对象（共享）"""
        self.mock_router = MagicMock()
        mock_route = MagicMock()
        mock_route.mode = "single_agent"
        mock_route.trace = ""
        mock_route.reasoning = ""
        mock_route.category = None
        self.mock_router.route.return_value = mock_route

        self.mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.answer = "multi answer"
        mock_result.total_steps = 1
        mock_result.total_elapsed_ms = 100.0
        mock_result.forced_stop = False
        mock_result.error = None
        mock_result.reasoning_chain = []
        self.mock_orchestrator.run.return_value = mock_result

        self.mock_reflector = MagicMock()
        mock_ref = MagicMock()
        mock_ref.score = 0.95
        mock_ref.issues = []
        mock_ref.corrected_answer = None
        self.mock_reflector.verify.return_value = mock_ref

    def test_mode_single_skips_router(self):
        """TC-71-01: mode="single" 时不调用 router"""
        import src.api_service as svc

        mock_agent = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.success = True
        mock_run_result.answer = "single answer"
        mock_run_result.total_steps = 1
        mock_run_result.total_elapsed_ms = 50.0
        mock_run_result.forced_stop = False
        mock_run_result.error = None
        mock_run_result.reasoning_chain = []
        mock_agent.run.return_value = mock_run_result

        mock_cm = MagicMock()
        mock_cm.agent_memory = MagicMock()
        mock_cm.get_context_string.return_value = ""

        with patch.object(svc, '_shared_state', {
            'agent_initialized': True,
            'query_router': self.mock_router,
            'llm_provider': MagicMock(),
            'tool_registry': MagicMock(),
            'ag_cfg': {'model': 'qwen-turbo', 'llm_timeout': 90, 'max_retries': 2,
                        'api_max_steps_hard_limit': 15},
            'reflector': self.mock_reflector,
        }):
            with patch('src.api_service._create_per_request_agent', return_value=mock_agent):
                with patch('src.api_service._ensure_conversation', return_value=mock_cm):
                    request = self.AgentQueryRequest(query="test", mode="single")
                    resp = asyncio.run(svc.api_agent_query(request))
                    self.assertEqual(resp.answer, "single answer")
                    self.mock_router.route.assert_not_called()

    def test_mode_multi_skips_router(self):
        """TC-71-02: mode="multi" 时不调用 router"""
        import src.api_service as svc

        mock_registry = MagicMock()
        mock_cm = MagicMock()
        mock_cm.agent_memory = MagicMock()
        mock_cm.get_context_string.return_value = ""

        mock_sm = MagicMock()
        mock_sm.agent_outputs = {}
        mock_sm.get_total_tokens.return_value = 0
        mock_sm.get_all_sources.return_value = []

        # SharedMemory/DelegateTool 在函数体内懒加载，需 patch 源模块
        with patch.object(svc, '_shared_state', {
            'agent_initialized': True,
            'query_router': self.mock_router,
            'agent_registry': mock_registry,
            'llm_provider': MagicMock(),
            'reflector': self.mock_reflector,
        }):
            with patch('src.api_service._ensure_conversation', return_value=mock_cm):
                with patch('src.shared_memory.SharedMemory', return_value=mock_sm):
                    with patch('src.tools.delegate_tool.DelegateTool', return_value=MagicMock()):
                        with patch.object(svc, 'OrchestratorAgent', return_value=self.mock_orchestrator):
                            request = self.AgentQueryRequest(query="test", mode="multi")
                            resp = asyncio.run(svc.api_agent_query(request))
                            self.assertTrue(resp.success)
                            self.assertEqual(resp.answer, "multi answer")
                            self.mock_router.route.assert_not_called()

    def test_mode_auto_router_none_fallback_single(self):
        """TC-71-03: mode="auto" 且 router 不可用时 fallback 到 single"""
        import src.api_service as svc

        mock_agent = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.success = True
        mock_run_result.answer = "fallback answer"
        mock_run_result.total_steps = 1
        mock_run_result.total_elapsed_ms = 50.0
        mock_run_result.forced_stop = False
        mock_run_result.error = None
        mock_run_result.reasoning_chain = []
        mock_agent.run.return_value = mock_run_result

        mock_cm = MagicMock()
        mock_cm.agent_memory = MagicMock()
        mock_cm.get_context_string.return_value = ""

        with patch.object(svc, '_shared_state', {
            'agent_initialized': True,
            'query_router': None,  # router 不可用
            'llm_provider': MagicMock(),
            'tool_registry': MagicMock(),
            'ag_cfg': {'model': 'qwen-turbo', 'llm_timeout': 90, 'max_retries': 2,
                        'api_max_steps_hard_limit': 15},
            'reflector': self.mock_reflector,
        }):
            with patch('src.api_service._create_per_request_agent', return_value=mock_agent):
                with patch('src.api_service._ensure_conversation', return_value=mock_cm):
                    request = self.AgentQueryRequest(query="test", mode="auto")
                    resp = asyncio.run(svc.api_agent_query(request))
                    self.assertEqual(resp.answer, "fallback answer")

    def test_mode_multi_passes_company_name(self):
        """TC-71-04: mode="multi" 下 company_name 传递给 Orchestrator"""
        import src.api_service as svc

        mock_registry = MagicMock()
        mock_cm = MagicMock()
        mock_cm.agent_memory = MagicMock()
        mock_cm.get_context_string.return_value = ""

        mock_sm = MagicMock()
        mock_sm.agent_outputs = {}
        mock_sm.get_total_tokens.return_value = 0
        mock_sm.get_all_sources.return_value = []

        with patch.object(svc, '_shared_state', {
            'agent_initialized': True,
            'query_router': self.mock_router,
            'agent_registry': mock_registry,
            'llm_provider': MagicMock(),
            'reflector': self.mock_reflector,
        }):
            with patch('src.api_service._ensure_conversation', return_value=mock_cm):
                with patch('src.shared_memory.SharedMemory', return_value=mock_sm):
                    with patch('src.tools.delegate_tool.DelegateTool', return_value=MagicMock()):
                        with patch.object(svc, 'OrchestratorAgent', return_value=self.mock_orchestrator):
                            request = self.AgentQueryRequest(
                                query="test", mode="multi", company_name="TestCorp",
                            )
                            asyncio.run(svc.api_agent_query(request))
                            call_kwargs = self.mock_orchestrator.run.call_args
                            self.assertIsNotNone(call_kwargs)
                            self.assertEqual(
                                call_kwargs[1].get('company_name'), "TestCorp",
                            )

    def test_get_stream_mode_parameter(self):
        """TC-71-05: GET /api/agent/stream mode 参数解析"""
        import src.api_service as svc

        mock_cm = MagicMock()
        mock_cm.agent_memory = MagicMock()
        mock_cm.get_context_string.return_value = ""

        mock_agent = MagicMock()

        with patch.object(svc, '_shared_state', {
            'agent_initialized': True,
            'query_router': None,
            'agent_registry': MagicMock(),
            'llm_provider': MagicMock(),
            'tool_registry': MagicMock(),
            'ag_cfg': {'model': 'qwen-turbo', 'llm_timeout': 90, 'max_retries': 2,
                        'api_max_steps_hard_limit': 15},
            'reflector': self.mock_reflector,
        }):
            with patch('src.api_service._ensure_conversation', return_value=mock_cm):
                with patch('src.api_service._create_per_request_agent', return_value=mock_agent):
                    # mode=multi 应触发 _stream_multi_agent 分支
                    with patch('src.api_service._stream_multi_agent') as mock_sma:
                        async def _fake():
                            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
                        mock_sma.return_value = _fake()

                        # api_agent_stream 返回 StreamingResponse，传入 _fake generator
                        resp = asyncio.run(svc.api_agent_stream(
                            query="test", mode="multi",
                        ))
                        self.assertIsNotNone(resp)


# ============================================================
# TC-72: 多 Agent SSE 事件完整性（5 项）
# ============================================================


class TestMultiAgentSSEEvents(unittest.TestCase):
    """TC-72: 多 Agent SSE 事件完整性"""

    def setUp(self):
        self.mock_registry = MagicMock()
        self.mock_registry.list_all.return_value = ["DataAgent"]

        self.mock_reflector = MagicMock()
        mock_ref = MagicMock()
        mock_ref.score = 0.9
        mock_ref.issues = []
        mock_ref.corrected_answer = None
        self.mock_reflector.verify.return_value = mock_ref

    def _collect_events(self, final_answer="short answer."):
        """运行 _stream_multi_agent 并收集所有解析后的 SSE 事件"""
        import src.api_service as svc

        shared_mem = MagicMock()
        shared_mem.agent_outputs = {"DataAgent": MagicMock()}
        shared_mem.get_total_tokens.return_value = 500
        shared_mem.get_all_sources.return_value = []

        mock_cm = MagicMock()
        mock_cm.get_context_string.return_value = ""

        with patch.object(svc, '_shared_state', {
            'agent_initialized': True,
            'agent_registry': self.mock_registry,
            'llm_provider': MagicMock(),
            'reflector': self.mock_reflector,
        }):
            with patch('src.shared_memory.SharedMemory', return_value=shared_mem):
                with patch('src.tools.delegate_tool.DelegateTool', return_value=MagicMock()):
                    mock_orch = MagicMock()
                    mock_result = MagicMock()
                    mock_result.answer = final_answer
                    mock_result.success = True
                    mock_result.total_steps = 2
                    mock_result.total_elapsed_ms = 200.0
                    mock_result.forced_stop = False
                    mock_result.error = None
                    mock_result.reasoning_chain = []
                    mock_orch.run.return_value = mock_result

                    with patch.object(svc, 'OrchestratorAgent', return_value=mock_orch):
                        async def _collect():
                            events = []
                            async for raw in svc._stream_multi_agent(
                                query="test", company_name=None, cm=mock_cm,
                            ):
                                if raw.startswith("data: ") and raw[6:].strip():
                                    try:
                                        events.append(json.loads(raw[6:].strip()))
                                    except json.JSONDecodeError:
                                        pass
                            return events

                        return asyncio.run(_collect())

    def test_sse_contains_delegating_event(self):
        """TC-72-01: SSE 流中包含 delegating 事件"""
        events = self._collect_events()
        event_types = [e.get("type") for e in events]
        self.assertIn("delegating", event_types,
                      f"应包含 delegating 事件，实际: {event_types}")

    def test_sse_contains_workers_done_event(self):
        """TC-72-02: SSE 流中包含 workers_done 事件"""
        events = self._collect_events()
        event_types = [e.get("type") for e in events]
        self.assertIn("workers_done", event_types,
                      f"应包含 workers_done 事件，实际: {event_types}")

    def test_answer_chunk_split_by_sentence(self):
        """TC-72-03: answer_chunk 事件按句子拆分"""
        events = self._collect_events(
            final_answer="CompanyA营收增长10%。CompanyB营收增长5%。",
        )
        chunks = [e for e in events if e.get("type") == "answer_chunk"]
        self.assertGreaterEqual(len(chunks), 2,
                                f"预期 >=2 个 answer_chunk，实际: {len(chunks)}, {chunks}")

    def test_reflection_is_independent_event(self):
        """TC-72-04: reflection 为独立事件（非嵌套在 answer 内）"""
        events = self._collect_events()
        event_types = [e.get("type") for e in events]
        self.assertIn("reflection", event_types,
                      f"应包含 reflection 事件，实际: {event_types}")
        # answer 事件中不应含 reflection 字段
        for ae in events:
            if ae.get("type") == "answer":
                self.assertNotIn("reflection", ae,
                                 "answer payload 不应含 reflection 字段")

    def test_sse_starts_with_connected(self):
        """TC-72-05: SSE 流中应包含 connected 事件且为首个"""
        events = self._collect_events()
        self.assertGreater(len(events), 0, "SSE 流应至少有一个事件")
        self.assertEqual(events[0].get("type"), "connected",
                         f"第一个事件应为 connected，实际: {events[0].get('type')}")


if __name__ == "__main__":
    unittest.main()
