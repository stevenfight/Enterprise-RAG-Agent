# -*- coding: utf-8 -*-
"""
TDD 测试: 多 Agent 升级 - 阶段九 启用/运行验证 + 可靠性回归补测

对应 TDD 规格: openspec/changes/multi-agent-step09/specs/tdd-step09.md
测试总计: 25 项
  - SP9-A 多 Agent 启用验证: 6 项
  - SP9-B 多 Agent 运行链路验证: 4 项
  - SP9-C 历史修复点回归: 15 项
    - SP9-C1 平衡括号 JSON 提取: 6 项
    - SP9-C2 Action=Final 空正文回退: 5 项
    - SP9-C3 单位换算规则覆盖: 4 项

编码: UTF-8
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# 将项目根目录加入 sys.path，使直接运行本脚本时 `import src` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============================================================
# 公共常量与工具函数
# ============================================================

WORKER_NAMES = ["DataAgent", "CalcAgent", "CompareAgent", "ChartAgent", "VerifyAgent"]


def _make_registry():
    """注册 5 个 Worker 能力的 AgentRegistry 实例"""
    from src.agent_registry import AgentRegistry, AgentCapability
    registry = AgentRegistry()
    for name in WORKER_NAMES:
        registry.register(AgentCapability(
            name=name,
            description=f"{name} 能力描述",
            tools=["retrieve"],
        ))
    return registry


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
# SP9-A: 多 Agent 启用验证（6 项）
# ============================================================


class TestAgentRegistryEnabled(unittest.TestCase):
    """TC-09-A-01: AgentRegistry 注册 5 个 Worker"""

    def test_registry_registers_5_workers(self):
        registry = _make_registry()

        names = registry.list_all()
        self.assertEqual(len(names), 5, "应注册 5 个 Worker")
        for name in WORKER_NAMES:
            self.assertIn(name, names, f"{name} 应已注册")

        desc = registry.get_agent_descriptions()
        for name in WORKER_NAMES:
            self.assertIn(name, desc, f"描述应包含 Worker 名 {name}")


class TestRouterMultiAgent(unittest.TestCase):
    """TC-09-A-02: QueryRouter 多公司对比路由到 multi_agent"""

    def test_multi_compare_routes_to_multi_agent(self):
        from src.router import QueryRouter

        router = QueryRouter(turbo_llm=MagicMock())
        result = router.route("中国移动和中国联通2024年营收对比")

        self.assertEqual(result.mode, "multi_agent")
        self.assertEqual(result.trace, "regex")


class TestOrchestratorInit(AgentTestCase):
    """TC-09-A-03: OrchestratorAgent 初始化正确"""

    def test_orchestrator_init(self):
        from src.orchestrator_agent import OrchestratorAgent
        from src.tools.delegate_tool import DelegateTool
        from src.shared_memory import SharedMemory

        registry = _make_registry()
        sm = SharedMemory()
        delegate_tool = DelegateTool(agent_registry=registry, shared_memory=sm)

        orch = OrchestratorAgent(
            delegate_tool=delegate_tool,
            agent_registry=registry,
            shared_memory=sm,
        )

        # 工具仅含 delegate
        self.assertEqual(orch.tool_registry.list_all(), ["delegate"])
        # 模型为 qwen-max
        self.assertEqual(orch.model, "qwen-max")
        # _agent_descriptions 含 Worker 名
        for name in WORKER_NAMES:
            self.assertIn(name, orch._agent_descriptions)


class TestDelegateDependencyGrouping(unittest.TestCase):
    """TC-09-A-04: DelegateTool 依赖分组正确"""

    def test_dependency_grouping_two_batches(self):
        from src.tools.delegate_tool import DelegateTool

        tool = DelegateTool(agent_registry=MagicMock(), shared_memory=MagicMock())
        tasks = [
            {"agent": "DataAgent", "task": "查询数据"},
            {"agent": "CalcAgent", "task": "计算指标"},
            {"agent": "CompareAgent", "task": "对比"},
            {"agent": "ChartAgent", "task": "画图"},
            {"agent": "VerifyAgent", "task": "验证"},
        ]

        batches = tool._group_by_dependency(tasks)

        self.assertEqual(len(batches), 2, "应分两批")
        self.assertEqual(
            [t["agent"] for t in batches[0]],
            ["DataAgent", "CalcAgent"],
            "第一批应为并行批 DataAgent/CalcAgent",
        )
        self.assertEqual(
            [t["agent"] for t in batches[1]],
            ["CompareAgent", "ChartAgent", "VerifyAgent"],
            "第二批应为下游批",
        )


class TestCreateAgent(AgentTestCase):
    """TC-09-A-05: DelegateTool 创建 5 种 Worker"""

    def test_create_agent_5_types(self):
        from src.tools.delegate_tool import DelegateTool
        from src.agent_registry import AgentCapability
        from src.worker_agents.data_agent import DataAgent
        from src.worker_agents.calc_agent import CalcAgent
        from src.worker_agents.compare_agent import CompareAgent
        from src.worker_agents.chart_agent import ChartAgent
        from src.worker_agents.verify_agent import VerifyAgent

        tool = DelegateTool(agent_registry=MagicMock(), shared_memory=MagicMock())

        expected = {
            "DataAgent": DataAgent,
            "CalcAgent": CalcAgent,
            "CompareAgent": CompareAgent,
            "ChartAgent": ChartAgent,
            "VerifyAgent": VerifyAgent,
        }

        for name, cls in expected.items():
            cap = AgentCapability(name=name, description="测试", tools=["retrieve"])
            agent = tool._create_agent(cap)
            self.assertIsInstance(
                agent, cls, f"{name} 应创建 {cls.__name__} 实例"
            )


class TestDelegateEmptyTasks(unittest.TestCase):
    """TC-09-A-06: DelegateTool 空 tasks 返回失败"""

    def test_empty_tasks_returns_failure(self):
        from src.tools.delegate_tool import DelegateTool

        tool = DelegateTool(agent_registry=MagicMock(), shared_memory=MagicMock())
        result = tool.run(tasks=[])

        self.assertFalse(result.success, "空 tasks 应返回失败")


# ============================================================
# SP9-B: 多 Agent 运行链路验证（4 项）
# ============================================================


class TestParseDelegateAction(AgentTestCase):
    """TC-09-B-01: delegate 动作解析（嵌套 tasks JSON）"""

    def test_parse_delegate_action(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry

        agent = ReActAgent(tool_registry=ToolRegistry())
        response = (
            "Thought: 需要拆解并委托\n"
            "Action: delegate\n"
            'Action Input: {"tasks": [{"agent": "DataAgent", "task": "查询中国移动营收", "company_name": "中国移动"}]}'
        )

        thought, action, action_input = agent._parse_response(response)

        self.assertEqual(action, "delegate")
        self.assertIsInstance(action_input, dict)
        self.assertIn("tasks", action_input)
        self.assertEqual(len(action_input["tasks"]), 1)
        self.assertEqual(action_input["tasks"][0]["agent"], "DataAgent")


class TestExecuteDelegateAction(AgentTestCase):
    """TC-09-B-02: delegate 工具路由"""

    def test_execute_delegate_action(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry, ToolResult

        agent = ReActAgent(tool_registry=ToolRegistry())

        mock_delegate = MagicMock()
        mock_delegate.name = "delegate"
        mock_delegate.description = "委托工具"
        mock_delegate.parameters = {
            "type": "object",
            "properties": {"tasks": {"type": "array", "description": "任务列表"}},
        }
        mock_result = ToolResult(
            success=True,
            data={"summary": "委托执行完成", "total": 1, "results": []},
        )
        mock_delegate.run.return_value = mock_result
        agent.tool_registry.register(mock_delegate)

        tasks = [{"agent": "DataAgent", "task": "查询营收"}]
        obs = agent._execute_action("delegate", {"tasks": tasks})

        mock_delegate.run.assert_called_once_with(tasks=tasks)
        self.assertIn("委托执行完成", obs, "应返回 delegate 工具的 Observation")


class TestWorkerTaskWritesMemory(unittest.TestCase):
    """TC-09-B-03: Worker 执行写回 SharedMemory"""

    def test_worker_task_writes_shared_memory(self):
        from src.tools.delegate_tool import DelegateTool
        from src.shared_memory import SharedMemory
        from src.agent_registry import AgentRegistry, AgentCapability

        registry = AgentRegistry()
        registry.register(AgentCapability(
            name="DataAgent", description="检索", tools=["retrieve"]
        ))
        sm = SharedMemory()
        tool = DelegateTool(agent_registry=registry, shared_memory=sm)

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

        entry = tool._run_worker_task(
            {"agent": "DataAgent", "task": "查询营收", "company_name": "中国移动"},
            worker_timeout=5,
            max_retries=0,
        )

        self.assertTrue(entry["success"])
        self.assertIn("DataAgent(中国移动)", sm.agent_outputs)
        self.assertEqual(sm.agent_outputs["DataAgent(中国移动)"], fake_result)


class TestOrchestratorFullChain(AgentTestCase):
    """TC-09-B-04: Orchestrator 完整链路汇总"""

    def test_orchestrator_full_chain(self):
        from src.orchestrator_agent import OrchestratorAgent
        from src.tools.delegate_tool import DelegateTool
        from src.shared_memory import SharedMemory
        from src.agent_registry import AgentRegistry, AgentCapability

        registry = AgentRegistry()
        registry.register(AgentCapability(
            name="DataAgent", description="检索", tools=["retrieve"]
        ))
        sm = SharedMemory()
        delegate_tool = DelegateTool(agent_registry=registry, shared_memory=sm)

        fake_worker = MagicMock()
        fake_result = MagicMock(
            success=True,
            answer="营收 100 亿元",
            total_steps=1,
            total_tokens=10,
            sources=[],
        )
        fake_worker.run.return_value = fake_result
        delegate_tool._create_agent = MagicMock(return_value=fake_worker)

        orch = OrchestratorAgent(
            delegate_tool=delegate_tool,
            agent_registry=registry,
            shared_memory=sm,
        )

        delegate_response = (
            "Thought: 需要检索中国移动营收\n"
            "Action: delegate\n"
            'Action Input: {"tasks": [{"agent": "DataAgent", "task": "查询中国移动营收", "company_name": "中国移动"}]}'
        )
        final_response = "Thought: 已完成\nFinal Answer: 中国移动2024年营收为100亿元"
        orch._call_llm = MagicMock(side_effect=[delegate_response, final_response])

        result = orch.run("中国移动2024年营收是多少")

        self.assertTrue(result.success)
        self.assertIn("100亿元", result.answer)
        self.assertIn("DataAgent(中国移动)", sm.agent_outputs)

        actions = [s["action"] for s in result.reasoning_chain]
        self.assertIn("delegate", actions, "推理链应包含 delegate 步骤")


# ============================================================
# SP9-C1: 平衡括号 JSON 提取（6 项）
# ============================================================


class TestExtractJsonObject(unittest.TestCase):
    """SP9-C1: _extract_json_object 平衡括号扫描"""

    def test_simple_json_object(self):
        from src.agent_core import _extract_json_object
        self.assertEqual(_extract_json_object('{"a": 1}'), '{"a": 1}')

    def test_nested_json_full_extract(self):
        from src.agent_core import _extract_json_object
        text = '{"tasks": [{"agent": "DataAgent", "task": "查询"}, {"agent": "CalcAgent", "task": "计算"}]}'
        self.assertEqual(_extract_json_object(text), text)

    def test_brace_inside_string(self):
        from src.agent_core import _extract_json_object
        text = '{"text": "a{b}c"}'
        self.assertEqual(_extract_json_object(text), text)

    def test_escaped_quote_inside_string(self):
        from src.agent_core import _extract_json_object
        text = '{"text": "a\\"b"}'
        self.assertEqual(_extract_json_object(text), text)

    def test_no_brace_returns_none(self):
        from src.agent_core import _extract_json_object
        self.assertIsNone(_extract_json_object("no json here"))

    def test_missing_close_brace_returns_none(self):
        from src.agent_core import _extract_json_object
        self.assertIsNone(_extract_json_object('{"a": 1'))


# ============================================================
# SP9-C2: Action=Final 空正文回退（5 项）
# ============================================================


class TestParseFinalFallback(AgentTestCase):
    """SP9-C2: _parse_response 的 Final 终止动作处理"""

    def test_final_no_body_fallback_to_thought(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry

        agent = ReActAgent(tool_registry=ToolRegistry())
        thought, action, answer = agent._parse_response(
            "Thought: 答案X\nAction: Final"
        )

        self.assertEqual(action, "Final Answer")
        self.assertEqual(answer, "答案X")

    def test_final_answer_normal_body(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry

        agent = ReActAgent(tool_registry=ToolRegistry())
        thought, action, answer = agent._parse_response(
            "Thought: 思考\nFinal Answer: 完整答案"
        )

        self.assertEqual(action, "Final Answer")
        self.assertEqual(answer, "完整答案")

    def test_final_with_json_answer(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry

        agent = ReActAgent(tool_registry=ToolRegistry())
        thought, action, answer = agent._parse_response(
            'Thought: 思考\nAction: Final\nAction Input: {"answer": "答案"}'
        )

        self.assertEqual(action, "Final Answer")
        self.assertEqual(answer, "答案")

    def test_final_no_body_and_no_thought(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry

        agent = ReActAgent(tool_registry=ToolRegistry())
        thought, action, answer = agent._parse_response("Action: Final")

        self.assertEqual(action, "Final Answer")
        self.assertEqual(answer, "")

    def test_non_json_action_input_fallback(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry

        agent = ReActAgent(tool_registry=ToolRegistry())
        thought, action, action_input = agent._parse_response(
            "Action: retrieve\nAction Input: 纯文本参数"
        )

        self.assertEqual(action, "retrieve")
        self.assertEqual(action_input, "纯文本参数")


# ============================================================
# SP9-C3: 单位换算规则覆盖（4 项）
# ============================================================


class TestUnitConversion(AgentTestCase):
    """SP9-C3: 单位换算规则覆盖"""

    @classmethod
    def setUpClass(cls):
        import yaml
        prompts_path = (
            Path(__file__).resolve().parent.parent / "config" / "agent_prompts.yaml"
        )
        with open(prompts_path, "r", encoding="utf-8") as f:
            cls._prompts = yaml.safe_load(f)

    def test_yaml_sections_contain_million_conversion(self):
        sections = [
            "default", "orchestrator", "data_agent",
            "calc_agent", "compare_agent", "verify_agent",
        ]
        for section in sections:
            template = self._prompts.get(section, {}).get("template", "")
            self.assertIn(
                "百万元 ÷ 100", template,
                f"{section} 节应包含百万元换算规则",
            )

    def test_fallback_prompt_contains_formula_and_example(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry

        agent = ReActAgent(tool_registry=ToolRegistry())
        prompt = agent._default_system_prompt
        self.assertIn("百万元 ÷ 100 = 亿元", prompt)
        self.assertIn("10,407.59亿元", prompt)

    def test_yaml_default_contains_example_value(self):
        default_template = self._prompts.get("default", {}).get("template", "")
        self.assertIn("10,407.59亿元", default_template)

    def test_conversion_value_correct(self):
        value = 1040759 / 100
        self.assertAlmostEqual(value, 10407.59, places=2)
        self.assertNotAlmostEqual(value, 1040.76, places=2)


if __name__ == "__main__":
    unittest.main()
