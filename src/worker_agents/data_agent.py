# -*- coding: utf-8 -*-
"""
DataAgent - 财务数据检索 Worker Agent

只做精确检索，不做计算、不做对比、不做分析。

使用方式:
    from src.worker_agents.data_agent import DataAgent
    from src.llm_provider import DashScopeProvider

    provider = DashScopeProvider(model_name="qwen-turbo")
    agent = DataAgent(retrieval_tool=retrieve_tool, llm_provider=provider)
    result = agent.run("中芯国际2024年营收是多少")
"""

from typing import Any, Optional

from src.agent_core import ReActAgent
from src.tools import ToolRegistry


class DataAgent(ReActAgent):
    """财务数据检索 Worker Agent

    继承 ReActAgent，只持有 retrieve 工具。
    使用 qwen-turbo（温度 0.2）以降低 API 成本。
    max_steps=3，因为检索任务不需要过多推理步骤。
    """

    def __init__(
        self,
        retrieval_tool: Any,
        llm_provider: Optional[Any] = None,
    ):
        """初始化 DataAgent

        Args:
            retrieval_tool: retrieve 工具实例（RetrieveTool）
            llm_provider: LLM Provider 实例（可选，不传则走原有 dashscope 直调）
        """
        # DataAgent 只注册 retrieve 一个工具
        registry = ToolRegistry()
        registry.register(retrieval_tool)

        super().__init__(
            tool_registry=registry,
            llm_provider=llm_provider,
            prompt_name="data_agent",  # 加载 agent_prompts.yaml 中 data_agent 节
            max_steps=3,               # 检索任务步数够用即可
            temperature=0.2,           # 检索需要稳定输出
            model="qwen-turbo",        # 简单推理，turbo 即可
        )
