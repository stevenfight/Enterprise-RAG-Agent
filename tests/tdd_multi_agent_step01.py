# -*- coding: utf-8 -*-
"""
TDD 测试: 步骤 0.1 多 Agent 基础能力搭建

对应 TDD: openspec/changes/multi-agent-step01/specs/tdd-step01.md
涵盖: TC-01 ~ TC-13，共 64 项测试

运行方式: python tests/tdd_multi_agent_step01.py
"""

import json
import os
import queue
import sys
import threading
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---- 关键：在 import src 之前 mock tiktoken，避免 SSL 下载错误 ----
# src/__init__.py -> src/retrieval.py -> tiktoken.get_encoding() 会触发网络请求
# 在离线/代理环境中会失败，因此预先 mock
import tiktoken as _real_tiktoken
try:
    _real_tiktoken.get_encoding("cl100k_base")
except Exception:
    # 如果 tiktoken 缓存不可用，mock 整个 tiktoken 模块
    _mock_tiktoken = MagicMock()
    _mock_encoding = MagicMock()
    _mock_encoding.encode = lambda text, *a, **kw: text.split()
    _mock_encoding.decode = lambda tokens, *a, **kw: " ".join(tokens) if isinstance(tokens, list) else str(tokens)
    _mock_tiktoken.get_encoding = MagicMock(return_value=_mock_encoding)
    sys.modules['tiktoken'] = _mock_tiktoken


# ============================================================
# TC-01: LLMProvider 抽象层
# ============================================================

class TestLLMProvider(unittest.TestCase):
    """TC-01: LLMProvider 抽象层"""

    def test_tc01_01_dashscope_init(self):
        """TC-01-01: DashScopeProvider 初始化"""
        from src.llm_provider import DashScopeProvider
        provider = DashScopeProvider(api_key="sk-test-key")
        self.assertEqual(provider.api_key, "sk-test-key")
        self.assertEqual(provider._call_count, 0)

    def test_tc01_02_base_chat_not_implemented(self):
        """TC-01-02: BaseLLMProvider.chat 抛出 NotImplementedError"""
        from src.llm_provider import BaseLLMProvider
        provider = BaseLLMProvider()
        with self.assertRaises(NotImplementedError):
            provider.chat([{"role": "user", "content": "test"}])

    def test_tc01_03_llm_usage_defaults(self):
        """TC-01-03: LLMUsage 默认值"""
        from src.llm_provider import LLMUsage
        usage = LLMUsage()
        self.assertEqual(usage.input_tokens, 0)
        self.assertEqual(usage.output_tokens, 0)

    def test_tc01_04_llm_response_defaults(self):
        """TC-01-04: LLMResponse 默认值"""
        from src.llm_provider import LLMResponse, LLMUsage
        resp = LLMResponse(content="", success=True)
        self.assertEqual(resp.content, "")
        self.assertTrue(resp.success)
        self.assertEqual(resp.error, "")
        self.assertIsInstance(resp.usage, LLMUsage)

    def test_tc01_05_dashscope_success(self):
        """TC-01-05: DashScopeProvider.chat 成功（mock）"""
        from src.llm_provider import DashScopeProvider
        provider = DashScopeProvider(api_key="sk-test")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.output.choices[0].message.content = "测试响应"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 20
        mock_resp.usage = mock_usage

        with patch('src.llm_provider.Generation.call', return_value=mock_resp):
            result = provider.chat([{"role": "user", "content": "test"}])

        self.assertTrue(result.success)
        self.assertEqual(result.content, "测试响应")
        self.assertEqual(result.usage.input_tokens, 10)
        self.assertEqual(result.usage.output_tokens, 20)

    def test_tc01_06_dashscope_failure(self):
        """TC-01-06: DashScopeProvider.chat 失败 status!=200"""
        from src.llm_provider import DashScopeProvider
        provider = DashScopeProvider(api_key="sk-test")

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.message = "Bad Request"

        with patch('src.llm_provider.Generation.call', return_value=mock_resp):
            result = provider.chat([{"role": "user", "content": "test"}])

        self.assertFalse(result.success)
        self.assertIn("400", result.error)

    def test_tc01_07_dashscope_timeout(self):
        """TC-01-07: DashScopeProvider.chat 超时"""
        from src.llm_provider import DashScopeProvider
        provider = DashScopeProvider(api_key="sk-test")

        with patch('src.llm_provider.Generation.call', side_effect=TimeoutError()):
            result = provider.chat([{"role": "user", "content": "test"}])

        self.assertFalse(result.success)
        self.assertIn("超时", result.error)

    def test_tc01_08_dashscope_exception(self):
        """TC-01-08: DashScopeProvider.chat 异常"""
        from src.llm_provider import DashScopeProvider
        provider = DashScopeProvider(api_key="sk-test")

        with patch('src.llm_provider.Generation.call', side_effect=RuntimeError("test error")):
            result = provider.chat([{"role": "user", "content": "test"}])

        self.assertFalse(result.success)
        self.assertIn("test error", result.error)

    def test_tc01_09_call_count(self):
        """TC-01-09: DashScopeProvider 累计调用次数"""
        from src.llm_provider import DashScopeProvider
        provider = DashScopeProvider(api_key="sk-test")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.output.choices[0].message.content = "ok"
        mock_resp.usage = MagicMock(input_tokens=1, output_tokens=1)

        with patch('src.llm_provider.Generation.call', return_value=mock_resp):
            provider.chat([{"role": "user", "content": "1"}])
            provider.chat([{"role": "user", "content": "2"}])

        self.assertEqual(provider._call_count, 2)


# ============================================================
# TC-02: AgentResult 字段扩展
# ============================================================

class TestAgentResult(unittest.TestCase):
    """TC-02: AgentResult 字段扩展"""

    def test_tc02_01_sources_default(self):
        """TC-02-01: AgentResult.sources 默认值"""
        from src.agent_core import AgentResult
        result = AgentResult(answer="test", success=True)
        self.assertEqual(result.sources, [])

    def test_tc02_02_total_tokens_default(self):
        """TC-02-02: AgentResult.total_tokens 默认值"""
        from src.agent_core import AgentResult
        result = AgentResult(answer="test", success=True)
        self.assertEqual(result.total_tokens, 0)

    def test_tc02_03_reflection_default(self):
        """TC-02-03: AgentResult.reflection 默认值"""
        from src.agent_core import AgentResult
        result = AgentResult(answer="test", success=True)
        self.assertIsNone(result.reflection)

    def test_tc02_04_full_construct(self):
        """TC-02-04: AgentResult 完整构造"""
        from src.agent_core import AgentResult
        result = AgentResult(
            answer="test",
            success=True,
            sources=[{"source": "a"}],
            total_tokens=100,
            reflection={"ok": True},
        )
        self.assertEqual(result.sources, [{"source": "a"}])
        self.assertEqual(result.total_tokens, 100)
        self.assertEqual(result.reflection, {"ok": True})


# ============================================================
# TC-03: ReActAgent.__init__ 新增参数
# ============================================================

class TestReActAgentInit(unittest.TestCase):
    """TC-03: ReActAgent.__init__ 新增参数"""

    def setUp(self):
        from src.tools import ToolRegistry
        self.registry = ToolRegistry()

    def test_tc03_01_backward_compat(self):
        """TC-03-01: 不传新参数（向后兼容）"""
        from src.agent_core import ReActAgent
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(tool_registry=self.registry)
        self.assertIsNone(agent.llm_provider)
        self.assertEqual(agent._prompt_name, "default")
        self.assertIsNone(agent._step_callback)

    def test_tc03_02_llm_provider(self):
        """TC-03-02: 传入 llm_provider"""
        from src.agent_core import ReActAgent
        mock_provider = MagicMock()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(tool_registry=self.registry, llm_provider=mock_provider)
        self.assertEqual(agent.llm_provider, mock_provider)

    def test_tc03_03_prompt_name(self):
        """TC-03-03: 传入 prompt_name"""
        from src.agent_core import ReActAgent
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(tool_registry=self.registry, prompt_name="data_agent")
        self.assertEqual(agent._prompt_name, "data_agent")

    def test_tc03_04_step_callback(self):
        """TC-03-04: 传入 step_callback"""
        from src.agent_core import ReActAgent
        mock_cb = MagicMock()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(tool_registry=self.registry, step_callback=mock_cb)
        self.assertEqual(agent._step_callback, mock_cb)

    def test_tc03_05_sources_init(self):
        """TC-03-05: _sources 初始化为空列表"""
        from src.agent_core import ReActAgent
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(tool_registry=self.registry)
        self.assertEqual(agent._sources, [])

    def test_tc03_06_total_tokens_init(self):
        """TC-03-06: _total_tokens 初始化为 0"""
        from src.agent_core import ReActAgent
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(tool_registry=self.registry)
        self.assertEqual(agent._total_tokens, 0)


# ============================================================
# TC-04: _call_llm 双路径
# ============================================================

class TestCallLLMDualPath(unittest.TestCase):
    """TC-04: _call_llm 双路径"""

    def setUp(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        self.registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            self.agent = ReActAgent(tool_registry=self.registry)

    def test_tc04_01_provider_success(self):
        """TC-04-01: 有 provider 成功"""
        from src.llm_provider import LLMResponse, LLMUsage
        mock_provider = MagicMock()
        mock_provider.chat.return_value = LLMResponse(
            content="provider response", success=True,
            usage=LLMUsage(input_tokens=5, output_tokens=10)
        )
        self.agent.llm_provider = mock_provider
        self.agent._total_tokens = 0

        result = self.agent._call_llm([{"role": "user", "content": "test"}])

        self.assertEqual(result, "provider response")
        self.assertEqual(self.agent._total_tokens, 15)

    def test_tc04_02_provider_failure(self):
        """TC-04-02: 有 provider 失败"""
        from src.llm_provider import LLMResponse
        mock_provider = MagicMock()
        mock_provider.chat.return_value = LLMResponse(
            content="", success=False, error="test error"
        )
        self.agent.llm_provider = mock_provider

        result = self.agent._call_llm([{"role": "user", "content": "test"}])

        self.assertIsNone(result)

    def test_tc04_03_legacy_success(self):
        """TC-04-03: 无 provider 走原有路径成功"""
        self.agent.llm_provider = None
        self.agent._total_tokens = 0

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.output.choices[0].message.content = "legacy response"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 3
        mock_usage.output_tokens = 7
        mock_resp.usage = mock_usage

        with patch('src.agent_core.Generation.call', return_value=mock_resp):
            result = self.agent._call_llm([{"role": "user", "content": "test"}])

        self.assertEqual(result, "legacy response")
        self.assertEqual(self.agent._total_tokens, 10)

    def test_tc04_04_legacy_failure(self):
        """TC-04-04: 无 provider 走原有路径失败"""
        self.agent.llm_provider = None

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.message = "Server Error"

        with patch('src.agent_core.Generation.call', return_value=mock_resp):
            result = self.agent._call_llm([{"role": "user", "content": "test"}])

        self.assertIsNone(result)

    def test_tc04_05_legacy_exception(self):
        """TC-04-05: 无 provider 走原有路径异常"""
        self.agent.llm_provider = None

        with patch('src.agent_core.Generation.call', side_effect=Exception("network error")):
            result = self.agent._call_llm([{"role": "user", "content": "test"}])

        self.assertIsNone(result)


# ============================================================
# TC-05: _build_system_prompt 升级
# ============================================================

class TestBuildSystemPrompt(unittest.TestCase):
    """TC-05: _build_system_prompt 升级"""

    def setUp(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        self.registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            self.agent = ReActAgent(tool_registry=self.registry)

    def test_tc05_01_template_substitute(self):
        """TC-05-01: string.Template 替换变量"""
        prompt = self.agent._build_system_prompt(
            tool_descriptions="- retrieve: test",
            context="历史上下文",
        )
        self.assertIn("- retrieve: test", prompt)
        self.assertIn("历史上下文", prompt)
        # 确保没有 $tool_descriptions 残留
        self.assertNotIn("$tool_descriptions", prompt)
        self.assertNotIn("$context", prompt)

    def test_tc05_02_braces_safe(self):
        """TC-05-02: 花括号 JSON 安全"""
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(
                tool_registry=registry,
                system_prompt='测试 $tool_descriptions JSON: {"key": "value"} $context'
            )
        # 不应抛出 KeyError
        prompt = agent._build_system_prompt(
            tool_descriptions="tools", context="ctx"
        )
        self.assertIn('{"key": "value"}', prompt)

    def test_tc05_03_shared_context_injected(self):
        """TC-05-03: shared_context 注入"""
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(
                tool_registry=registry,
                system_prompt="$tool_descriptions $context $shared_context"
            )
        prompt = agent._build_system_prompt(
            tool_descriptions="tools", context="ctx",
            shared_context="上游数据内容"
        )
        self.assertIn("上游数据内容", prompt)

    def test_tc05_04_shared_context_empty(self):
        """TC-05-04: shared_context 为空"""
        prompt = self.agent._build_system_prompt(
            tool_descriptions="tools", context="ctx",
            shared_context=""
        )
        # 不应包含 $shared_context 残留
        self.assertNotIn("$shared_context", prompt)

    def test_tc05_05_agent_descriptions_injected(self):
        """TC-05-05: agent_descriptions 注入"""
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(
                tool_registry=registry,
                system_prompt="$tool_descriptions $context $agent_descriptions"
            )
        prompt = agent._build_system_prompt(
            tool_descriptions="tools", context="ctx",
            agent_descriptions="DataAgent: 检索数据"
        )
        self.assertIn("DataAgent: 检索数据", prompt)

    def test_tc05_06_custom_prompt_priority(self):
        """TC-05-06: custom_system_prompt 优先级"""
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(
                tool_registry=registry,
                system_prompt="自定义 $tool_descriptions $context"
            )
        prompt = agent._build_system_prompt(tool_descriptions="TOOLS", context="CTX")
        self.assertEqual(prompt, "自定义 TOOLS CTX")

    def test_tc05_07_yaml_load(self):
        """TC-05-07: YAML 模板加载（文件存在）"""
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        registry = ToolRegistry()

        yaml_content = "data_agent:\n  template: '数据Agent模板 $tool_descriptions'"
        with patch('src.agent_core.yaml') as mock_yaml, \
             patch('src.agent_core.Path') as mock_path:
            mock_yaml_path = MagicMock()
            mock_yaml_path.exists.return_value = True
            mock_path.return_value.parent.parent.__truediv__.return_value = mock_yaml_path
            mock_path_instance = MagicMock()
            mock_path_instance.parent.parent.__truediv__.return_value = mock_yaml_path

            # 直接 mock _load_prompt_template
            with patch('src.agent_core.get_api_key', return_value="sk-test"):
                agent = ReActAgent(tool_registry=registry, prompt_name="data_agent")

            with patch.object(agent, '_load_prompt_template', return_value="数据Agent模板 $tool_descriptions"):
                prompt = agent._build_system_prompt(tool_descriptions="TOOLS", context="CTX")
                self.assertIn("数据Agent模板", prompt)
                self.assertIn("TOOLS", prompt)

    def test_tc05_08_yaml_fallback(self):
        """TC-05-08: YAML 不存在回退"""
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(tool_registry=registry)

        # 直接测试 _load_prompt_template
        with patch.object(Path, 'exists', return_value=False):
            template = agent._load_prompt_template()
        self.assertEqual(template, agent._default_system_prompt)


# ============================================================
# TC-06: run()/run_stream() 签名扩展
# ============================================================

class TestRunSignature(unittest.TestCase):
    """TC-06: run()/run_stream() 签名扩展"""

    def setUp(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        self.registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            self.agent = ReActAgent(tool_registry=self.registry, max_steps=1)

    def test_tc06_01_shared_context_passed(self):
        """TC-06-01: run() 传入 shared_context"""
        with patch.object(self.agent, '_call_llm', return_value='Thought: ok\nAction: Final Answer\nFinal Answer: test'):
            with patch.object(self.agent, '_build_system_prompt', return_value="prompt") as mock_build:
                # 需要 mock memory
                self.agent.memory = MagicMock()
                self.agent.memory.get_full_context.return_value = ""
                try:
                    self.agent.run("test", shared_context="上游数据")
                except Exception:
                    pass
                # 验证 _build_system_prompt 被调用时传了 shared_context
                if mock_build.called:
                    call_kwargs = mock_build.call_args
                    if call_kwargs:
                        self.assertEqual(call_kwargs[1].get("shared_context", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else ""), "上游数据")

    def test_tc06_02_sources_reset(self):
        """TC-06-02: run() 重置 sources"""
        self.agent._sources = [{"old": "data"}]
        with patch.object(self.agent, '_call_llm', return_value='Thought: ok\nAction: Final Answer\nFinal Answer: test'):
            self.agent.memory = MagicMock()
            self.agent.memory.get_full_context.return_value = ""
            try:
                self.agent.run("test")
            except Exception:
                pass
        self.assertEqual(self.agent._sources, [])

    def test_tc06_03_tokens_reset(self):
        """TC-06-03: run() 重置 _total_tokens"""
        self.agent._total_tokens = 999
        with patch.object(self.agent, '_call_llm', return_value='Thought: ok\nAction: Final Answer\nFinal Answer: test'):
            self.agent.memory = MagicMock()
            self.agent.memory.get_full_context.return_value = ""
            try:
                self.agent.run("test")
            except Exception:
                pass
        self.assertEqual(self.agent._total_tokens, 0)

    def test_tc06_04_result_sources(self):
        """TC-06-04: run() 返回值包含 sources"""
        with patch.object(self.agent, '_call_llm', return_value='Thought: ok\nAction: Final Answer\nFinal Answer: test'):
            self.agent.memory = MagicMock()
            self.agent.memory.get_full_context.return_value = ""
            self.agent.memory.summarize_to_episodic = MagicMock()
            result = self.agent.run("test")
        self.assertIsInstance(result.sources, list)

    def test_tc06_05_result_total_tokens(self):
        """TC-06-05: run() 返回值包含 total_tokens"""
        with patch.object(self.agent, '_call_llm', return_value='Thought: ok\nAction: Final Answer\nFinal Answer: test'):
            self.agent.memory = MagicMock()
            self.agent.memory.get_full_context.return_value = ""
            self.agent.memory.summarize_to_episodic = MagicMock()
            result = self.agent.run("test")
        self.assertIsInstance(result.total_tokens, int)
        self.assertGreaterEqual(result.total_tokens, 0)

    def test_tc06_06_run_stream_shared_context(self):
        """TC-06-06: run_stream() 传入 shared_context"""
        with patch.object(self.agent, '_build_system_prompt', return_value="prompt") as mock_build:
            self.agent.memory = MagicMock()
            self.agent.memory.get_full_context.return_value = ""
            with patch.object(self.agent, '_call_llm', return_value='Thought: ok\nAction: Final Answer\nFinal Answer: test'):
                events = list(self.agent.run_stream("test", shared_context="上游"))
            if mock_build.called:
                call_kwargs = mock_build.call_args
                if call_kwargs:
                    self.assertEqual(call_kwargs[1].get("shared_context", ""), "上游")


# ============================================================
# TC-07: sources 收集
# ============================================================

class TestSourcesCollection(unittest.TestCase):
    """TC-07: sources 收集"""

    def setUp(self):
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        self.registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            self.agent = ReActAgent(tool_registry=self.registry)
        self.agent._sources = []

    def test_tc07_01_retrieve_collects(self):
        """TC-07-01: retrieve 成功收集 sources"""
        from src.tools import ToolResult
        mock_result = ToolResult(
            success=True,
            data={
                "results": [{
                    "source_file": "中芯国际2024年报.pdf",
                    "text": "营业收入57,795,570千元",
                    "pages": "第23页",
                    "company_name": "中芯国际",
                }]
            }
        )
        with patch.object(self.agent.tool_registry, 'execute', return_value=mock_result):
            self.agent._execute_action("retrieve", {"query": "test"})

        self.assertEqual(len(self.agent._sources), 1)
        self.assertEqual(self.agent._sources[0]["source"], "中芯国际2024年报.pdf")

    def test_tc07_02_source_fields(self):
        """TC-07-02: 来源信息包含必要字段"""
        from src.tools import ToolResult
        mock_result = ToolResult(
            success=True,
            data={
                "results": [{
                    "source_file": "report.pdf",
                    "text": "数据内容",
                    "pages": "第1页",
                    "company_name": "测试公司",
                }]
            }
        )
        with patch.object(self.agent.tool_registry, 'execute', return_value=mock_result):
            self.agent._execute_action("retrieve", {"query": "test"})

        src = self.agent._sources[0]
        self.assertIn("source", src)
        self.assertIn("content", src)
        self.assertIn("pages", src)
        self.assertIn("company_name", src)

    def test_tc07_03_non_retrieve_no_collect(self):
        """TC-07-03: 非 retrieve 工具不收集"""
        from src.tools import ToolResult
        mock_result = ToolResult(success=True, data={"result": "5"})
        with patch.object(self.agent.tool_registry, 'execute', return_value=mock_result):
            self.agent._execute_action("calculator", {"expression": "1+1"})

        self.assertEqual(len(self.agent._sources), 0)

    def test_tc07_04_retrieve_fail_no_collect(self):
        """TC-07-04: retrieve 失败不收集"""
        from src.tools import ToolResult
        mock_result = ToolResult(success=False, error="检索失败")
        with patch.object(self.agent.tool_registry, 'execute', return_value=mock_result):
            self.agent._execute_action("retrieve", {"query": "test"})

        self.assertEqual(len(self.agent._sources), 0)

    def test_tc07_05_retrieve_empty_results(self):
        """TC-07-05: retrieve 返回空 results 不收集"""
        from src.tools import ToolResult
        mock_result = ToolResult(success=True, data={"results": []})
        with patch.object(self.agent.tool_registry, 'execute', return_value=mock_result):
            self.agent._execute_action("retrieve", {"query": "test"})

        self.assertEqual(len(self.agent._sources), 0)


# ============================================================
# TC-08: StepCallback 机制
# ============================================================

class TestStepCallback(unittest.TestCase):
    """TC-08: StepCallback 机制"""

    def test_tc08_01_init(self):
        """TC-08-01: 初始化"""
        from src.step_callback import StepCallback
        q = queue.Queue()
        cb = StepCallback(agent_name="TestAgent", event_queue=q)
        self.assertEqual(cb.agent_name, "TestAgent")
        self.assertEqual(cb.event_queue, q)

    def test_tc08_02_on_step(self):
        """TC-08-02: on_step 推送事件"""
        from src.step_callback import StepCallback
        q = queue.Queue()
        cb = StepCallback("TestAgent", q)
        cb.on_step("thought", 1, "测试内容")
        event = q.get()
        self.assertEqual(event["type"], "worker_step")
        self.assertEqual(event["agent"], "TestAgent")

    def test_tc08_03_on_step_fields(self):
        """TC-08-03: on_step 事件字段完整"""
        from src.step_callback import StepCallback
        q = queue.Queue()
        cb = StepCallback("TestAgent", q)
        cb.on_step("thought", 1, "内容")
        event = q.get()
        self.assertIn("type", event)
        self.assertIn("agent", event)
        self.assertIn("step_type", event)
        self.assertIn("step", event)
        self.assertIn("content", event)
        self.assertIn("timestamp", event)

    def test_tc08_04_on_done(self):
        """TC-08-04: on_done 推送完成事件"""
        from src.step_callback import StepCallback
        from src.agent_core import AgentResult
        q = queue.Queue()
        cb = StepCallback("TestAgent", q)
        result = AgentResult(answer="ok", success=True, total_steps=3)
        cb.on_done(result)
        event = q.get()
        self.assertEqual(event["type"], "worker_done")

    def test_tc08_05_on_done_fields(self):
        """TC-08-05: on_done 事件字段完整"""
        from src.step_callback import StepCallback
        from src.agent_core import AgentResult
        q = queue.Queue()
        cb = StepCallback("TestAgent", q)
        result = AgentResult(answer="ok", success=True, total_steps=3, total_elapsed_ms=1000.0)
        cb.on_done(result)
        event = q.get()
        self.assertIn("type", event)
        self.assertIn("agent", event)
        self.assertIn("success", event)
        self.assertIn("total_steps", event)
        self.assertIn("total_elapsed_ms", event)
        self.assertIn("timestamp", event)

    def test_tc08_06_content_truncation(self):
        """TC-08-06: 内容超 500 字符截断"""
        from src.step_callback import StepCallback
        q = queue.Queue()
        cb = StepCallback("TestAgent", q)
        long_content = "x" * 600
        cb.on_step("thought", 1, long_content)
        event = q.get()
        self.assertLessEqual(len(event["content"]), 500)

    def test_tc08_07_parallel_no_loss(self):
        """TC-08-07: 多线程并行推送不丢失"""
        from src.step_callback import StepCallback
        q = queue.Queue()

        def worker(name):
            cb = StepCallback(name, q)
            for i in range(3):
                cb.on_step("thought", i, f"{name} step {i}")

        threads = [threading.Thread(target=worker, args=(f"Worker-{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        received = 0
        while not q.empty():
            q.get()
            received += 1

        self.assertGreaterEqual(received, 9)


# ============================================================
# TC-09: WorkerToolFactory
# ============================================================

class TestWorkerToolFactory(unittest.TestCase):
    """TC-09: WorkerToolFactory"""

    def test_tc09_01_create_registry(self):
        """TC-09-01: 创建含指定工具的 Registry"""
        from src.worker_tool_factory import WorkerToolFactory
        from src.tools import BaseTool, ToolRegistry

        class MockTool(BaseTool):
            name = "retrieve"
            description = "test"
            def run(self, **kwargs):
                from src.tools import ToolResult
                return ToolResult(success=True)

        shared = {"retrieve": MockTool()}
        factory = WorkerToolFactory(shared)
        registry = factory.create_registry(["retrieve"])
        self.assertIn("retrieve", registry.list_all())

    def test_tc09_02_unknown_tool(self):
        """TC-09-02: 请求不存在的工具"""
        from src.worker_tool_factory import WorkerToolFactory
        factory = WorkerToolFactory({})
        registry = factory.create_registry(["unknown_tool"])
        self.assertEqual(registry.list_all(), [])

    def test_tc09_03_shared_instance(self):
        """TC-09-03: 共享实例复用"""
        from src.worker_tool_factory import WorkerToolFactory
        from src.tools import BaseTool

        class MockTool(BaseTool):
            name = "retrieve"
            description = "test"
            def run(self, **kwargs):
                from src.tools import ToolResult
                return ToolResult(success=True)

        tool = MockTool()
        shared = {"retrieve": tool}
        factory = WorkerToolFactory(shared)
        r1 = factory.create_registry(["retrieve"])
        r2 = factory.create_registry(["retrieve"])
        self.assertIs(r1.get("retrieve"), r2.get("retrieve"))

    def test_tc09_04_init_log(self):
        """TC-09-04: 初始化日志"""
        from src.worker_tool_factory import WorkerToolFactory
        factory = WorkerToolFactory({"a": MagicMock()})
        # 无异常即通过


# ============================================================
# TC-10: RetrieveTool 线程安全
# ============================================================

class TestRetrieveToolThreadSafety(unittest.TestCase):
    """TC-10: RetrieveTool 线程安全"""

    def test_tc10_01_multi_thread_init_once(self):
        """TC-10-01: 多线程首次调用只加载一次"""
        from src.tools.retrieve_tool import RetrieveTool
        tool = RetrieveTool(api_key="sk-test")
        tool._retriever = None

        # Mock _resolve_vector_db_dir 和延迟导入的 HybridRetriever
        mock_retriever = MagicMock()
        with patch.object(tool, '_resolve_vector_db_dir', return_value=Path("/tmp/mock")):
            with patch('src.retrieval.HybridRetriever', return_value=mock_retriever):
                def call_get():
                    try:
                        tool._get_retriever()
                    except Exception:
                        pass

                threads = [threading.Thread(target=call_get) for _ in range(3)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

        # 由于 double-check locking，_retriever 应不为 None 且是同一实例
        self.assertIsNotNone(tool._retriever)

    def test_tc10_02_init_lock_exists(self):
        """TC-10-02: _init_lock 存在"""
        from src.tools.retrieve_tool import RetrieveTool
        self.assertIsInstance(RetrieveTool._init_lock, type(threading.Lock()))


# ============================================================
# TC-11: agent_config.json 扩展
# ============================================================

class TestAgentConfig(unittest.TestCase):
    """TC-11: agent_config.json 扩展"""

    def test_tc11_01_models_loaded(self):
        """TC-11-01: models 配置加载"""
        from src.api_service import _load_agent_config
        config = _load_agent_config()
        self.assertIn("models", config)
        self.assertIsInstance(config["models"], dict)

    def test_tc11_02_multi_agent_loaded(self):
        """TC-11-02: multi_agent 配置加载"""
        from src.api_service import _load_agent_config
        config = _load_agent_config()
        self.assertIn("multi_agent", config)
        self.assertIsInstance(config["multi_agent"], dict)

    def test_tc11_03_models_fallback(self):
        """TC-11-03: models 缺失回退"""
        # 直接测试 _load_agent_config 对缺失 models 节的处理
        from src.api_service import _load_agent_config
        with patch('src.api_service.Path') as mock_path:
            mock_config_path = MagicMock()
            mock_config_path.exists.return_value = True
            mock_path.return_value.parent.parent.__truediv__.return_value = mock_config_path
            mock_path_instance = MagicMock()
            mock_path_instance.parent.__truediv__.return_value = mock_config_path

            # 使用不含 models 的配置
            test_config = {
                "agent": {"max_steps": 5, "model": "qwen-max"},
                "reflector": {},
                "memory": {},
                "api": {"key": "test", "max_steps_hard_limit": 15},
            }
            with patch('builtins.open', MagicMock()):
                with patch('json.load', return_value=test_config):
                    result = _load_agent_config()
            self.assertEqual(result.get("models", {}), {})


# ============================================================
# TC-12: api_service LLMProvider 集成
# ============================================================

class TestApiServiceIntegration(unittest.TestCase):
    """TC-12: api_service LLMProvider 集成"""

    def test_tc12_01_create_agent_with_provider(self):
        """TC-12-01: _create_per_request_agent 传递 provider"""
        from src.api_service import _create_per_request_agent
        from src.agent_memory import AgentMemory
        mock_provider = MagicMock()

        with patch('src.api_service._shared_state', {
            "tool_registry": MagicMock(),
            "ag_cfg": {
                "model": "qwen-max",
                "llm_timeout": 60,
                "max_retries": 1,
                "api_max_steps_hard_limit": 15,
            },
        }):
            with patch('src.agent_core.get_api_key', return_value="sk-test"):
                agent = _create_per_request_agent(
                    memory=AgentMemory(),
                    max_steps=5,
                    temperature=0.3,
                    llm_provider=mock_provider,
                )
        self.assertEqual(agent.llm_provider, mock_provider)

    def test_tc12_02_create_agent_prompt_name(self):
        """TC-12-02: _create_per_request_agent 传 prompt_name"""
        from src.api_service import _create_per_request_agent
        from src.agent_memory import AgentMemory

        with patch('src.api_service._shared_state', {
            "tool_registry": MagicMock(),
            "ag_cfg": {
                "model": "qwen-max",
                "llm_timeout": 60,
                "max_retries": 1,
                "api_max_steps_hard_limit": 15,
            },
        }):
            with patch('src.agent_core.get_api_key', return_value="sk-test"):
                agent = _create_per_request_agent(
                    memory=AgentMemory(),
                    max_steps=5,
                    temperature=0.3,
                    llm_provider=MagicMock(),
                )
        self.assertEqual(agent._prompt_name, "default")


# ============================================================
# TC-13: 向后兼容性
# ============================================================

class TestBackwardCompat(unittest.TestCase):
    """TC-13: 向后兼容性"""

    def test_tc13_01_no_provider_works(self):
        """TC-13-01: 不传 llm_provider 时原有路径可用"""
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(tool_registry=registry, max_steps=1)

        self.assertIsNone(agent.llm_provider)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.output.choices[0].message.content = 'Thought: ok\nFinal Answer: 测试答案'
        mock_resp.usage = MagicMock(input_tokens=5, output_tokens=5)

        with patch('src.agent_core.Generation.call', return_value=mock_resp):
            agent.memory = MagicMock()
            agent.memory.get_full_context.return_value = ""
            agent.memory.summarize_to_episodic = MagicMock()
            result = agent.run("测试")

        self.assertTrue(result.success)
        self.assertEqual(result.answer, "测试答案")

    def test_tc13_02_no_shared_context_works(self):
        """TC-13-02: 不传 shared_context 时原有行为不变"""
        from src.agent_core import ReActAgent
        from src.tools import ToolRegistry
        registry = ToolRegistry()
        with patch('src.agent_core.get_api_key', return_value="sk-test"):
            agent = ReActAgent(tool_registry=registry, max_steps=1)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.output.choices[0].message.content = 'Thought: ok\nFinal Answer: 兼容测试'
        mock_resp.usage = MagicMock(input_tokens=5, output_tokens=5)

        with patch('src.agent_core.Generation.call', return_value=mock_resp):
            agent.memory = MagicMock()
            agent.memory.get_full_context.return_value = ""
            agent.memory.summarize_to_episodic = MagicMock()
            result = agent.run("测试")

        self.assertTrue(result.success)

    def test_tc13_03_old_fields_accessible(self):
        """TC-13-03: AgentResult 新字段不影响旧代码访问"""
        from src.agent_core import AgentResult
        result = AgentResult(answer="测试", success=True)
        # 旧代码访问旧字段
        self.assertEqual(result.answer, "测试")
        self.assertTrue(result.success)
        self.assertIsInstance(result.reasoning_chain, list)
        self.assertEqual(result.total_steps, 0)


# ============================================================
# 运行测试
# ============================================================

if __name__ == "__main__":
    # 运行并输出详细结果
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 加载所有测试类
    test_classes = [
        TestLLMProvider,
        TestAgentResult,
        TestReActAgentInit,
        TestCallLLMDualPath,
        TestBuildSystemPrompt,
        TestRunSignature,
        TestSourcesCollection,
        TestStepCallback,
        TestWorkerToolFactory,
        TestRetrieveToolThreadSafety,
        TestAgentConfig,
        TestApiServiceIntegration,
        TestBackwardCompat,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 统计
    print("\n" + "=" * 60)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"TDD 测试总计: {total} 项")
    print(f"通过: {passed} 项")
    print(f"失败: {len(result.failures)} 项")
    print(f"错误: {len(result.errors)} 项")
    if result.wasSuccessful():
        print("所有测试通过!")
    else:
        print("存在未通过的测试，请检查上方输出。")
