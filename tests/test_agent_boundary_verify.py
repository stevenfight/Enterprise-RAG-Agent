# -*- coding: utf-8 -*-
"""边界场景测试: 强制终止 + 空结果埋点 (pytest 规范化)

历史问题(D6 阻断): 本文件原为直接执行的验证脚本, 全部逻辑位于模块级,
导致 `pytest -q` 在收集(import)阶段即触发真实 LLM 网络调用, 并在打印
reasoning_chain 时因 `KeyError: 'step_number'` 中断整个测试收集。

现改造为规范 pytest 结构:
  - 场景 1(真实 LLM): 标记 @pytest.mark.skip, 原验证代码保留, 仅供手动验证
  - 场景 2(合成空结果): monkey-patch _call_llm 与 _execute_action, 完全脱网
  - 场景 3(_parse_response / _is_empty_result): 纯逻辑单元测试
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools import ToolRegistry
from tools.retrieve_tool import RetrieveTool
from tools.calculator_tool import CalculatorTool
from tools.compare_tool import CompareTool
from tools.chart_tool import ChartTool
from tools.verify_tool import VerifyTool
from agent_memory import AgentMemory
from agent_core import ReActAgent


@pytest.fixture(scope="module")
def registry():
    """注册全部工具(构建轻量, 不发起网络请求)"""
    reg = ToolRegistry()
    reg.register(RetrieveTool())
    reg.register(CalculatorTool())
    reg.register(CompareTool())
    reg.register(ChartTool())
    reg.register(VerifyTool())
    return reg


@pytest.fixture()
def make_agent(registry):
    def _make(max_steps=2):
        return ReActAgent(
            tool_registry=registry,
            memory=AgentMemory(),
            max_steps=max_steps,
            temperature=0.3,
            model="qwen-max",
        )

    return _make


@pytest.mark.skip(reason="场景1依赖真实 LLM(qwen-max)网络调用, 耗时且不稳定; 验证代码保留供手动运行")
def test_scenario1_real_llm_empty_result(make_agent):
    """场景 1: 真实 LLM 空结果 —— 非注册公司 特斯拉 + company_name 参数"""
    agent = make_agent(max_steps=2)
    result = agent.run("特斯拉2024年营收和净利润是多少", company_name="特斯拉")
    # 真实调用仅观察行为, 不做强断言(受模型随机性影响), 关键链路指标保留
    assert result is not None
    assert result.total_steps >= 0


def test_scenario2_forced_stop_on_synthetic_empty_results(make_agent):
    """场景 2: 合成空结果 —— 所有工具调用返回失败标记, 必然触发强制终止

    链路: 空结果累计(1次→2次) → forced_stop=True → _generate_forced_answer() 降级答案
    """
    agent = make_agent(max_steps=2)

    # LLM 决策固定为持续调用 retrieve (脱网, 不依赖外部服务)
    def fake_llm(messages):
        return (
            "Thought: 需要检索数据。\n"
            "Action: retrieve\n"
            'Action Input: {"query": "营收"}'
        )

    # 工具执行固定返回空结果标记
    def fake_execute(action, action_input):
        return "[工具执行失败] 模拟空结果: 检索无匹配数据"

    original_llm = agent._call_llm
    original_execute = agent._execute_action
    agent._call_llm = fake_llm
    agent._execute_action = fake_execute
    try:
        result = agent.run("中芯国际2024年营收和净利润是多少")
    finally:
        agent._call_llm = original_llm
        agent._execute_action = original_execute

    assert result.forced_stop is True, "预期 forced_stop=True"
    assert result.total_steps == agent.max_steps, "预期 total_steps=max_steps"
    assert len(result.answer) > 0, "预期强制降级答案非空"


def test_scenario3_parse_response_formats():
    """场景 3: _parse_response 三种格式解析"""
    agent = ReActAgent.__new__(ReActAgent)
    agent._tool_registry = ToolRegistry()

    # 正常格式
    resp1 = 'Thought: 需要检索。\nAction: retrieve\nAction Input: {"query": "营收"}'
    thought1, action1, input1 = agent._parse_response(resp1)
    assert thought1, "正常格式应解析出 thought"
    assert action1 == "retrieve", "正常格式应解析出 action"

    # 缺少 Action (视为最终答案)
    resp2 = "Thought: 我需要更多数据。\n这是最终答案：营收1000亿"
    thought2, action2, _ = agent._parse_response(resp2)
    assert thought2, "缺 Action 格式应解析出 thought"

    # 标准 ReAct 格式
    resp3 = 'Thought: 先检索一下数据。\nAction: retrieve\nAction Input: {"query": "营收"}'
    _, action3, input3 = agent._parse_response(resp3)
    assert action3 == "retrieve", "标准格式应解析出 action"


@pytest.mark.parametrize(
    "text,expected,label",
    [
        ("[错误]test", True, "[错误] 前缀"),
        ("[工具执行失败] 公司 '特斯拉' 未在注册表中", True, "[工具执行失败] 前缀"),
        ("未检索到相关数据。建议：调整查询关键词", True, "未检索到相关数据"),
        ("未找到相关数据", True, "未找到相关数据"),
        ("无有效数值", True, "无有效数值"),
        ("中芯国际营收578亿元", False, "正常结果"),
        ("", True, "空字符串"),
    ],
)
def test_scenario3_is_empty_result_markers(text, expected, label):
    """场景 3: _is_empty_result 空结果标记全覆盖"""
    agent = ReActAgent.__new__(ReActAgent)
    agent._tool_registry = ToolRegistry()
    assert agent._is_empty_result(text) == expected, label
