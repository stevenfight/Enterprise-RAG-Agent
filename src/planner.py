# -*- coding: utf-8 -*-
"""
任务规划器 (Agent 规划层)

将复杂用户查询拆解为可执行的子任务链，按依赖关系排序。

规划策略:
  - 单公司单指标: 不拆解，直接检索
  - 多公司对比: 按公司拆解为并行子查询
  - 趋势分析: 先检索历史数据，再生成趋势图表
  - 复合计算: 先检索原始数据，再调用 calculator

输出 TaskPlan，驱动 Agent 的 ReAct 循环按序执行子任务。

调用链路:
  用户输入 → TaskPlanner.plan(query) → TaskPlan.subtasks
    → Agent 逐个执行 → Reflector.verify()

对应 SDD: openspec/changes/rag-to-agent/design.md §2.3
对应 TDD: tests/test_agent_core.py (TC-A04 ~ TC-A06)
"""

import logging
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("planner")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


# ============================================================
# 枚举与数据结构
# ============================================================

class SubTaskType(str, Enum):
    """子任务类型"""
    RETRIEVE = "retrieve"        # 数据检索
    CALCULATE = "calculate"      # 指标计算
    COMPARE = "compare"          # 多公司对比 (内部会检索)
    CHART = "chart"              # 图表生成
    VERIFY = "verify"            # 数据验证
    REPORT = "report"            # 汇总输出


class DependencyType(str, Enum):
    """依赖关系类型"""
    NONE = "none"                # 无依赖，可并行
    SEQUENTIAL = "sequential"    # 顺序依赖 (B 必须在 A 之后)
    PARALLEL = "parallel"        # 可并行
    AGGREGATE = "aggregate"      # 聚合依赖 (C 依赖 A 和 B 全部完成)


@dataclass
class SubTask:
    """单个子任务

    Attributes:
        task_id: 任务唯一编号 (如 T1, T2)
        task_type: 任务类型 (检索/计算/对比/图表/验证/汇总)
        description: 任务描述文字
        tool_name: 对应的工具名称 (retrieve/calculator/compare/chart/verify)
        tool_params: 传递给工具的参数字典
        depends_on: 依赖的子任务 ID 列表
        priority: 优先级 (0 最高)
        status: 当前状态 (pending/running/completed/failed)
    """
    task_id: str
    task_type: SubTaskType
    description: str
    tool_name: str = ""
    tool_params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    priority: int = 0
    status: str = "pending"


@dataclass
class QueryCategory:
    """查询分类结果"""
    category: str                          # single / multi_compare / trend / compound
    company_names: List[str] = field(default_factory=list)
    metric_names: List[str] = field(default_factory=list)
    year_range: Tuple[Optional[int], Optional[int]] = (None, None)
    need_chart: bool = False
    need_calculate: bool = False
    need_compare: bool = False


@dataclass
class TaskPlan:
    """规划结果

    Attributes:
        original_query: 原始用户查询
        category: 查询类型分类
        subtasks: 子任务列表 (已按依赖排序)
        execution_order: 执行分组 (每批可并行的子任务)
        valid: 规划是否成功 (False 时 fallback 到直接检索)
    """
    original_query: str
    category: QueryCategory
    subtasks: List[SubTask] = field(default_factory=list)
    execution_order: List[List[str]] = field(default_factory=list)
    valid: bool = True
    message: str = ""


# ============================================================
# 关键词映射
# ============================================================

# 已知公司名 (用于检测用户提到了哪些公司)
COMPANY_NAMES = {"中芯国际", "中国移动", "中国联通", "中国电信"}

# 财务指标关键词
METRIC_KEYWORDS = {
    "营收": ["营收", "收入", "营业收入"],
    "净利润": ["净利润", "归母净利润"],
    "毛利率": ["毛利率"],
    "净利率": ["净利率"],
    "研发费用": ["研发费用", "研发投入"],
    "总资产": ["总资产"],
    "增长率": ["增长率", "增速", "同比增长"],
}

# 趋势/分析关键词
TREND_KEYWORDS = {"趋势", "变化", "走势", "历年", "近几年", "增长趋势",
                  "历史", "逐年", "几年", "走势图"}

# 对比关键词
COMPARE_KEYWORDS = {"对比", "比较", "哪个", "差距", "vs", "VS",
                    "和", "与", "及", "以及"}

# 计算关键词
CALC_KEYWORDS = {"同比增长", "增速", "CAGR", "复合增长率", "利润率"}


# ============================================================
# TaskPlanner
# ============================================================

class TaskPlanner:
    """任务规划器

    分析用户查询意图，拆解为子任务列表，确定执行顺序。

    使用方式:
        planner = TaskPlanner()
        plan = planner.plan("中国移动和中国联通2024年营收对比")
        for batch in plan.execution_order:
            # batch 是一组可并行执行的 task_id
            for tid in batch:
                subtask = plan.get_task(tid)
                # 执行 subtask...
    """

    def __init__(self):
        self._task_counter = 0
        logger.info("[Planner] 初始化完成")

    # ============================================================
    # 主入口: plan()
    # ============================================================

    def plan(self, query: str, context: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """分析查询并生成执行计划

        Args:
            query: 用户原始查询
            context: 可选上下文 (如已检索到的公司列表)

        Returns:
            TaskPlan: 包含子任务列表和执行顺序
        """
        logger.info("[Planner] ========== 开始规划 ==========")
        logger.info("[Planner] 查询: '%s'", query[:120] if len(query) > 120 else query)

        # ---- 1. 分类查询 ----
        category = self._classify_query(query)
        logger.info("[Planner] 查询分类: category=%s, companies=%s, metrics=%s, "
                     "years=%s, chart=%s, calc=%s, compare=%s",
                     category.category,
                     category.company_names,
                     category.metric_names,
                     category.year_range,
                     category.need_chart,
                     category.need_calculate,
                     category.need_compare)

        # ---- 2. 根据分类生成子任务 ----
        subtasks = self._build_subtasks(category, query)
        logger.info("[Planner] 生成 %d 个子任务", len(subtasks))
        for st in subtasks:
            logger.info("[Planner]   %s: type=%s, tool=%s, deps=%s, desc='%s'",
                         st.task_id, st.task_type.value, st.tool_name,
                         st.depends_on, st.description[:80])

        # ---- 3. 构建 DAG 执行顺序 ----
        execution_order = self._build_execution_order(subtasks)
        logger.info("[Planner] 执行顺序: %d 个批次", len(execution_order))
        for i, batch in enumerate(execution_order):
            logger.info("[Planner]   批次 %d: %s (可并行)", i + 1, batch)

        logger.info("[Planner] ========== 规划完成 ==========")

        return TaskPlan(
            original_query=query,
            category=category,
            subtasks=subtasks,
            execution_order=execution_order,
            valid=True,
        )

    # ---- 便捷方法 (TDD 兼容) ----

    def decompose(self, complex_query: str) -> List[Dict[str, Any]]:
        """拆解复杂查询为子任务列表 (兼容 TDD 接口)

        Returns:
            [{task_id, type, description}]
        """
        plan = self.plan(complex_query)
        return [
            {
                "task_id": st.task_id,
                "type": st.task_type.value,
                "description": st.description,
                "tool_name": st.tool_name,
                "depends_on": st.depends_on,
                "priority": st.priority,
            }
            for st in plan.subtasks
        ]

    def build_dag(self, tasks: List[Dict[str, Any]]) -> List[List[str]]:
        """构建执行顺序 (兼容 TDD 接口)

        Args:
            tasks: decompose 返回的子任务列表

        Returns:
            执行批次列表
        """
        subtasks = [
            SubTask(
                task_id=t["task_id"],
                task_type=SubTaskType(t["type"]),
                description=t["description"],
                tool_name=t.get("tool_name", ""),
                depends_on=t.get("depends_on", []),
                priority=t.get("priority", 0),
            )
            for t in tasks
        ]
        return self._build_execution_order(subtasks)

    # ============================================================
    # 1. 查询分类
    # ============================================================

    def _classify_query(self, query: str) -> QueryCategory:
        """将用户查询分类到标准类型

        分类优先级: trend > compound > multi_compare > single

        Returns:
            QueryCategory
        """
        # 提取公司名
        companies = [c for c in COMPANY_NAMES if c in query]
        logger.debug("[Planner] 检测到公司: %s", companies if companies else "(无)")

        # 提取指标
        metrics = []
        for metric_name, keywords in METRIC_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    if metric_name not in metrics:
                        metrics.append(metric_name)
                    break
        logger.debug("[Planner] 检测到指标: %s", metrics if metrics else "(无)")

        # 提取年份
        years = self._extract_years(query)
        logger.debug("[Planner] 检测到年份: %s", years if years[0] else "(无)")

        # 检测趋势
        need_chart = any(kw in query for kw in TREND_KEYWORDS)
        # 检测计算需求
        need_calculate = any(kw in query for kw in CALC_KEYWORDS)
        # 检测对比需求
        need_compare = len(companies) >= 2 or any(kw in query for kw in COMPARE_KEYWORDS)

        # 分类判定
        if need_chart and need_calculate:
            category = "trend"          # 趋势分析 → 检索+计算+图表
        elif need_calculate and companies:
            category = "compound"       # 复合计算 → 检索+计算
        elif need_compare and len(companies) >= 2:
            category = "multi_compare"  # 多公司对比 → 直接用 compare 工具
        elif need_compare:
            category = "multi_compare"  # 含对比关键词但未明确公司 → 仍按对比处理
        else:
            category = "single"         # 单查询 → 直接检索

        return QueryCategory(
            category=category,
            company_names=companies,
            metric_names=metrics,
            year_range=years,
            need_chart=need_chart,
            need_calculate=need_calculate,
            need_compare=need_compare,
        )

    def _extract_years(self, text: str) -> Tuple[Optional[int], Optional[int]]:
        """提取查询中的年份范围"""
        year_pattern = re.findall(r"\b(20[12]\d)\b", text)
        years = sorted(set(int(y) for y in year_pattern))
        if not years:
            return (None, None)
        if len(years) == 1:
            return (years[0], years[0])
        return (years[0], years[-1])

    # ============================================================
    # 2. 生成子任务
    # ============================================================

    def _build_subtasks(self, category: QueryCategory, query: str) -> List[SubTask]:
        """根据查询分类构建子任务列表

        Args:
            category: 查询分类结果
            query: 原始查询

        Returns:
            子任务列表
        """
        self._task_counter = 0
        tasks: List[SubTask] = []

        if category.category == "single":
            tasks = self._build_single(category, query)
        elif category.category == "multi_compare":
            tasks = self._build_multi_compare(category, query)
        elif category.category == "trend":
            tasks = self._build_trend(category, query)
        elif category.category == "compound":
            tasks = self._build_compound(category, query)

        logger.info("[Planner] 策略: %s → %d 个子任务", category.category, len(tasks))
        return tasks

    def _next_id(self) -> str:
        self._task_counter += 1
        return "T%d" % self._task_counter

    def _build_single(self, cat: QueryCategory, query: str) -> List[SubTask]:
        """单公司单指标: 检索 → 验证"""
        tid = self._next_id()

        params = {"query": query}
        if cat.company_names:
            params["company_name"] = cat.company_names[0]

        retrieve = SubTask(
            task_id=tid,
            task_type=SubTaskType.RETRIEVE,
            description="检索: %s" % (cat.company_names[0] if cat.company_names else query[:40]),
            tool_name="retrieve",
            tool_params=params,
            priority=0,
        )

        verify = SubTask(
            task_id=self._next_id(),
            task_type=SubTaskType.VERIFY,
            description="验证检索结果中的数据准确性",
            tool_name="verify",
            tool_params={"query": query},
            depends_on=[tid],
            priority=1,
        )

        return [retrieve, verify]

    def _build_multi_compare(self, cat: QueryCategory, query: str) -> List[SubTask]:
        """多公司对比: 直接用 compare_tool (内部会自行检索)

        依赖策略:
          - 不预先检索，compare_tool 的三层保底机制已自行处理
          - 对比结果出来后做一次验证
        """
        tid1 = self._next_id()
        metric = cat.metric_names[0] if cat.metric_names else "营收"
        year = cat.year_range[0] if cat.year_range[0] else 2024

        compare = SubTask(
            task_id=tid1,
            task_type=SubTaskType.COMPARE,
            description="对比 %s: %s年%s" % (
                "、".join(cat.company_names) if cat.company_names else "各公司",
                year, metric
            ),
            tool_name="compare",
            tool_params={
                "companies": cat.company_names,
                "metric": metric,
                "year": year,
            },
            priority=0,
        )

        verify = SubTask(
            task_id=self._next_id(),
            task_type=SubTaskType.VERIFY,
            description="验证对比结果的数值准确性",
            tool_name="verify",
            tool_params={"query": query},
            depends_on=[tid1],
            priority=1,
        )

        return [compare, verify]

    def _build_trend(self, cat: QueryCategory, query: str) -> List[SubTask]:
        """趋势分析: 检索历史数据 → 计算 → 图表

        依赖: chart 依赖计算完成后的数据
        """
        tid_retrieve = self._next_id()
        tid_calc = self._next_id()
        tid_chart = self._next_id()

        company = cat.company_names[0] if cat.company_names else ""
        metric = cat.metric_names[0] if cat.metric_names else "营收"
        years = cat.year_range[0] if cat.year_range[0] else 2024

        retrieve = SubTask(
            task_id=tid_retrieve,
            task_type=SubTaskType.RETRIEVE,
            description="检索 %s 历年%s数据" % (company, metric),
            tool_name="retrieve",
            tool_params={
                "query": "%s %s 历年" % (company, metric),
                "company_name": company,
            },
            priority=0,
        )

        calculate = SubTask(
            task_id=tid_calc,
            task_type=SubTaskType.CALCULATE,
            description="计算 %s %s 年增长率" % (company, metric),
            tool_name="calculator",
            tool_params={
                "operation": "yoy_growth",
                "current": 0,      # 由 Agent 填充实际值
                "previous": 0,
            },
            depends_on=[tid_retrieve],
            priority=1,
        )

        chart = SubTask(
            task_id=tid_chart,
            task_type=SubTaskType.CHART,
            description="生成 %s %s 趋势图表" % (company, metric),
            tool_name="chart",
            tool_params={
                "chart_type": "line",
                "title": "%s %s 趋势" % (company, metric),
                "data": {},        # 由 Agent 填充
            },
            depends_on=[tid_retrieve, tid_calc],
            priority=2,
        )

        return [retrieve, calculate, chart]

    def _build_compound(self, cat: QueryCategory, query: str) -> List[SubTask]:
        """复合计算: 检索原始数据 → 多指标计算

        依赖: 计算依赖检索结果
        """
        tid_retrieve = self._next_id()
        tid_calc = self._next_id()

        company = cat.company_names[0] if cat.company_names else ""

        retrieve = SubTask(
            task_id=tid_retrieve,
            task_type=SubTaskType.RETRIEVE,
            description="检索 %s 财务数据" % (company or "相关公司"),
            tool_name="retrieve",
            tool_params={
                "query": query,
                "company_name": company if company else None,
            },
            priority=0,
        )

        metric_desc = "、".join(cat.metric_names[:2]) if cat.metric_names else "财务指标"
        calculate = SubTask(
            task_id=tid_calc,
            task_type=SubTaskType.CALCULATE,
            description="计算 %s %s" % (company, metric_desc),
            tool_name="calculator",
            tool_params={
                "operation": "yoy_growth",
                "current": 0,
                "previous": 0,
            },
            depends_on=[tid_retrieve],
            priority=1,
        )

        return [retrieve, calculate]

    # ============================================================
    # 3. 执行顺序 (DAG 拓扑排序)
    # ============================================================

    def _build_execution_order(self, subtasks: List[SubTask]) -> List[List[str]]:
        """构建 DAG 拓扑排序，按批次分组

        算法:
          1. 每批找出所有依赖已满足的未执行任务
          2. 同批任务可并行执行
          3. 重复直到所有任务执行完毕

        Args:
            subtasks: 子任务列表

        Returns:
            执行批次列表
        """
        if not subtasks:
            return []

        # 构建索引
        task_map = {st.task_id: st for st in subtasks}
        remaining = set(st.task_id for st in subtasks)
        completed = set()
        batches = []

        while remaining:
            batch = []
            for tid in sorted(remaining):  # 按 ID 字母序保证确定性
                st = task_map[tid]
                if all(dep in completed for dep in st.depends_on):
                    batch.append(tid)
                else:
                    pending = [d for d in st.depends_on if d not in completed]
                    logger.debug("[Planner] %s 等待依赖: %s", tid, pending)

            if not batch:
                # 检测到循环依赖
                logger.error("[Planner] 循环依赖检测: 无法继续排布, 剩余任务=%s", remaining)
                break

            batches.append(batch)
            for tid in batch:
                remaining.remove(tid)
                completed.add(tid)

        logger.info("[Planner] DAG 排序完成: %d 个批次, %d 个任务",
                     len(batches), len(subtasks))
        return batches
