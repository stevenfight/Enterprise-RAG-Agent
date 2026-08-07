# -*- coding: utf-8 -*-
"""
SharedMemory - 跨 Worker Agent 共享中间结果

实现写入隔离、读取合并、来源聚合、Token 聚合。
Worker 各自的私有记忆（AgentMemory）不变，SharedMemory 是上层扩展。

注意：add_agent_result 为同步方法，使用 threading.Lock 保护写入。
这是因为 DelegateTool.run() 通过 ReActAgent → BaseTool 链在同步上下文中调用，
而非 async 上下文。

对应方案：多Agent升级方案 步骤 2.2
"""

import logging
import sys
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("shared_memory")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


class SharedMemory:
    """跨 Agent 共享记忆

    写入隔离，读取合并。用于 Orchestrator 将 DataAgent 的检索结果
    传递给后续的 CalcAgent / CompareAgent 等。

    Usage:
        sm = SharedMemory()
        sm.set_task_context("query", "三大运营商2024营收对比")
        sm.set_task_context("companies", ["中国移动", "中国联通", "中国电信"])
        sm.add_agent_result("DataAgent(中芯)", result)
        ctx = sm.get_context_for("CalcAgent", {"company_name": "中芯国际"})
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.task_context: Dict[str, Any] = {}
        self.agent_outputs: Dict[str, Any] = {}  # { "DataAgent(中芯)": AgentResult, ... }
        self.execution_log: List[Dict[str, Any]] = []

    # ---- 任务上下文 ----

    def set_task_context(self, key: str, value: Any) -> None:
        """设置任务级公共上下文"""
        self.task_context[key] = value
        logger.info("[SharedMemory] 设置任务上下文: %s", key)

    def get_task_context(self, key: str, default: Any = None) -> Any:
        """获取任务级公共上下文"""
        return self.task_context.get(key, default)

    # ---- Agent 结果写入 ----

    def add_agent_result(self, agent_name: str, result) -> None:
        """写入 Worker Agent 的执行结果（并发安全）

        Args:
            agent_name: Worker 名称标识（如 "DataAgent(中芯)"）
            result: AgentResult 实例
        """
        with self._lock:
            self.agent_outputs[agent_name] = result
            self.execution_log.append({
                "agent": agent_name,
                "ts": time.time(),
                "success": getattr(result, "success", False),
                "tokens": getattr(result, "total_tokens", 0),
            })
            logger.info("[SharedMemory] 写入 Agent 结果: %s, success=%s",
                         agent_name, getattr(result, "success", False))

    # ---- Agent 结果读取 ----

    def get_agent_result(self, agent_name: str) -> Optional[Any]:
        """获取指定 Worker 的执行结果"""
        return self.agent_outputs.get(agent_name)

    def get_all_agent_results(self) -> Dict[str, Any]:
        """获取所有 Worker 的执行结果"""
        return dict(self.agent_outputs)

    def get_context_for(self, agent_name: str, task: dict = None) -> str:
        """为下游 Agent 构建上下文文本

        不同 Worker 角色返回不同格式：
        - ChartAgent: 返回结构化数值（方便构造 data 参数）
        - VerifyAgent: 返回陈述文本 + 来源文本
        - 其他: 返回纯文本摘要

        Args:
            agent_name: 下游 Agent 名称（如 "ChartAgent"）
            task: 当前子任务信息（如 {"company_name": "中芯国际"}）

        Returns:
            上下文文本
        """
        lines = []
        for name, result in self.agent_outputs.items():
            answer = getattr(result, "answer", "")
            if answer:
                lines.append(f"[{name} 结果]\n{answer}")

        if not lines:
            return "（无上游结果）"

        return "\n\n".join(lines)

    # ---- 聚合方法 ----

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """收集所有 Worker 的检索来源，供 Reflector 使用

        AgentResult.sources 在步骤 0.1 中新增，
        存储 retrieve 工具返回的来源信息（含 source/content/pages/company_name 字段）
        """
        sources = []
        for name, result in self.agent_outputs.items():
            result_sources = getattr(result, "sources", [])
            if result_sources:
                sources.extend(result_sources)
        logger.info("[SharedMemory] 来源聚合: %d 个 Worker, %d 条来源",
                     len(self.agent_outputs), len(sources))
        return sources

    def get_total_tokens(self) -> int:
        """聚合所有 Worker 的 Token 用量"""
        return sum(
            getattr(result, "total_tokens", 0)
            for result in self.agent_outputs.values()
        )

    def get_execution_log(self) -> List[Dict[str, Any]]:
        """获取执行流水日志"""
        return list(self.execution_log)

    def clear(self) -> None:
        """清空所有共享数据（每次新查询时调用）"""
        self.task_context.clear()
        self.agent_outputs.clear()
        self.execution_log.clear()
        logger.info("[SharedMemory] 已清空")
