# -*- coding: utf-8 -*-
"""
Agent 注册表

管理所有 Worker Agent 的能力描述。复用 ToolRegistry 设计模式。

对应方案：多Agent升级方案 步骤 2.1
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class AgentCapability:
    """Worker Agent 能力描述

    Attributes:
        name: Agent 唯一名称（"DataAgent"）
        description: 能力描述（供 LLM 理解）
        tools: 持有的工具名称列表
        max_parallel: 可并行实例数
        llm_model: 使用的 LLM 模型
    """
    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    max_parallel: int = 1
    llm_model: str = "qwen-turbo"


class AgentRegistry:
    """Agent 注册表

    管理 Worker Agent 的能力元数据。

    Usage:
        registry = AgentRegistry()
        registry.register(AgentCapability(
            name="DataAgent",
            description="从向量数据库精确检索财务数据",
            tools=["retrieve"],
            max_parallel=3,
            llm_model="qwen-turbo",
        ))
        desc = registry.get_agent_descriptions()
        # "1. DataAgent: 从向量数据库精确检索财务数据 [工具: retrieve]"
    """

    def __init__(self):
        self._capabilities: Dict[str, AgentCapability] = {}

    def register(self, cap: AgentCapability) -> None:
        """注册 Agent 能力

        Args:
            cap: AgentCapability 实例

        Raises:
            ValueError: Agent 名已存在
        """
        if cap.name in self._capabilities:
            raise ValueError(f"Agent '{cap.name}' 已注册")
        self._capabilities[cap.name] = cap

    def get(self, name: str):
        """根据名称获取 Agent 能力描述

        Args:
            name: Agent 名称

        Returns:
            AgentCapability 或 None
        """
        return self._capabilities.get(name)

    def list_all(self) -> List[str]:
        """列出所有已注册 Agent 的名称"""
        return list(self._capabilities.keys())

    def get_agent_descriptions(self) -> str:
        """生成 LLM 可用的 Agent 能力描述文本

        用于注入 OrchestratorAgent 的 System Prompt。

        Returns:
            格式化的 Agent 能力描述
        """
        if not self._capabilities:
            return "(没有可用的 Worker Agent)"

        lines = []
        for i, cap in enumerate(self._capabilities.values(), 1):
            tool_str = ", ".join(cap.tools) if cap.tools else "无"
            lines.append(
                f"{i}. {cap.name}: {cap.description} "
                f"[工具: {tool_str}]"
            )
        return "\n".join(lines)
