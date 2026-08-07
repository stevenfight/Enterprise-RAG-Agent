# -*- coding: utf-8 -*-
"""
StepCallback 机制

解决 Worker 在 ThreadPool 中运行时，内部步骤无法直接 yield 到外层 SSE 的问题。

关键设计：
  - 使用 queue.Queue（线程安全），而不是 asyncio.Queue（单线程）
  - on_done 推送 worker_done 事件，最终结束信号由 DelegateTool 推入 None

对应方案：多Agent升级方案 步骤 0.1 改动 E
对应 SDD: openspec/changes/multi-agent-step01/specs/spec-step01-upgrade.md
"""

import logging
import queue
import sys
import time
from typing import Any, Dict

logger = logging.getLogger("step_callback")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


class StepCallback:
    """Worker 步骤回调：将步骤事件推入线程安全队列，供 SSE 消费

    Usage:
        event_queue = queue.Queue()
        callback = StepCallback(agent_name="DataAgent(中芯)", event_queue=event_queue)

        # Worker 内部每步完成后调用
        callback.on_step("thought", step=1, content="正在检索中芯国际...")
        callback.on_step("action", step=1, content="retrieve")
        callback.on_step("observation", step=1, content="...")

        # 结束标记
        callback.on_done(agent_result)
    """

    def __init__(self, agent_name: str, event_queue: "queue.Queue"):
        """初始化回调

        Args:
            agent_name: Worker 名称（如 "DataAgent(中芯)"），用于 SSE 事件标识
            event_queue: 线程安全的 queue.Queue 实例（注意：不是 asyncio.Queue）
        """
        self.agent_name = agent_name
        self.event_queue = event_queue
        logger.info("[StepCallback] 初始化: agent=%s", agent_name)

    def on_step(self, step_type: str, step: int, content: str):
        """Worker 每步完成后调用

        从 ThreadPool 工作线程中调用，queue.Queue.put() 是线程安全的。

        Args:
            step_type: 步骤类型 (thought / action / observation)
            step: 步骤编号
            content: 步骤内容（超过 500 字符自动截断，SSE 展示用；
                     完整数据通过 SharedMemory 传递）
        """
        event = {
            "type": "worker_step",
            "agent": self.agent_name,
            "step_type": step_type,
            "step": step,
            "content": content[:500] if len(content) > 500 else content,
            "timestamp": int(time.time() * 1000),
        }
        self.event_queue.put(event)
        logger.debug("[StepCallback] 推送事件: agent=%s, type=%s, step=%d",
                     self.agent_name, step_type, step)

    def on_done(self, result: Any):
        """Worker 完成后调用，推送完成事件

        Args:
            result: Worker 的 AgentResult 实例
        """
        event = {
            "type": "worker_done",
            "agent": self.agent_name,
            "success": getattr(result, "success", False),
            "total_steps": getattr(result, "total_steps", 0),
            "total_elapsed_ms": getattr(result, "total_elapsed_ms", 0.0),
            "timestamp": int(time.time() * 1000),
        }
        self.event_queue.put(event)
        logger.info("[StepCallback] Worker 完成: agent=%s, success=%s, steps=%d",
                    self.agent_name, event["success"], event["total_steps"])
