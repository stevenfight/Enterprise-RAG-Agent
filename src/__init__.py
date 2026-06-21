# -*- coding: utf-8 -*-
"""
企业级财务年报分析智能 RAG-Agent 系统

导出核心模块，以支持管道模式（向后兼容）和 Agent 模式（新增）。
"""

__version__ = "2.1.0"

# ============================================================
# 管道模式 (RAG Pipeline，向后兼容)
# ============================================================
from .retrieval import RAGGenerator, HybridRetriever, VectorRetriever, BM25Retriever
from .query_processor import QueryProcessor
from .conversation import ConversationManager
# pdf_mineru 和 text_splitter 为脚本式模块(shell 调用), 不导出类

# ============================================================
# Agent 模式 (新增)
# ============================================================
from .agent_core import ReActAgent, AgentResult
from .agent_memory import AgentMemory
from .planner import TaskPlanner, TaskPlan, SubTask, SubTaskType
from .reflector import AnswerReflector, ReflectionResult
from .tools import ToolRegistry, BaseTool, ToolResult

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
