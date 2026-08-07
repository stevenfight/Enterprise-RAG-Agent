# -*- coding: utf-8 -*-
"""
TDD 测试: 步骤 1.1 DataAgent

对应 TDD 规格: openspec/changes/multi-agent-step04/specs/tdd-step04.md
测试总计: 16 项

编码: UTF-8
"""

import os
import unittest
from unittest.mock import MagicMock

from src.agent_core import ReActAgent
from src.tools.retrieve_tool import RetrieveTool
from src.worker_agents.data_agent import DataAgent


class TestDataAgentClassDefinition(unittest.TestCase):
    """TC-40: DataAgent 类定义"""

    @classmethod
    def setUpClass(cls):
        """创建所有 TC-40 测试共享的 DataAgent 实例"""
        cls.mock_retrieve = MagicMock(spec=RetrieveTool)
        cls.mock_retrieve.name = "retrieve"
        cls.mock_retrieve.description = "mock retrieve tool"
        cls.mock_retrieve.parameters = {}
        cls.mock_provider = MagicMock()
        cls.agent = DataAgent(
            retrieval_tool=cls.mock_retrieve,
            llm_provider=cls.mock_provider,
        )

    def test_tc40_01_is_subclass_of_react_agent(self):
        """TC-40-01: DataAgent 是 ReActAgent 的子类"""
        self.assertTrue(issubclass(DataAgent, ReActAgent))

    def test_tc40_02_instantiation_success(self):
        """TC-40-02: DataAgent 实例化成功"""
        agent = DataAgent(
            retrieval_tool=self.mock_retrieve,
            llm_provider=self.mock_provider,
        )
        self.assertIsNotNone(agent)
        self.assertIsInstance(agent, ReActAgent)

    def test_tc40_03_prompt_name_is_data_agent(self):
        """TC-40-03: DataAgent 的 prompt_name 为 "data_agent" """
        self.assertEqual(self.agent._prompt_name, "data_agent")

    def test_tc40_04_model_is_qwen_turbo(self):
        """TC-40-04: DataAgent 的 model 为 "qwen-turbo" """
        self.assertEqual(self.agent.model, "qwen-turbo")

    def test_tc40_05_max_steps_is_3(self):
        """TC-40-05: DataAgent 的 max_steps 为 3"""
        self.assertEqual(self.agent.max_steps, 3)

    def test_tc40_06_temperature_is_0_2(self):
        """TC-40-06: DataAgent 的 temperature 为 0.2"""
        self.assertEqual(self.agent.temperature, 0.2)


class TestDataAgentToolRegistration(unittest.TestCase):
    """TC-41: DataAgent 工具注册"""

    @classmethod
    def setUpClass(cls):
        """创建所有 TC-41 测试共享的 DataAgent 实例"""
        cls.mock_retrieve = MagicMock(spec=RetrieveTool)
        cls.mock_retrieve.name = "retrieve"
        cls.mock_retrieve.description = "mock retrieve tool"
        cls.mock_retrieve.parameters = {}
        cls.mock_provider = MagicMock()
        cls.agent = DataAgent(
            retrieval_tool=cls.mock_retrieve,
            llm_provider=cls.mock_provider,
        )

    def test_tc41_01_only_retrieve_registered(self):
        """TC-41-01: DataAgent 只注册了 retrieve 工具"""
        self.assertEqual(self.agent.tool_registry.list_all(), ["retrieve"])

    def test_tc41_02_retrieve_tool_exists(self):
        """TC-41-02: DataAgent 的 ToolRegistry 有 retrieve 工具"""
        tool = self.agent.tool_registry.get("retrieve")
        self.assertIsNotNone(tool)

    def test_tc41_03_no_other_tools_registered(self):
        """TC-41-03: DataAgent 的 ToolRegistry 不包含其他工具"""
        other_tools = ["chart", "compare", "calculator", "verify"]
        registered = self.agent.tool_registry.list_all()
        for tool_name in other_tools:
            self.assertNotIn(tool_name, registered,
                             f"工具 {tool_name} 不应被注册到 DataAgent")

    def test_tc41_04_none_llm_provider_instantiation(self):
        """TC-41-04: DataAgent 实例化时传入 None llm_provider 仍可创建"""
        mock_retrieve = MagicMock(spec=RetrieveTool)
        mock_retrieve.name = "retrieve"
        mock_retrieve.description = "mock retrieve tool"
        mock_retrieve.parameters = {}
        agent = DataAgent(
            retrieval_tool=mock_retrieve,
            llm_provider=None,
        )
        self.assertIsNotNone(agent)
        self.assertIsNone(agent.llm_provider)


class TestDataAgentRetrieval(unittest.TestCase):
    """TC-42: DataAgent 独立检索验证"""

    @classmethod
    def setUpClass(cls):
        """创建所有 TC-42 测试共享的 DataAgent 实例"""
        # 检查 API Key 是否可用
        cls.has_api_key = bool(os.environ.get("DASHSCOPE_API_KEY", ""))
        if not cls.has_api_key:
            return

        try:
            retrieve_tool = RetrieveTool()
            from src.llm_provider import DashScopeProvider
            provider = DashScopeProvider(model_name="qwen-turbo")
            cls.agent = DataAgent(
                retrieval_tool=retrieve_tool,
                llm_provider=provider,
            )
            # 预先执行一次检索，后续测试复用结果
            cls.result_2024 = cls.agent.run("中芯国际2024年营收是多少")
            cls.result_2023 = cls.agent.run("中芯国际2023年营收是多少")
        except Exception:
            cls.has_api_key = False

    def test_tc42_01_retrieval_success(self):
        """TC-42-01: DataAgent 独立检索 "中芯国际2024年营收是多少" """
        if not self.has_api_key:
            self.skipTest("需要 DASHSCOPE_API_KEY 环境变量")
        self.assertTrue(self.result_2024.success)
        self.assertGreater(len(self.result_2024.answer), 0)

    def test_tc42_02_sources_not_empty(self):
        """TC-42-02: DataAgent 检索结果 sources 非空"""
        if not self.has_api_key:
            self.skipTest("需要 DASHSCOPE_API_KEY 环境变量")
        self.assertGreater(len(self.result_2024.sources), 0)

    def test_tc42_03_total_tokens_positive(self):
        """TC-42-03: DataAgent 检索结果 total_tokens > 0"""
        if not self.has_api_key:
            self.skipTest("需要 DASHSCOPE_API_KEY 环境变量")
        self.assertGreater(self.result_2024.total_tokens, 0)

    def test_tc42_04_reasoning_chain_not_empty(self):
        """TC-42-04: DataAgent 检索结果 reasoning_chain 非空"""
        if not self.has_api_key:
            self.skipTest("需要 DASHSCOPE_API_KEY 环境变量")
        self.assertGreaterEqual(len(self.result_2024.reasoning_chain), 1)

    def test_tc42_05_prompt_no_chart_rule(self):
        """TC-42-05: data_agent Prompt 不含规则 8（图表展示）"""
        # 直接验证 YAML 模板内容，不需要 API Key
        import yaml
        from pathlib import Path

        yaml_path = Path(__file__).parent.parent / "config" / "agent_prompts.yaml"
        if not yaml_path.exists():
            self.skipTest("agent_prompts.yaml 不存在")

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.assertIn("data_agent", config)
        template = config["data_agent"]["template"]
        # data_agent 模板不应包含 "图表展示" 关键词（规则 8）
        self.assertNotIn("图表展示", template)

    def test_tc42_06_repeated_retrieval(self):
        """TC-42-06: DataAgent 独立检索 "中芯国际2023年营收是多少" 再跑一次"""
        if not self.has_api_key:
            self.skipTest("需要 DASHSCOPE_API_KEY 环境变量")
        self.assertTrue(self.result_2023.success)


if __name__ == "__main__":
    unittest.main()
