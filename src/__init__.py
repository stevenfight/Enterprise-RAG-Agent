# -*- coding: utf-8 -*-
"""
企业级财务年报分析智能 RAG-Agent 系统

导出核心模块，以支持管道模式（向后兼容）和 Agent 模式（新增）。
"""

__version__ = "2.1.0"

from importlib import import_module
from typing import Any


# 根包只保留兼容导出名称，具体模块在真正访问时再加载。
# 这样评测、schema 等不需要 RAG/Agent 的子模块不会触发监控或模型依赖初始化。
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # 管道模式（RAG Pipeline，向后兼容）
    "RAGGenerator": (".retrieval", "RAGGenerator"),
    "HybridRetriever": (".retrieval", "HybridRetriever"),
    "VectorRetriever": (".retrieval", "VectorRetriever"),
    "BM25Retriever": (".retrieval", "BM25Retriever"),
    "QueryProcessor": (".query_processor", "QueryProcessor"),
    "ConversationManager": (".conversation", "ConversationManager"),
    # Agent 模式
    "ReActAgent": (".agent_core", "ReActAgent"),
    "AgentResult": (".agent_core", "AgentResult"),
    "AgentMemory": (".agent_memory", "AgentMemory"),
    "TaskPlanner": (".planner", "TaskPlanner"),
    "TaskPlan": (".planner", "TaskPlan"),
    "SubTask": (".planner", "SubTask"),
    "SubTaskType": (".planner", "SubTaskType"),
    "AnswerReflector": (".reflector", "AnswerReflector"),
    "ReflectionResult": (".reflector", "ReflectionResult"),
    "ToolRegistry": (".tools", "ToolRegistry"),
    "BaseTool": (".tools", "BaseTool"),
    "ToolResult": (".tools", "ToolResult"),
}


def __getattr__(name: str) -> Any:
    """按需解析根包兼容导出，保留原有 ``from src import ...`` 用法。"""
    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value

__all__ = [
    # Pipeline
    "RAGGenerator", "HybridRetriever", "VectorRetriever", "BM25Retriever",
    "QueryProcessor", "ConversationManager",
    # Agent Core
    "ReActAgent", "AgentResult", "AgentMemory",
    # Agent Reflection
    "TaskPlanner", "TaskPlan", "SubTask", "SubTaskType",
    "AnswerReflector", "ReflectionResult",
    # Tools
    "ToolRegistry", "BaseTool", "ToolResult",
]
