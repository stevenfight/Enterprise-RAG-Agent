# -*- coding: utf-8 -*-
"""
Worker 工具实例工厂

为每个 Worker 创建独立的 ToolRegistry，只注册该 Worker 需要的工具。
- RetrieveTool/CalculatorTool/ChartTool/VerifyTool -> 共享实例（无状态或并行安全）
- CompareTool -> 共享实例（优先从 SharedMemory 获取数据）

对应方案：多Agent升级方案 步骤 0.1 改动 H
对应 SDD: openspec/changes/multi-agent-step01/specs/spec-step01-upgrade.md
"""

import logging
import sys
from typing import Dict, List

from src.tools import BaseTool, ToolRegistry

logger = logging.getLogger("worker_tool_factory")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


class WorkerToolFactory:
    """Worker 工具实例工厂

    从全局共享的工具实例中，为每个 Worker 创建只含所需工具的 ToolRegistry。

    Usage:
        factory = WorkerToolFactory(global_registry._tools)
        data_registry = factory.create_registry(["retrieve"])
        calc_registry = factory.create_registry(["calculator", "retrieve"])
    """

    def __init__(self, shared_tools: Dict[str, BaseTool]):
        """初始化工厂

        Args:
            shared_tools: 全局 ToolRegistry 中的工具实例字典（tool_name -> BaseTool）
        """
        self._shared = shared_tools
        logger.info("[WorkerToolFactory] 初始化完成, 共享工具: %s", list(shared_tools.keys()))

    def create_registry(self, tool_names: List[str]) -> ToolRegistry:
        """为 Worker 创建工具注册表

        Args:
            tool_names: Worker 需要的工具名称列表

        Returns:
            独立的 ToolRegistry，只注册所需工具
        """
        registry = ToolRegistry()
        for name in tool_names:
            if name in self._shared:
                registry.register(self._shared[name])
                logger.debug("[WorkerToolFactory] 注册共享工具: %s", name)
            else:
                logger.warning("[WorkerToolFactory] 工具 '%s' 不在共享池中，跳过", name)

        logger.info("[WorkerToolFactory] 创建 ToolRegistry: tools=%s", registry.list_all())
        return registry
