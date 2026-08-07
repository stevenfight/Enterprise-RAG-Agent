# -*- coding: utf-8 -*-
"""
查询复杂度路由器

实现三层路由的第一层（正则 + turbo 兜底），自动判断用户查询应走:
  - rag 模式：纯检索（不改现有逻辑）
  - agent 模式：单 Agent + 工具调用（不改现有逻辑）
  - multi_agent 模式：多 Agent 协作（步骤 0.3 仅标记，不执行）

第二层 Orchestrator 任务拆解在步骤 2.4 OrchestratorAgent 中实现。
第三层拓扑排序在步骤 3.1 并行调度中实现。

对应方案：多Agent升级方案 步骤 0.3
"""

import logging
import sys
from typing import Any, Dict, Optional

from src.planner import TaskPlanner, QueryCategory
from src.llm_provider import BaseLLMProvider, LLMResponse

logger = logging.getLogger("router")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


class RouteResult:
    """路由决策结果

    Attributes:
        mode: 路由模式 ("rag" / "agent" / "multi_agent")
        trace: 路由来源追踪 ("regex" / "turbo")
        category: planner 分类详情（正则命中时有值）
        reasoning: 路由决策说明
    """

    __slots__ = ("mode", "trace", "category", "reasoning")

    def __init__(self, mode: str, trace: str,
                 category: Optional[QueryCategory] = None,
                 reasoning: str = ""):
        self.mode = mode
        self.trace = trace
        self.category = category
        self.reasoning = reasoning

    def to_dict(self) -> Dict[str, Any]:
        """转为字典，方便日志和 SSE 事件"""
        result: Dict[str, Any] = {
            "mode": self.mode,
            "trace": self.trace,
            "reasoning": self.reasoning,
        }
        if self.category:
            result["category"] = {
                "type": self.category.category,
                "companies": self.category.company_names,
                "metrics": self.category.metric_names,
                "years": list(self.category.year_range),
                "need_chart": self.category.need_chart,
                "need_calculate": self.category.need_calculate,
                "need_compare": self.category.need_compare,
            }
        return result


class QueryRouter:
    """查询复杂度路由器

    三层路由的第一层调度器：
      - 1a: 复用 planner._classify_query() 正则分类（0 API 成本）
      - 1b: qwen-turbo 兜底分类（极低 API 成本）

    Usage:
        from src.llm_provider import DashScopeProvider
        turbo = DashScopeProvider(api_key="sk-xxx")
        router = QueryRouter(turbo_llm=turbo)

        result = router.route("中芯国际2024年营收")
        # result.mode == "rag", result.trace == "regex"

        result = router.route("三家运营商2024营收对比")
        # result.mode == "multi_agent", result.trace == "regex"

        result = router.route("中芯国际营收走势图")
        # result.mode 取决于 turbo 分类结果, trace == "turbo"
    """

    def __init__(self, turbo_llm: BaseLLMProvider):
        """初始化路由器

        Args:
            turbo_llm: 用于兜底分类的 LLM Provider（qwen-turbo）
        """
        self.turbo_llm = turbo_llm
        self._planner = TaskPlanner()
        self._route_count: Dict[str, int] = {"rag": 0, "agent": 0, "multi_agent": 0}
        self._trace_count: Dict[str, int] = {"regex": 0, "turbo": 0}
        logger.info("[QueryRouter] 初始化完成: turbo_model=qwen-turbo")

    def route(self, query: str, context: str = "") -> RouteResult:
        """对用户查询进行路由决策

        Args:
            query: 用户查询文本
            context: 历史对话上下文（用于 turbo 兜底分类时理解上下文）

        Returns:
            RouteResult: 含 mode / trace / category / reasoning
        """
        logger.info("[QueryRouter] 路由分析: query='%s'", query[:80])

        # ---- 第一层 1a：复用 planner._classify_query() 正则分类 ----
        category = self._planner._classify_query(query)

        logger.info("[QueryRouter] planner 分类结果: category=%s, companies=%s, "
                     "need_chart=%s, need_calculate=%s, need_compare=%s",
                     category.category, category.company_names,
                     category.need_chart, category.need_calculate, category.need_compare)

        # 路由规则
        # single: 单一查询 -> rag（不改现有 RAG 模式行为）
        if category.category == "single" and not category.need_calculate \
                and not category.need_chart:
            result = RouteResult(
                mode="rag", trace="regex", category=category,
                reasoning=f"正则分类: single, 无计算/图表需求, 走 RAG 模式",
            )
            self._record(result)
            return result

        # trend / compound: 单公司复合需求 -> agent
        if category.category in ("trend", "compound") or category.need_calculate:
            if len(category.company_names) < 2:
                result = RouteResult(
                    mode="agent", trace="regex", category=category,
                    reasoning=f"正则分类: {category.category}, 有计算需求, 走单 Agent 模式",
                )
                self._record(result)
                return result

        # multi_compare / 多公司 -> multi_agent
        if category.category == "multi_compare" or len(category.company_names) >= 2:
            result = RouteResult(
                mode="multi_agent", trace="regex", category=category,
                reasoning=f"正则分类: {category.category}, {len(category.company_names)}家公司, "
                          f"标记为 multi_agent 模式",
            )
            self._record(result)
            return result

        # ---- 第一层 1b：正则未明确 -> qwen-turbo 兜底分类 ----
        turbo_mode = self._turbo_classify(query, context)
        result = RouteResult(
            mode=turbo_mode, trace="turbo",
            reasoning=f"正则未命中, turbo 分类: {turbo_mode}",
        )
        self._record(result)
        return result

    def _turbo_classify(self, query: str, context: str) -> str:
        """用 qwen-turbo 做兜底三分类

        Args:
            query: 用户查询文本
            context: 历史对话上下文

        Returns:
            路由模式字符串 ("rag" / "agent" / "multi_agent")
        """
        prompt = (
            "你是路由分类器，只做一件事：判断用户查询属于以下哪类。\n"
            "- simple: 单一公司、单一问题，不需要对比，不需要计算\n"
            "- compound: 单一公司但需要计算增长率/趋势/画图等\n"
            "- multi: 涉及多公司对比，或多步骤复杂分析\n"
            "\n"
            "只输出一个词：simple / compound / multi。不要输出任何其他内容。\n"
        )
        if context:
            prompt += f"\n历史上下文: {context}\n"
        prompt += f"用户查询: {query}"

        logger.info("[QueryRouter] turbo 兜底分类: query='%s'", query[:80])
        response: LLMResponse = self.turbo_llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model="qwen-turbo",
            temperature=0.0,
            timeout=15,
        )

        if not response.success:
            logger.warning("[QueryRouter] turbo 分类失败: %s, 回退到 agent 模式", response.error)
            return "agent"

        answer = response.content.strip().lower()
        logger.info("[QueryRouter] turbo 分类结果: raw='%s', tokens=%d",
                     answer, response.usage.input_tokens + response.usage.output_tokens)

        if "multi" in answer:
            return "multi_agent"
        elif "compound" in answer:
            return "agent"
        else:
            return "rag"

    def _record(self, result: RouteResult):
        """记录路由统计"""
        self._route_count[result.mode] = self._route_count.get(result.mode, 0) + 1
        self._trace_count[result.trace] = self._trace_count.get(result.trace, 0) + 1
        logger.info("[QueryRouter] 路由决策: mode=%s, trace=%s | 累计统计: %s",
                     result.mode, result.trace,
                     {k: v for k, v in self._route_count.items() if v > 0})

    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计信息"""
        total = sum(self._route_count.values())
        return {
            "total_routes": total,
            "by_mode": dict(self._route_count),
            "by_trace": dict(self._trace_count),
            "regex_hit_rate": round(
                self._trace_count.get("regex", 0) / max(total, 1) * 100, 1
            ),
        }
