# -*- coding: utf-8 -*-
"""
检索工具 (Agent 工具)

封装 HybridRetriever.search() 为 Agent 可调用的标准工具。
Agent 通过此工具从企业年报向量数据库中检索财务数据。

调用链路:
  Agent.Action("retrieve") → RetrieveTool.run(query, company_name, top_n)
    → HybridRetriever.search(query, company_name, top_n)
    → BM25 + 向量检索 → 融合 → gte-rerank → 返回结果
    → ToolResult(success=True, data=格式化后的检索结果)

对应 SDD: openspec/changes/rag-to-agent/specs/spec-tools.md
对应 TDD: tests/test_agent_tools.py (TC-T01 ~ TC-T03)
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import BaseTool, ToolResult

logger = logging.getLogger("retrieve_tool")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


class RetrieveTool(BaseTool):
    """财报检索工具

    将用户查询从年报向量数据库中检索相关财务数据。
    内部调用 HybridRetriever（BM25 + 向量混合检索 + gte-rerank-v2 重排）。

    Agent 用法示例:
        Thought: 需要查询中芯国际2024年营收
        Action: retrieve
        Action Input: {"query": "中芯国际 2024 营收", "company_name": "中芯国际", "top_n": 3}
    """

    name = "retrieve"
    description = (
        "从企业年报数据库中检索财务数据。支持指定公司名称或检索全部公司。"
        "返回结果包含文本内容、来源文件名、页码、公司名和各项检索评分。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索查询文本，用自然语言描述要查找的财务信息"
            },
            "company_name": {
                "type": "string",
                "description": (
                    "指定公司名称，可选值: 中芯国际, 中国移动, 中国联通, 中国电信。"
                    "不填则检索全部公司并公平分配结果"
                )
            },
            "top_n": {
                "type": "integer",
                "description": "返回结果数量，默认 5，最大 10"
            },
        },
        "required": ["query"],
    }

    def __init__(self, api_key: Optional[str] = None):
        """初始化检索工具

        Args:
            api_key: DashScope API Key（可选，默认从环境读取）
        """
        self._api_key = api_key
        self._retriever = None
        self._vector_db_dir = None

        logger.info("[RetrieveTool] 初始化完成（HybridRetriever 延迟加载）")

    # ============================================================
    # 内部方法
    # ============================================================

    def _resolve_vector_db_dir(self) -> Path:
        """解析向量数据库目录路径

        从 src/tools/retrieve_tool.py 向上三级到项目根目录，
        再拼接 data/stock_data/databases/vector_dbs

        Returns:
            Path: 向量数据库目录的绝对路径

        Raises:
            FileNotFoundError: 向量数据库目录不存在时抛出
        """
        if self._vector_db_dir is not None:
            return self._vector_db_dir

        # 相对路径推算：src/tools/retrieve_tool.py → src/tools/ → src/ → 项目根
        project_root = Path(__file__).resolve().parent.parent.parent
        self._vector_db_dir = project_root / "data" / "stock_data" / "databases" / "vector_dbs"

        if not self._vector_db_dir.exists():
            logger.error("[RetrieveTool] 向量数据库目录不存在: %s", self._vector_db_dir)
            raise FileNotFoundError(
                f"向量数据库目录不存在: {self._vector_db_dir}\n"
                "请先运行 python src/ingestion.py 构建向量数据库。"
            )

        logger.info("[RetrieveTool] 向量数据库目录已确认: %s", self._vector_db_dir)
        return self._vector_db_dir

    def _get_retriever(self):
        """延迟初始化 HybridRetriever

        只在第一次调用检索时加载 retrieval 模块及其重型依赖
        （jieba, faiss, dashscope 等），避免启动时全部加载。
        """
        if self._retriever is None:
            logger.info("[RetrieveTool] 首次调用，延迟加载 HybridRetriever...")

            # 延迟导入：避免工具注册时加载重型依赖
            from retrieval import HybridRetriever

            vector_db_dir = self._resolve_vector_db_dir()
            self._retriever = HybridRetriever(vector_db_dir, api_key=self._api_key)
            logger.info("[RetrieveTool] HybridRetriever 实例化完成")

        return self._retriever

    def _format_results(
        self,
        results: List[Dict[str, Any]],
        query: str,
        company_name: Optional[str],
    ) -> Dict[str, Any]:
        """将 HybridRetriever 原始结果格式化为 Agent 可读结构

        把 scores 字典展平、页码格式化为中文、补充查询摘要信息。

        Args:
            results: HybridRetriever.search() 的返回列表
            query: 原始查询文本
            company_name: 指定的公司名（None 表示全部）

        Returns:
            格式化后的字典，包含 results 数组和查询摘要
        """
        formatted = []
        for i, r in enumerate(results):
            # 页码格式化: [23, 24, 25] → "第23-25页"
            pages = r.get("pages", [])
            if pages and len(pages) >= 2:
                pages_str = "第%d-%d页" % (pages[0], pages[-1])
            elif pages:
                pages_str = "第%d页" % pages[0]
            else:
                pages_str = "页码未知"

            formatted.append({
                "index": i + 1,
                "company_name": r.get("company_name", "未知"),
                "source_file": r.get("source_file", "未知"),
                "pages": pages_str,
                "text": r.get("parent_text", ""),
                "relevance_score": round(r.get("scores", {}).get("rerank", 0.0), 1),
                "confidence": r.get("scores", {}).get("confidence", "unknown"),
            })

        logger.info("[RetrieveTool] 格式化完成: %d 条结果", len(formatted))
        return {
            "query": query,
            "company_name": company_name or "全部",
            "count": len(formatted),
            "results": formatted,
        }

    # ============================================================
    # 核心 run 方法
    # ============================================================

    def run(self, **kwargs) -> ToolResult:
        """执行检索

        参数校验 → 调用 HybridRetriever.search() → 格式化结果 → 返回 ToolResult

        Args:
            query (str): 检索查询文本，必填
            company_name (str): 公司名称，可选（不填则检索全部 4 家公司）
            top_n (int): 返回条数，默认 5，最大 10

        Returns:
            ToolResult: success=True 时 data 包含检索结果
                        success=False 时 error 包含错误信息
        """
        # ---- 参数校验 ----
        error = self._validate_params(["query"], **kwargs)
        if error:
            logger.warning("[RetrieveTool] 参数校验失败: %s", error)
            return ToolResult(success=False, error=error)

        query = kwargs["query"]
        company_name = kwargs.get("company_name", None)
        top_n = min(kwargs.get("top_n", 5), 10)

        logger.info("[RetrieveTool] ====== 检索开始 ======")
        logger.info("[RetrieveTool] query='%s', company=%s, top_n=%d",
                     query[:80] + ("..." if len(query) > 80 else ""),
                     company_name or "全部",
                     top_n)

        # ---- 执行检索 ----
        try:
            retriever = self._get_retriever()
            results = retriever.search(
                query=query,
                company_name=company_name,
                top_n=top_n,
            )
        except FileNotFoundError as e:
            logger.error("[RetrieveTool] 检索失败: 索引文件不存在")
            return ToolResult(
                success=False,
                error=(
                    "向量数据库索引文件不存在。请先运行以下命令构建索引：\n"
                    "python src/ingestion.py"
                )
            )
        except ValueError as e:
            logger.error("[RetrieveTool] 检索失败: 参数错误 - %s", str(e))
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            logger.error("[RetrieveTool] 检索失败: 未知异常 - %s", str(e))
            return ToolResult(success=False, error="检索异常: %s" % str(e))

        # ---- 空结果处理 ----
        if not results:
            logger.info("[RetrieveTool] ====== 检索完成: 0 条结果 ======")
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "company_name": company_name or "全部",
                    "count": 0,
                    "message": (
                        "未检索到相关数据。建议：\n"
                        "1. 调整查询关键词，补充具体信息（如年份、指标名称）\n"
                        "2. 去掉公司限制，扩大检索范围\n"
                        "3. 确认查询的公司名称拼写正确"
                    ),
                    "results": [],
                }
            )

        # ---- 格式化并返回 ----
        formatted_results = self._format_results(results, query, company_name)
        logger.info("[RetrieveTool] ====== 检索完成: %d 条结果 ======", len(results))
        return ToolResult(success=True, data=formatted_results)
