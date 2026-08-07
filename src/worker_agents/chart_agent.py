# -*- coding: utf-8 -*-
"""
ChartAgent - 图表渲染 Worker Agent

从上游 SharedMemory 数据中提取结构化数值并生成图表。
只持有 chart 工具，不自行检索（数据来源为上游 Worker 结果）。

对应方案：多Agent升级方案 步骤 3.4
"""

from typing import Any, Optional

from src.agent_core import ReActAgent
from src.tools import ToolRegistry


class ChartAgent(ReActAgent):
    """图表渲染 Worker Agent

    继承 ReActAgent，只持有 chart 工具。
    使用 qwen-max（温度 0.3）从上游文本提取结构化数值。
    max_steps=5，图表任务通常 1-3 步。
    """

    def __init__(
        self,
        chart_tool: Any,
        llm_provider: Optional[Any] = None,
    ):
        """初始化 ChartAgent

        Args:
            chart_tool: chart 工具实例（ChartTool）
            llm_provider: LLM Provider 实例（可选，不传则走原有 dashscope 直调）
        """
        registry = ToolRegistry()
        registry.register(chart_tool)

        super().__init__(
            tool_registry=registry,
            llm_provider=llm_provider,
            prompt_name="chart_agent",
            max_steps=5,
            temperature=0.3,
            model="qwen-max",
        )
