# -*- coding: utf-8 -*-
"""
VerifyAgent - 财务数据审核 Worker Agent

验证其他 Worker 输出的数据准确性（数字与来源对应关系）。
claim 来自 SharedMemory，source_text 由 retrieve 检索获得。

对应方案：多Agent升级方案 步骤 3.5
"""

from typing import Any, Optional

from src.agent_core import ReActAgent
from src.tools import ToolRegistry


class VerifyAgent(ReActAgent):
    """财务数据审核 Worker Agent

    继承 ReActAgent，持有 verify + retrieve 工具。
    使用 qwen-plus（温度 0.1）保证审核结论稳定可靠。
    max_steps=5，审核任务通常 1-3 步。
    """

    def __init__(
        self,
        verify_tool: Any,
        retrieval_tool: Any | None = None,
        llm_provider: Optional[Any] = None,
        allow_retrieve: bool = True,
    ):
        """初始化 VerifyAgent

        Args:
            verify_tool: verify 工具实例（VerifyTool）
            retrieval_tool: retrieve 工具实例（仅允许检索时需要）
            llm_provider: LLM Provider 实例（可选，不传则走原有 dashscope 直调）
            allow_retrieve: 是否允许注册 retrieve；由研究步骤的工具策略决定
        """
        registry = ToolRegistry()
        registry.register(verify_tool)
        if allow_retrieve:
            if retrieval_tool is None:
                raise ValueError("允许检索的 VerifyAgent 必须提供 retrieve 工具")
            registry.register(retrieval_tool)

        super().__init__(
            tool_registry=registry,
            llm_provider=llm_provider,
            prompt_name="verify_agent",
            max_steps=5,
            temperature=0.1,
            model="qwen-plus",
        )
