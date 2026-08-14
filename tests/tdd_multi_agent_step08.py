# -*- coding: utf-8 -*-
"""
TDD 测试: 多 Agent 升级 - 阶段五 调优（第一轮）

对应 TDD 规格: openspec/changes/multi-agent-step08/specs/tdd-step08.md
测试总计: 12 项
  - TC-80 工具描述嵌套参数展示: 4 项
  - TC-81 orchestrator 提示词 delegate 调用示例: 2 项
  - TC-82 DelegateTool 并行批次统计: 3 项
  - TC-83 api_service 观测日志 + 路由回归: 3 项

编码: UTF-8
"""

import logging
import queue
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# 将项目根目录加入 sys.path，使直接运行本脚本时 `import src` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============================================================
# TC-80: 工具描述嵌套参数展示（4 项）
# ============================================================


class TestToolDescriptionNestedParams(unittest.TestCase):
    """TC-80: 工具描述嵌套参数展示"""

    def setUp(self):
        from src.tools import ToolRegistry
        self.registry = ToolRegistry()

    def _create_delegate_tool_instance(self):
        """创建 DelegateTool 实例（依赖注入 Mock）"""
        from src.tools.delegate_tool import DelegateTool
        mock_registry = MagicMock()
        mock_registry.get.return_value = MagicMock()
        mock_memory = MagicMock()
        mock_memory.get_context_for.return_value = {}
        mock_memory.agent_outputs = {}
        return DelegateTool(
            agent_registry=mock_registry,
            shared_memory=mock_memory,
        )

    def test_delegate_desc_contains_agent(self):
        """TC-80-01: delegate 工具描述包含 agent 字段说明"""
        tool = self._create_delegate_tool_instance()
        self.registry.register(tool)
        desc = self.registry.get_tool_descriptions()
        self.assertIn("agent", desc, "delegate 工具描述应包含 agent 子字段说明")

    def test_delegate_desc_contains_task(self):
        """TC-80-02: delegate 工具描述包含 task 字段说明"""
        tool = self._create_delegate_tool_instance()
        self.registry.register(tool)
        desc = self.registry.get_tool_descriptions()
        self.assertIn("task", desc, "delegate 工具描述应包含 task 子字段说明")

    def test_plain_tool_no_regression(self):
        """TC-80-03: 普通工具（无嵌套参数）描述格式不变"""
        from src.tools.retrieve_tool import RetrieveTool
        tool = RetrieveTool()
        self.registry.register(tool)
        desc = self.registry.get_tool_descriptions()
        self.assertIn("retrieve", desc, "retrieve 工具应在描述中")
        self.assertNotIn("每项含", desc,
                         "无嵌套参数的工具描述不应包含'每项含'字样")

    def test_delegate_desc_contains_company_name(self):
        """TC-80-04: delegate 工具描述包含 company_name 字段说明"""
        tool = self._create_delegate_tool_instance()
        self.registry.register(tool)
        desc = self.registry.get_tool_descriptions()
        self.assertIn("company_name", desc,
                      "delegate 工具描述应包含 company_name 子字段说明")


# ============================================================
# TC-81: orchestrator 提示词 delegate 调用示例（2 项）
# ============================================================


class TestOrchestratorPromptExamples(unittest.TestCase):
    """TC-81: orchestrator 提示词 delegate 调用示例"""

    @classmethod
    def setUpClass(cls):
        import yaml
        from pathlib import Path
        prompts_path = Path(__file__).resolve().parent.parent / "config" / "agent_prompts.yaml"
        with open(prompts_path, "r", encoding="utf-8") as f:
            cls._prompts = yaml.safe_load(f)
        cls._orchestrator_template = cls._prompts.get("orchestrator", {}).get("template", "")

    def test_orchestrator_has_single_task_example(self):
        """TC-81-01: orchestrator prompt 包含 delegate 单任务调用示例"""
        self.assertIn("tasks", self._orchestrator_template,
                      "orchestrator 模板应包含 tasks 数组示例")
        self.assertIn('"agent"', self._orchestrator_template,
                      "orchestrator 模板应包含 agent 键示例")
        self.assertIn('"task"', self._orchestrator_template,
                      "orchestrator 模板应包含 task 键示例")

    def test_orchestrator_has_multi_task_example(self):
        """TC-81-02: orchestrator prompt 包含多任务并行示例"""
        self.assertIn("company_name", self._orchestrator_template,
                      "orchestrator 模板应包含 company_name 键（多任务并行示例）")


# ============================================================
# TC-82: DelegateTool 并行批次统计（3 项）
# ============================================================


class TestDelegateToolBatchStats(unittest.TestCase):
    """TC-82: DelegateTool 并行批次统计"""

    def setUp(self):
        from src.tools.delegate_tool import DelegateTool
        self.mock_registry = MagicMock()
        self.mock_memory = MagicMock()
        self.mock_memory.get_context_for.return_value = {}
        self.tool = DelegateTool(
            agent_registry=self.mock_registry,
            shared_memory=self.mock_memory,
        )

    def _mock_worker_run_success(self, query, company_name=None, shared_context=None):
        """Mock Worker Agent 执行成功"""
        result = MagicMock()
        result.success = True
        result.answer = "mock answer"
        result.total_steps = 2
        result.total_tokens = 100
        return result

    def _setup_mock_worker(self):
        """设置 Mock Worker Agent，使 _create_agent 返回 mock"""
        mock_worker = MagicMock()
        mock_worker.run = MagicMock(side_effect=self._mock_worker_run_success)

        mock_cap = MagicMock()
        mock_cap.name = "DataAgent"

        self.mock_registry.get.return_value = mock_cap

        original_create = self.tool._create_agent

        def mock_create(cap, step_callback=None):
            return mock_worker

        self.tool._create_agent = mock_create
        self.tool._original_create = original_create

    def test_single_task_batch_count_1(self):
        """TC-82-01: 单任务批次 parallel_batch_count=1"""
        self._setup_mock_worker()
        result = self.tool.run(tasks=[
            {"agent": "DataAgent", "task": "查询营收"}
        ])
        self.assertTrue(result.success)
        self.assertEqual(result.data["parallel_batch_count"], 1,
                         "单任务应只有 1 个并行批次")

    def test_multi_task_same_type_batch_count_1(self):
        """TC-82-02: 多任务同批并行 parallel_batch_count=1"""
        self._setup_mock_worker()
        result = self.tool.run(tasks=[
            {"agent": "DataAgent", "task": "查询中国移动营收", "company_name": "中国移动"},
            {"agent": "DataAgent", "task": "查询中国联通营收", "company_name": "中国联通"},
        ])
        self.assertTrue(result.success)
        self.assertEqual(result.data["parallel_batch_count"], 1,
                         "同类型 DataAgent 任务应为同 1 批并行")

    def test_mixed_task_batch_count_2(self):
        """TC-82-03: 检索+分析混合任务 parallel_batch_count=2"""

        def mock_create_mixed(cap, step_callback=None):
            mock_worker = MagicMock()
            mock_worker.run = MagicMock(side_effect=self._mock_worker_run_success)
            return mock_worker

        mock_cap_data = MagicMock()
        mock_cap_data.name = "DataAgent"
        mock_cap_compare = MagicMock()
        mock_cap_compare.name = "CompareAgent"

        self.mock_registry.get.side_effect = [mock_cap_data, mock_cap_compare]
        self.tool._create_agent = mock_create_mixed

        result = self.tool.run(tasks=[
            {"agent": "DataAgent", "task": "查询营收"},
            {"agent": "CompareAgent", "task": "对比营收"},
        ])
        self.assertTrue(result.success)
        self.assertEqual(result.data["parallel_batch_count"], 2,
                         "DataAgent + CompareAgent 应为 2 批次")


# ============================================================
# TC-83: api_service 观测日志 + 路由回归（3 项）
# ============================================================


class TestApiServiceLogging(unittest.TestCase):
    """TC-83: api_service 观测日志 + 路由回归"""

    @classmethod
    def setUpClass(cls):
        import src.api_service as api_module
        cls.api_module = api_module

    def setUp(self):
        self.log_stream = StringIO()
        self.log_handler = logging.StreamHandler(self.log_stream)
        self.log_handler.setLevel(logging.INFO)
        self.log_handler.setFormatter(logging.Formatter(
            "[%(name)s] %(message)s"
        ))
        self.api_logger = logging.getLogger("api_service")
        self.api_logger.addHandler(self.log_handler)
        self.api_logger.setLevel(logging.INFO)

    def tearDown(self):
        self.api_logger.removeHandler(self.log_handler)
        self.log_stream.close()

    def test_multi_agent_log_has_total_tokens(self):
        """TC-83-01: multi_agent 日志包含 total_tokens 字段"""
        # Mock _shared_state + OrchestratorAgent + SharedMemory
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.answer = "test answer"
        mock_result.reasoning_chain = []
        mock_result.sources = []
        mock_result.total_steps = 3
        mock_result.total_tokens = 1234
        mock_result.total_elapsed_ms = 100.0
        mock_result.forced_stop = False
        mock_result.error = None

        mock_shared_memory = MagicMock()
        mock_shared_memory.agent_outputs = {"DataAgent": MagicMock(), "CalcAgent": MagicMock()}
        mock_shared_memory.get_all_sources.return_value = []
        mock_shared_memory.get_agent_results.return_value = []

        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = mock_result
        mock_orchestrator.shared_memory = mock_shared_memory

        mock_request = MagicMock()
        mock_request.query = "test query"
        mock_request.company_name = "TestCompany"
        mock_request.mode = "multi"

        mock_cm = MagicMock()
        mock_cm.get_context_string.return_value = ""

        mock_reflector = MagicMock()
        mock_reflector.verify.return_value = MagicMock(
            overall_confidence=0.95,
            suggestions=[]
        )

        with patch("src.api_service.OrchestratorAgent",
                   return_value=mock_orchestrator), \
             patch("src.api_service._shared_state", {
                 "agent_registry": MagicMock(),
                 "reflector": mock_reflector,
             }), \
             patch("src.shared_memory.SharedMemory",
                   return_value=mock_shared_memory), \
             patch("src.tools.delegate_tool.DelegateTool", MagicMock()):
            import asyncio
            asyncio.run(self.api_module._handle_multi_agent_query(
                request=mock_request,
                cm=mock_cm,
                conversation_id="test-001",
            ))

        log_output = self.log_stream.getvalue()
        self.assertIn("total_tokens", log_output,
                      "多 Agent 日志应包含 total_tokens 记录")

    def test_multi_agent_log_has_workers(self):
        """TC-83-02: multi_agent 日志包含 workers 数量"""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.answer = "test answer"
        mock_result.reasoning_chain = []
        mock_result.sources = []
        mock_result.total_steps = 3
        mock_result.total_tokens = 500
        mock_result.total_elapsed_ms = 100.0
        mock_result.forced_stop = False
        mock_result.error = None

        mock_shared_memory = MagicMock()
        mock_shared_memory.agent_outputs = {
            "DataAgent(中国移动)": MagicMock(),
            "DataAgent(中国联通)": MagicMock(),
        }
        mock_shared_memory.get_all_sources.return_value = []
        mock_shared_memory.get_agent_results.return_value = []

        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = mock_result
        mock_orchestrator.shared_memory = mock_shared_memory

        mock_request = MagicMock()
        mock_request.query = "test query"
        mock_request.company_name = "TestCompany"
        mock_request.mode = "multi"

        mock_cm = MagicMock()
        mock_cm.get_context_string.return_value = ""

        mock_reflector = MagicMock()
        mock_reflector.verify.return_value = MagicMock(
            overall_confidence=0.95,
            suggestions=[]
        )

        with patch("src.api_service.OrchestratorAgent",
                   return_value=mock_orchestrator), \
             patch("src.api_service._shared_state", {
                 "agent_registry": MagicMock(),
                 "reflector": mock_reflector,
             }), \
             patch("src.shared_memory.SharedMemory",
                   return_value=mock_shared_memory), \
             patch("src.tools.delegate_tool.DelegateTool", MagicMock()):
            import asyncio
            asyncio.run(self.api_module._handle_multi_agent_query(
                request=mock_request,
                cm=mock_cm,
                conversation_id="test-002",
            ))

        log_output = self.log_stream.getvalue()
        self.assertIn("workers=2", log_output,
                      "多 Agent 日志应包含 workers=2 记录")

    def test_simple_query_not_routed_to_multi_agent(self):
        """TC-83-03: 简单查询路由不误判 multi_agent"""
        from src.router import QueryRouter

        mock_turbo_llm = MagicMock()
        mock_turbo_llm.chat.return_value = '{"mode": "rag"}'
        router = QueryRouter(turbo_llm=mock_turbo_llm)

        result = router.route("中芯国际2024年营收是多少")
        self.assertEqual(result.mode, "rag",
                         "单公司简单查询应路由到 rag 模式，不应误判为 multi_agent")


if __name__ == "__main__":
    unittest.main()
