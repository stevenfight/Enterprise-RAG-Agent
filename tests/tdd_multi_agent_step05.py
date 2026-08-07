# -*- coding: utf-8 -*-
"""
TDD 测试: 步骤 2.1 ~ 2.4 多 Agent 升级 - 阶段二 Orchestrator + 委托

对应 TDD 规格: openspec/changes/multi-agent-step05/specs/tdd-step05.md
测试总计: 28 项
  - TC-50 AgentCapability: 3 项
  - TC-51 AgentRegistry: 7 项
  - TC-52 SharedMemory: 6 项
  - TC-53 DelegateTool: 6 项（1 项需 API Key）
  - TC-54 OrchestratorAgent: 6 项（1 项需 API Key）

编码: UTF-8
"""

import os
import queue
import unittest
from unittest.mock import MagicMock

import pytest

from src.agent_core import AgentResult, ReActAgent
from src.agent_registry import AgentCapability, AgentRegistry
from src.shared_memory import SharedMemory
from src.tools import BaseTool, ToolResult
from src.tools.delegate_tool import DelegateTool
from src.orchestrator_agent import OrchestratorAgent


# ============================================================
# 网络连通性前置检查
# ============================================================

def _check_connectivity():
    """检查 dashscope API 网络连通性，不通则 pytest.skip"""
    try:
        import requests
        requests.get("https://dashscope.aliyuncs.com", timeout=3)
    except Exception:
        pytest.skip("网络不通，无法访问 dashscope.aliyuncs.com")


# ============================================================
# TC-50: AgentCapability（3 项）
# ============================================================

class TestAgentCapability(unittest.TestCase):
    """TC-50: AgentCapability 数据类"""

    def test_tc50_01_attributes_correct(self):
        """TC-50-01: AgentCapability 创建 - name/description/tools/max_parallel/llm_model 属性正确"""
        cap = AgentCapability(
            name="DataAgent",
            description="从向量数据库精确检索财务数据",
            tools=["retrieve"],
            max_parallel=3,
            llm_model="qwen-turbo",
        )
        self.assertEqual(cap.name, "DataAgent")
        self.assertEqual(cap.description, "从向量数据库精确检索财务数据")
        self.assertEqual(cap.tools, ["retrieve"])
        self.assertEqual(cap.max_parallel, 3)
        self.assertEqual(cap.llm_model, "qwen-turbo")

    def test_tc50_02_default_values(self):
        """TC-50-02: AgentCapability 创建 - 不传 tools/max_parallel/llm_model 时使用默认值"""
        cap = AgentCapability(
            name="CalcAgent",
            description="执行数值计算",
        )
        self.assertEqual(cap.name, "CalcAgent")
        self.assertEqual(cap.tools, [])
        self.assertEqual(cap.max_parallel, 1)
        self.assertEqual(cap.llm_model, "qwen-turbo")

    def test_tc50_03_tools_list_correct(self):
        """TC-50-03: AgentCapability 创建 - tools 为指定列表时正确保存"""
        tools = ["retrieve", "calculator", "compare"]
        cap = AgentCapability(
            name="HybridAgent",
            description="混合能力 Agent",
            tools=tools,
        )
        self.assertEqual(cap.tools, tools)
        self.assertEqual(len(cap.tools), 3)
        self.assertIn("retrieve", cap.tools)
        self.assertIn("calculator", cap.tools)
        self.assertIn("compare", cap.tools)


# ============================================================
# TC-51: AgentRegistry（7 项）
# ============================================================

class TestAgentRegistry(unittest.TestCase):
    """TC-51: AgentRegistry 注册表"""

    def test_tc51_01_register_success(self):
        """TC-51-01: AgentRegistry.register() 注册 AgentCapability 成功"""
        registry = AgentRegistry()
        cap = AgentCapability(
            name="DataAgent",
            description="数据检索 Agent",
            tools=["retrieve"],
        )
        registry.register(cap)
        # 注册后可通过 get 获取
        self.assertIsNotNone(registry.get("DataAgent"))

    def test_tc51_02_register_duplicate_raises(self):
        """TC-51-02: AgentRegistry.register() 重复注册同名 Agent 抛出 ValueError"""
        registry = AgentRegistry()
        cap = AgentCapability(name="DataAgent", description="数据检索 Agent")
        registry.register(cap)
        with self.assertRaises(ValueError) as ctx:
            registry.register(AgentCapability(name="DataAgent", description="重复注册"))
        self.assertIn("已注册", str(ctx.exception))

    def test_tc51_03_get_returns_capability(self):
        """TC-51-03: AgentRegistry.get() 返回已注册的 AgentCapability"""
        registry = AgentRegistry()
        original_cap = AgentCapability(
            name="DataAgent",
            description="从向量数据库检索",
            tools=["retrieve"],
            max_parallel=3,
        )
        registry.register(original_cap)
        fetched = registry.get("DataAgent")
        self.assertIsNotNone(fetched)
        self.assertIs(fetched, original_cap)
        self.assertEqual(fetched.name, "DataAgent")
        self.assertEqual(fetched.tools, ["retrieve"])
        self.assertEqual(fetched.max_parallel, 3)

    def test_tc51_04_get_unregistered_returns_none(self):
        """TC-51-04: AgentRegistry.get() 未注册名称返回 None"""
        registry = AgentRegistry()
        result = registry.get("NonExistentAgent")
        self.assertIsNone(result)

    def test_tc51_05_descriptions_contains_info(self):
        """TC-51-05: AgentRegistry.get_agent_descriptions() 包含 Agent 名称/描述/工具"""
        registry = AgentRegistry()
        registry.register(AgentCapability(
            name="DataAgent",
            description="从向量数据库精确检索财务数据",
            tools=["retrieve"],
        ))
        desc = registry.get_agent_descriptions()
        self.assertIn("DataAgent", desc)
        self.assertIn("从向量数据库精确检索财务数据", desc)
        self.assertIn("retrieve", desc)

    def test_tc51_06_descriptions_empty_registry(self):
        """TC-51-06: AgentRegistry.get_agent_descriptions() 空注册表返回"(没有可用的 Worker Agent)" """
        registry = AgentRegistry()
        desc = registry.get_agent_descriptions()
        self.assertEqual(desc, "(没有可用的 Worker Agent)")

    def test_tc51_07_list_all_returns_names(self):
        """TC-51-07: AgentRegistry.list_all() 返回所有已注册 Agent 名称"""
        registry = AgentRegistry()
        registry.register(AgentCapability(name="DataAgent", description="数据检索"))
        registry.register(AgentCapability(name="CalcAgent", description="计算"))
        registry.register(AgentCapability(name="ChartAgent", description="图表"))
        names = registry.list_all()
        self.assertEqual(len(names), 3)
        self.assertIn("DataAgent", names)
        self.assertIn("CalcAgent", names)
        self.assertIn("ChartAgent", names)


# ============================================================
# TC-52: SharedMemory（6 项）
# ============================================================

class TestSharedMemory(unittest.TestCase):
    """TC-52: SharedMemory 跨 Agent 共享记忆"""

    def _make_result(self, answer="测试答案", success=True, sources=None, tokens=100):
        """构造测试用 AgentResult"""
        return AgentResult(
            answer=answer,
            success=success,
            sources=sources or [],
            total_tokens=tokens,
        )

    def test_tc52_01_add_and_get_result(self):
        """TC-52-01: SharedMemory.add_agent_result() 写入后可 get_agent_result() 读取"""
        sm = SharedMemory()
        result = self._make_result(answer="中芯国际营收 495 亿元", tokens=200)
        sm.add_agent_result("DataAgent(中芯)", result)
        fetched = sm.get_agent_result("DataAgent(中芯)")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.answer, "中芯国际营收 495 亿元")
        self.assertEqual(fetched.total_tokens, 200)

    def test_tc52_02_get_context_for_returns_upstream(self):
        """TC-52-02: SharedMemory.get_context_for() 返回包含上游 Agent 结果的文本"""
        sm = SharedMemory()
        sm.add_agent_result("DataAgent(中芯)", self._make_result(answer="中芯营收 495 亿"))
        sm.add_agent_result("DataAgent(华虹)", self._make_result(answer="华虹营收 100 亿"))
        ctx = sm.get_context_for("CompareAgent", {})
        self.assertIn("DataAgent(中芯)", ctx)
        self.assertIn("中芯营收 495 亿", ctx)
        self.assertIn("DataAgent(华虹)", ctx)
        self.assertIn("华虹营收 100 亿", ctx)

    def test_tc52_03_get_all_sources_aggregates(self):
        """TC-52-03: SharedMemory.get_all_sources() 聚合所有 Agent 的 sources"""
        sm = SharedMemory()
        sources_1 = [{"source": "年报A", "page": 1}]
        sources_2 = [{"source": "年报B", "page": 5}, {"source": "年报C", "page": 8}]
        sm.add_agent_result("DataAgent(中芯)", self._make_result(sources=sources_1))
        sm.add_agent_result("DataAgent(华虹)", self._make_result(sources=sources_2))
        all_sources = sm.get_all_sources()
        self.assertEqual(len(all_sources), 3)
        sources_files = [s["source"] for s in all_sources]
        self.assertIn("年报A", sources_files)
        self.assertIn("年报B", sources_files)
        self.assertIn("年报C", sources_files)

    def test_tc52_04_get_total_tokens_aggregates(self):
        """TC-52-04: SharedMemory.get_total_tokens() 聚合所有 Agent 的 total_tokens"""
        sm = SharedMemory()
        sm.add_agent_result("DataAgent(中芯)", self._make_result(tokens=150))
        sm.add_agent_result("DataAgent(华虹)", self._make_result(tokens=250))
        sm.add_agent_result("DataAgent(中微)", self._make_result(tokens=80))
        total = sm.get_total_tokens()
        self.assertEqual(total, 480)

    def test_tc52_05_clear_empties_all(self):
        """TC-52-05: SharedMemory.clear() 清空所有数据"""
        sm = SharedMemory()
        sm.set_task_context("query", "三大运营商营收对比")
        sm.add_agent_result("DataAgent(中芯)", self._make_result(tokens=100))
        self.assertEqual(len(sm.agent_outputs), 1)
        self.assertEqual(sm.get_total_tokens(), 100)
        sm.clear()
        self.assertEqual(len(sm.agent_outputs), 0)
        self.assertEqual(sm.get_total_tokens(), 0)
        self.assertEqual(len(sm.execution_log), 0)
        self.assertIsNone(sm.get_task_context("query", default=None))

    def test_tc52_06_task_context_read_write(self):
        """TC-52-06: SharedMemory.set_task_context()/get_task_context() 读写正确"""
        sm = SharedMemory()
        sm.set_task_context("query", "三大运营商2024营收对比")
        sm.set_task_context("companies", ["中国移动", "中国联通", "中国电信"])
        self.assertEqual(sm.get_task_context("query"), "三大运营商2024营收对比")
        companies = sm.get_task_context("companies")
        self.assertEqual(len(companies), 3)
        self.assertIn("中国移动", companies)
        # 未设置的 key 返回默认值
        self.assertIsNone(sm.get_task_context("non_existent"))
        self.assertEqual(sm.get_task_context("non_existent", default="N/A"), "N/A")


# ============================================================
# TC-53: DelegateTool（6 项）
# ============================================================

class TestDelegateTool(unittest.TestCase):
    """TC-53: DelegateTool 委托工具"""

    def test_tc53_01_attributes_correct(self):
        """TC-53-01: DelegateTool 实例化 - name/description/parameters 属性正确"""
        registry = AgentRegistry()
        sm = SharedMemory()
        tool = DelegateTool(agent_registry=registry, shared_memory=sm)
        self.assertEqual(tool.name, "delegate")
        self.assertIn("委托", tool.description)
        self.assertIn("tasks", tool.parameters["properties"])
        self.assertIn("tasks", tool.parameters["required"])

    def test_tc53_02_empty_tasks_returns_failure(self):
        """TC-53-02: DelegateTool.run(tasks=[]) 空任务返回失败结果"""
        registry = AgentRegistry()
        sm = SharedMemory()
        tool = DelegateTool(agent_registry=registry, shared_memory=sm)
        result = tool.run(tasks=[])
        self.assertIsInstance(result, ToolResult)
        self.assertFalse(result.success)
        self.assertIn("空", result.error)

    def test_tc53_03_unknown_agent_returns_failure_in_results(self):
        """TC-53-03: DelegateTool.run() 未知 Agent 名称返回失败结果（在 results 列表中标记）"""
        registry = AgentRegistry()
        sm = SharedMemory()
        tool = DelegateTool(agent_registry=registry, shared_memory=sm)
        # 未注册任何 Agent，直接委托 DataAgent
        result = tool.run(tasks=[
            {"agent": "DataAgent", "task": "中芯国际2024营收", "company_name": "中芯国际"},
        ])
        # 整体 run 返回 success=True（委托执行流程完成），但 results 内该项 success=False
        self.assertTrue(result.success)
        results_list = result.data["results"]
        self.assertEqual(len(results_list), 1)
        self.assertFalse(results_list[0]["success"])
        self.assertIn("未注册", results_list[0]["error"])

    def test_tc53_04_delegate_data_agent_retrieval(self):
        """TC-53-04: DelegateTool.run() 委托 DataAgent 执行检索 (需要 API Key，无 Key 时 skip)"""
        _check_connectivity()
        if not os.environ.get("DASHSCOPE_API_KEY"):
            self.skipTest("需要 DASHSCOPE_API_KEY 环境变量")

        registry = AgentRegistry()
        registry.register(AgentCapability(
            name="DataAgent",
            description="从向量数据库精确检索财务数据",
            tools=["retrieve"],
            max_parallel=3,
            llm_model="qwen-turbo",
        ))
        sm = SharedMemory()
        tool = DelegateTool(agent_registry=registry, shared_memory=sm)
        result = tool.run(tasks=[
            {"agent": "DataAgent", "task": "中芯国际2024年营收是多少", "company_name": "中芯国际"},
        ])
        self.assertTrue(result.success)
        self.assertEqual(len(result.data["results"]), 1)
        worker_result = result.data["results"][0]
        self.assertTrue(worker_result["success"])
        self.assertGreater(len(worker_result["answer"]), 0)

    def test_tc53_05_result_written_to_shared_memory(self):
        """TC-53-05: DelegateTool.run() 执行后结果写入 SharedMemory

        使用 Mock Worker 验证写入逻辑（无需 API Key）。
        通过 monkey patch 替换 DelegateTool._create_agent 返回 Mock Agent。
        """
        registry = AgentRegistry()
        registry.register(AgentCapability(
            name="DataAgent",
            description="数据检索",
            tools=["retrieve"],
        ))
        sm = SharedMemory()
        tool = DelegateTool(agent_registry=registry, shared_memory=sm)

        # 构造 Mock Worker Agent，返回固定 AgentResult
        mock_worker = MagicMock()
        mock_result = AgentResult(
            answer="中芯国际2024年营收 495 亿元",
            success=True,
            total_steps=2,
            total_tokens=180,
            sources=[{"source": "中芯国际2024年报", "page": 12}],
        )
        mock_worker.run.return_value = mock_result
        # 替换 _create_agent 方法
        tool._create_agent = lambda cap, step_callback=None: mock_worker

        result = tool.run(tasks=[
            {"agent": "DataAgent", "task": "中芯国际2024年营收", "company_name": "中芯国际"},
        ])
        self.assertTrue(result.success)

        # 验证 SharedMemory 中已写入结果
        sm_result = sm.get_agent_result("DataAgent(中芯国际)")
        self.assertIsNotNone(sm_result)
        self.assertEqual(sm_result.answer, "中芯国际2024年营收 495 亿元")
        self.assertTrue(sm_result.success)
        self.assertEqual(sm_result.total_tokens, 180)
        # 验证来源聚合
        all_sources = sm.get_all_sources()
        self.assertEqual(len(all_sources), 1)
        self.assertEqual(all_sources[0]["source"], "中芯国际2024年报")
        # 验证 Token 聚合
        self.assertEqual(sm.get_total_tokens(), 180)

    def test_tc53_06_event_queue_receives_worker_step(self):
        """TC-53-06: DelegateTool 传入 event_queue 时 worker_step 事件正确推送

        验证 _DelegateStepCallback 推送事件到队列。
        """
        registry = AgentRegistry()
        sm = SharedMemory()
        event_queue = queue.Queue()
        tool = DelegateTool(
            agent_registry=registry,
            shared_memory=sm,
            event_queue=event_queue,
        )

        # 通过 Mock Worker 触发 step_callback（模拟）
        # 直接验证 _DelegateStepCallback 行为
        from src.tools.delegate_tool import _DelegateStepCallback
        cb = _DelegateStepCallback(agent_name="DataAgent(中芯)", event_queue=event_queue)
        cb("thought", {"content": "正在检索中芯国际营收"})
        cb("observation", {"content": "找到 5 条相关结果"})

        # 队列中应有两个事件
        self.assertEqual(event_queue.qsize(), 2)
        event1 = event_queue.get_nowait()
        event2 = event_queue.get_nowait()
        self.assertEqual(event1["type"], "worker_step")
        self.assertEqual(event1["agent"], "DataAgent(中芯)")
        self.assertEqual(event1["step_type"], "thought")
        self.assertIn("content", event1["data"])
        self.assertEqual(event2["step_type"], "observation")
        self.assertIn("timestamp", event1)
        self.assertIn("timestamp", event2)


# ============================================================
# TC-54: OrchestratorAgent（6 项）
# ============================================================

class TestOrchestratorAgent(unittest.TestCase):
    """TC-54: OrchestratorAgent 主控 Agent"""

    def _make_orchestrator(self, llm_provider=None):
        """构造测试用 OrchestratorAgent（无需 API Key 也能创建）"""
        registry = AgentRegistry()
        registry.register(AgentCapability(
            name="DataAgent",
            description="从向量数据库精确检索财务数据，支持指定公司名称",
            tools=["retrieve"],
            max_parallel=3,
            llm_model="qwen-turbo",
        ))
        sm = SharedMemory()
        delegate_tool = DelegateTool(
            agent_registry=registry,
            shared_memory=sm,
        )
        orchestrator = OrchestratorAgent(
            delegate_tool=delegate_tool,
            agent_registry=registry,
            llm_provider=llm_provider,
            shared_memory=sm,
        )
        return orchestrator, registry, sm

    def test_tc54_01_attributes_correct(self):
        """TC-54-01: OrchestratorAgent 创建 - 所有属性正确设置"""
        mock_provider = MagicMock()
        orchestrator, registry, sm = self._make_orchestrator(llm_provider=mock_provider)
        # 基本属性
        self.assertIsNotNone(orchestrator)
        self.assertIsInstance(orchestrator, ReActAgent)
        # 引用关系
        self.assertIs(orchestrator.agent_registry, registry)
        self.assertIs(orchestrator.shared_memory, sm)
        # LLM 配置
        self.assertEqual(orchestrator.model, "qwen-max")
        self.assertEqual(orchestrator.temperature, 0.3)
        self.assertEqual(orchestrator.max_steps, 10)
        self.assertEqual(orchestrator.llm_timeout, 120)
        self.assertEqual(orchestrator._prompt_name, "orchestrator")

    def test_tc54_02_tool_registry_only_delegate(self):
        """TC-54-02: OrchestratorAgent.tool_registry 只包含 delegate 工具"""
        orchestrator, _, _ = self._make_orchestrator()
        registered_tools = orchestrator.tool_registry.list_all()
        self.assertEqual(registered_tools, ["delegate"])
        # 不应包含其他工具
        for tool_name in ["retrieve", "calculator", "compare", "chart", "verify"]:
            self.assertNotIn(tool_name, registered_tools)

    def test_tc54_03_agent_descriptions_contains_info(self):
        """TC-54-03: OrchestratorAgent._agent_descriptions 包含已注册 Agent 信息"""
        orchestrator, registry, _ = self._make_orchestrator()
        desc = orchestrator._agent_descriptions
        # 与 registry.get_agent_descriptions() 一致
        self.assertEqual(desc, registry.get_agent_descriptions())
        # 包含 DataAgent 信息
        self.assertIn("DataAgent", desc)
        self.assertIn("retrieve", desc)

    def test_tc54_04_run_multi_agent_chain(self):
        """TC-54-04: OrchestratorAgent.run() 多 Agent 链路 (需要 API Key，无 Key 时 skip)"""
        _check_connectivity()
        if not os.environ.get("DASHSCOPE_API_KEY"):
            self.skipTest("需要 DASHSCOPE_API_KEY 环境变量")

        from src.llm_provider import DashScopeProvider
        provider = DashScopeProvider(api_key=os.environ["DASHSCOPE_API_KEY"])

        registry = AgentRegistry()
        registry.register(AgentCapability(
            name="DataAgent",
            description="从向量数据库精确检索财务数据，支持指定公司名称",
            tools=["retrieve"],
            max_parallel=3,
            llm_model="qwen-turbo",
        ))
        sm = SharedMemory()
        sm.set_task_context("query", "三大运营商2024年营收对比")
        delegate_tool = DelegateTool(
            agent_registry=registry,
            shared_memory=sm,
        )
        orchestrator = OrchestratorAgent(
            delegate_tool=delegate_tool,
            agent_registry=registry,
            llm_provider=provider,
            shared_memory=sm,
        )
        result = orchestrator.run("三大运营商2024年营收对比")
        # 结果对象基本断言
        self.assertIsInstance(result, AgentResult)
        self.assertTrue(result.success)
        self.assertGreater(len(result.answer), 0)
        # SharedMemory 中应有 Worker 写入结果
        self.assertGreaterEqual(len(sm.agent_outputs), 1)

    def test_tc54_05_constructor_args_passed_to_react_agent(self):
        """TC-54-05: OrchestratorAgent 构造函数参数正确传递给 ReActAgent"""
        mock_provider = MagicMock()
        orchestrator, _, _ = self._make_orchestrator(llm_provider=mock_provider)
        # 验证传递给 ReActAgent 的参数
        self.assertEqual(orchestrator.model, "qwen-max")
        self.assertEqual(orchestrator.temperature, 0.3)
        self.assertEqual(orchestrator.max_steps, 10)
        self.assertEqual(orchestrator.llm_timeout, 120)
        self.assertEqual(orchestrator.llm_provider, mock_provider)
        self.assertEqual(orchestrator._prompt_name, "orchestrator")

    def test_tc54_06_instantiation_without_llm_provider(self):
        """TC-54-06: OrchestratorAgent 不带 llm_provider 也能创建（走 dashscope 直调）"""
        # 不传 llm_provider，仍应能创建（运行时走 dashscope 直调）
        orchestrator, _, _ = self._make_orchestrator(llm_provider=None)
        self.assertIsNotNone(orchestrator)
        self.assertIsInstance(orchestrator, ReActAgent)
        self.assertIsNone(orchestrator.llm_provider)
        # 但属性仍正确
        self.assertEqual(orchestrator._prompt_name, "orchestrator")
        self.assertEqual(orchestrator.model, "qwen-max")


if __name__ == "__main__":
    unittest.main()
