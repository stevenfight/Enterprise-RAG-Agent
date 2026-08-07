# -*- coding: utf-8 -*-
"""
CalcAgent - 财务计算 Worker Agent

只做精确计算（增长率/CAGR/利润率），不做原始数据检索。
输入来自上游 DataAgent 的 SharedMemory 结果（shared_context 注入）。

对应方案：多Agent升级方案 步骤 3.2
"""

from typing import Any, Optional

from src.agent_core import ReActAgent
from src.tools import ToolRegistry


class CalcAgent(ReActAgent):
    """财务计算 Worker Agent

    继承 ReActAgent，持有 calculator + retrieve 工具。
    使用 qwen-plus（温度 0.1）保证计算稳定且成本可控。
    max_steps=5，计算任务通常 1-3 步。
    """

    def __init__(
        self,
        calculator_tool: Any,
        retrieval_tool: Any,
        llm_provider: Optional[Any] = None,
    ):
        """初始化 CalcAgent

        Args:
            calculator_tool: calculator 工具实例（CalculatorTool）
            retrieval_tool: retrieve 工具实例（RetrieveTool，数据不足时补充检索）
            llm_provider: LLM Provider 实例（可选，不传则走原有 dashscope 直调）
        """
        registry = ToolRegistry()
        registry.register(calculator_tool)
        registry.register(retrieval_tool)

        super().__init__(
            tool_registry=registry,
            llm_provider=llm_provider,
            prompt_name="calc_agent",
            max_steps=5,
            temperature=0.1,
            model="qwen-plus",
        )
