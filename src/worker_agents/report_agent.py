# -*- coding: utf-8 -*-
"""研究报告确认 Worker Agent。"""

from typing import Any, Optional

from src.agent_core import ReActAgent
from src.tools import ToolRegistry


class ReportAgent(ReActAgent):
    """只确认已有不可变报告草稿，不新增或改写声明。"""

    def __init__(self, llm_provider: Optional[Any] = None):
        super().__init__(
            tool_registry=ToolRegistry(),
            llm_provider=llm_provider,
            system_prompt="你是研究报告确认 Worker。只确认用户消息中的不可变报告草稿；不得调用工具、不得新增或改写声明。仅使用 Final Answer 简短确认。",
            max_steps=1,
            temperature=0.0,
            model="qwen-turbo",
        )
