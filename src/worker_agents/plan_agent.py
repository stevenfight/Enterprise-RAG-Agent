# -*- coding: utf-8 -*-
"""研究计划确认 Worker Agent。"""

from typing import Any, Optional

from src.agent_core import ReActAgent
from src.tools import ToolRegistry


class PlanAgent(ReActAgent):
    """只确认已审批计划快照，不具备重规划或工具调用能力。"""

    def __init__(self, llm_provider: Optional[Any] = None):
        """初始化不含工具的计划确认 Agent。"""
        super().__init__(
            tool_registry=ToolRegistry(),
            llm_provider=llm_provider,
            system_prompt=(
                "你是研究计划确认 Worker。只确认用户消息中给出的已审批计划快照。"
                "不得生成、修改、替换步骤、范围、预算、风险或 Agent 绑定；不得调用工具。"
                "仅使用 Final Answer 简短确认已读取快照。"
            ),
            max_steps=1,
            temperature=0.0,
            model="qwen-turbo",
        )
