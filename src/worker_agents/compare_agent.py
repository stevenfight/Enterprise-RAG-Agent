# -*- coding: utf-8 -*-
"""
CompareAgent - 横向对比 Worker Agent

多公司财务数据横向对比，输出 Markdown 表格。
优先使用上游 SharedMemory 数据，数据不足时才触发 compare 工具检索。

对应方案：多Agent升级方案 步骤 3.3
"""

from typing import Any, Optional

from src.agent_core import ReActAgent
from src.tools import ToolRegistry


class CompareAgent(ReActAgent):
    """财务对比 Worker Agent

    继承 ReActAgent，持有 compare + retrieve 工具。
    使用 qwen-max（温度 0.3）保证对比分析的推理质量。
    max_steps=5，对比任务通常 1-3 步。
    """

    def __init__(
        self,
        compare_tool: Any,
        retrieval_tool: Any,
        llm_provider: Optional[Any] = None,
    ):
        """初始化 CompareAgent

        Args:
            compare_tool: compare 工具实例（CompareTool）
            retrieval_tool: retrieve 工具实例（RetrieveTool，数据不足时补充检索）
            llm_provider: LLM Provider 实例（可选，不传则走原有 dashscope 直调）
        """
        registry = ToolRegistry()
        registry.register(compare_tool)
        registry.register(retrieval_tool)

        super().__init__(
            tool_registry=registry,
            llm_provider=llm_provider,
            prompt_name="compare_agent",
            max_steps=5,
            temperature=0.3,
            model="qwen-max",
        )
