# -*- coding: utf-8 -*-
"""
OrchestratorAgent - 多 Agent 任务调度器

继承 ReActAgent，只持有 delegate 工具。
使用 LLM 拆解复杂查询，委托 Worker Agent 执行，汇总结果。

对应方案：多Agent升级方案 步骤 2.4
"""

import json
import logging
import os
import sys
from typing import Any, Optional

from src.agent_core import ReActAgent
from src.tools import ToolRegistry

logger = logging.getLogger("orchestrator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


class OrchestratorAgent(ReActAgent):
    """任务调度 Agent

    分析用户需求 → 委托 Worker Agent 执行 → 汇总结果。

    Usage:
        registry = AgentRegistry()
        sm = SharedMemory()
        delegate_tool = DelegateTool(agent_registry=registry, shared_memory=sm)
        orchestrator = OrchestratorAgent(
            delegate_tool=delegate_tool,
            agent_registry=registry,
            llm_provider=provider,
            shared_memory=sm,
        )
        result = orchestrator.run("三大运营商2024年营收对比")
    """

    def __init__(
        self,
        delegate_tool,
        agent_registry,
        llm_provider: Optional[Any] = None,
        shared_memory: Optional[Any] = None,
    ):
        """初始化 OrchestratorAgent

        Args:
            delegate_tool: DelegateTool 实例
            agent_registry: AgentRegistry 实例
            llm_provider: LLM Provider 实例
            shared_memory: SharedMemory 实例
        """
        self.agent_registry = agent_registry
        self.shared_memory = shared_memory

        # 低优修复: 参数校验
        if delegate_tool is None:
            raise ValueError("delegate_tool 不能为 None")
        if agent_registry is None:
            raise ValueError("agent_registry 不能为 None")

        # Orchestrator 只注册 delegate 工具
        tool_registry = ToolRegistry()
        tool_registry.register(delegate_tool)

        # 使用 agent_descriptions 作为自定义 System Prompt 的变量
        self._agent_descriptions = agent_registry.get_agent_descriptions()

        super().__init__(
            tool_registry=tool_registry,
            llm_provider=llm_provider,
            prompt_name="orchestrator",
            model="qwen-max",
            temperature=0.3,
            max_steps=10,
            llm_timeout=120,
        )

        # M7: 从配置文件读取参数，优先配置文件，其次构造函数参数
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'agent_config.json')
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f).get("multi_agent", {})
                    self.model = cfg.get("orchestrator_model", self.model)
                    self.temperature = cfg.get("orchestrator_temperature", self.temperature)
                    self.llm_timeout = cfg.get("orchestrator_timeout", self.llm_timeout)
        except Exception:
            pass  # 配置不可用则使用构造函数默认值

        logger.info("[OrchestratorAgent] 初始化完成: agents=%s",
                     agent_registry.list_all())

    def _build_system_prompt(self, **kwargs) -> str:
        """覆写 _build_system_prompt，注入 agent_descriptions

        Orchestrator 的 System Prompt 中需要知道可调度哪些 Worker。
        agent_descriptions 在构造时从 AgentRegistry 获取。
        """
        kwargs["agent_descriptions"] = self._agent_descriptions
        return super()._build_system_prompt(**kwargs)
