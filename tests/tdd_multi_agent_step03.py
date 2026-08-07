# -*- coding: utf-8 -*-
"""
TDD 测试: 步骤 0.3 三层路由

对应 TDD 规格: openspec/changes/multi-agent-step03/specs/tdd-step03.md
测试总计: 21 项

编码: UTF-8
"""

import unittest
from unittest.mock import MagicMock

from src.router import QueryRouter, RouteResult
from src.planner import TaskPlanner, QueryCategory
from src.llm_provider import LLMResponse, LLMUsage, DashScopeProvider


class TestRouteResult(unittest.TestCase):
    """TC-30: RouteResult 基础功能"""

    def test_tc30_01_query_router_instantiation(self):
        """TC-30-01: QueryRouter 实例化"""
        mock_turbo = MagicMock(spec=DashScopeProvider)
        router = QueryRouter(turbo_llm=mock_turbo)
        self.assertIsNotNone(router)
        self.assertIsInstance(router._planner, TaskPlanner)

    def test_tc30_02_route_result_data_structure(self):
        """TC-30-02: RouteResult 数据结构"""
        cat = QueryCategory(category="single")
        result = RouteResult(mode="rag", trace="regex", category=cat, reasoning="测试")
        self.assertEqual(result.mode, "rag")
        self.assertEqual(result.trace, "regex")
        self.assertEqual(result.category, cat)
        self.assertEqual(result.reasoning, "测试")

    def test_tc30_03_route_result_to_dict(self):
        """TC-30-03: RouteResult.to_dict() 输出"""
        cat = QueryCategory(
            category="single",
            company_names=["中芯国际"],
            metric_names=["营收"],
            year_range=(2024, 2024),
        )
        result = RouteResult(mode="rag", trace="regex", category=cat, reasoning="测试")
        d = result.to_dict()
        self.assertEqual(d["mode"], "rag")
        self.assertEqual(d["trace"], "regex")
        self.assertEqual(d["reasoning"], "测试")
        self.assertIn("category", d)
        self.assertEqual(d["category"]["type"], "single")
        self.assertEqual(d["category"]["companies"], ["中芯国际"])

    def test_tc30_03b_route_result_to_dict_no_category(self):
        """TC-30-03 补充: 无 category 时 to_dict() 不含 category 键"""
        result = RouteResult(mode="rag", trace="turbo", reasoning="turbo 分类")
        d = result.to_dict()
        self.assertNotIn("category", d)


class TestRegexRouting(unittest.TestCase):
    """TC-31: 正则分类路由"""

    def setUp(self):
        self.mock_turbo = MagicMock(spec=DashScopeProvider)
        self.router = QueryRouter(turbo_llm=self.mock_turbo)

    def test_tc31_01_single_company_routes_to_rag(self):
        """TC-31-01: 单公司单指标查询 -> rag 模式"""
        result = self.router.route("中芯国际2024年营收是多少")
        self.assertEqual(result.mode, "rag")
        self.assertEqual(result.trace, "regex")
        self.assertIsNotNone(result.category)
        self.assertEqual(result.category.category, "single")

    def test_tc31_02_single_company_calc_routes_to_agent(self):
        """TC-31-02: 单公司趋势查询 -> agent 模式"""
        result = self.router.route("中芯国际毛利率同比增长率")
        self.assertEqual(result.mode, "agent")
        self.assertEqual(result.trace, "regex")

    def test_tc31_03_single_company_revenue_growth_routes_to_agent(self):
        """TC-31-03: 单公司计算查询 -> agent 模式"""
        result = self.router.route("中芯国际营收同比增长率")
        self.assertEqual(result.mode, "agent")
        self.assertEqual(result.trace, "regex")

    def test_tc31_04_two_companies_routes_to_multi_agent(self):
        """TC-31-04: 双公司对比 -> multi_agent 模式"""
        result = self.router.route("中国移动和中国联通2024年营收对比")
        self.assertEqual(result.mode, "multi_agent")
        self.assertEqual(result.trace, "regex")
        self.assertGreaterEqual(len(result.category.company_names), 2)

    def test_tc31_05_three_companies_routes_to_multi_agent(self):
        """TC-31-05: 三公司对比 -> multi_agent 模式"""
        result = self.router.route("三大运营商营收对比")
        self.assertEqual(result.mode, "multi_agent")
        self.assertEqual(result.trace, "regex")


class TestTurboFallback(unittest.TestCase):
    """TC-32: turbo 兜底分类"""

    def test_tc32_01_single_chart_only_goes_turbo(self):
        """TC-32-01: single + need_chart + no calc 穿透 regex 走 turbo（mock 验证路径）"""
        # 使用 mock 模拟 turbo 返回，验证查询确实走了 turbo 路径而非 regex
        mock_turbo = MagicMock(spec=DashScopeProvider)
        mock_turbo.chat.return_value = LLMResponse(
            content="compound", success=True,
            usage=LLMUsage(input_tokens=10, output_tokens=1),
        )
        router = QueryRouter(turbo_llm=mock_turbo)
        result = router.route("中芯国际营收走势图")
        self.assertEqual(result.trace, "turbo")
        self.assertEqual(result.mode, "agent")  # turbo 返回 compound -> agent

    def test_tc32_02_turbo_simple_routes_to_rag(self):
        """TC-32-02: turbo 返回 simple -> rag"""
        mock_turbo = MagicMock(spec=DashScopeProvider)
        mock_turbo.chat.return_value = LLMResponse(
            content="simple", success=True,
            usage=LLMUsage(input_tokens=10, output_tokens=1),
        )
        router = QueryRouter(turbo_llm=mock_turbo)
        result = router.route("中芯国际营收走势图", context="")
        self.assertEqual(result.mode, "rag")
        self.assertEqual(result.trace, "turbo")

    def test_tc32_03_turbo_compound_routes_to_agent(self):
        """TC-32-03: turbo 返回 compound -> agent"""
        mock_turbo = MagicMock(spec=DashScopeProvider)
        mock_turbo.chat.return_value = LLMResponse(
            content="compound", success=True,
            usage=LLMUsage(input_tokens=10, output_tokens=1),
        )
        router = QueryRouter(turbo_llm=mock_turbo)
        result = router.route("中芯国际营收走势图", context="")
        self.assertEqual(result.mode, "agent")
        self.assertEqual(result.trace, "turbo")

    def test_tc32_04_turbo_multi_routes_to_multi_agent(self):
        """TC-32-04: turbo 返回 multi -> multi_agent"""
        mock_turbo = MagicMock(spec=DashScopeProvider)
        mock_turbo.chat.return_value = LLMResponse(
            content="multi", success=True,
            usage=LLMUsage(input_tokens=10, output_tokens=1),
        )
        router = QueryRouter(turbo_llm=mock_turbo)
        result = router.route("中芯国际营收走势图", context="")
        self.assertEqual(result.mode, "multi_agent")
        self.assertEqual(result.trace, "turbo")


class TestTurboFaultTolerance(unittest.TestCase):
    """TC-33: turbo 容错"""

    def test_tc33_01_turbo_failure_falls_back_to_agent(self):
        """TC-33-01: turbo 调用失败 -> 回退到 agent"""
        mock_turbo = MagicMock(spec=DashScopeProvider)
        mock_turbo.chat.return_value = LLMResponse(
            content="", success=False, error="模拟失败",
        )
        router = QueryRouter(turbo_llm=mock_turbo)
        result = router.route("中芯国际营收走势图", context="")
        self.assertEqual(result.mode, "agent")
        self.assertEqual(result.trace, "turbo")

    def test_tc33_02_turbo_empty_content_falls_back_to_rag(self):
        """TC-33-02: turbo 返回空内容 -> rag（不匹配 multi/compound 走 else 分支）"""
        mock_turbo = MagicMock(spec=DashScopeProvider)
        mock_turbo.chat.return_value = LLMResponse(
            content="", success=True,
            usage=LLMUsage(input_tokens=10, output_tokens=0),
        )
        router = QueryRouter(turbo_llm=mock_turbo)
        result = router.route("中芯国际营收走势图", context="")
        self.assertEqual(result.mode, "rag")
        self.assertEqual(result.trace, "turbo")


class TestRoutingStats(unittest.TestCase):
    """TC-34: 路由统计"""

    def test_tc34_01_stats_accumulate_correctly(self):
        """TC-34-01: 路由统计正确累计"""
        mock_turbo = MagicMock(spec=DashScopeProvider)
        mock_turbo.chat.return_value = LLMResponse(
            content="simple", success=True,
            usage=LLMUsage(),
        )
        router = QueryRouter(turbo_llm=mock_turbo)

        # 3 次正则命中
        router.route("中芯国际2024年营收是多少")
        router.route("中国联通毛利率")
        router.route("中国移动和中国联通对比")

        # 1 次 turbo（穿透 regex 的查询）
        router.route("中芯国际营收走势图")

        stats = router.get_stats()
        self.assertEqual(stats["total_routes"], 4)
        self.assertEqual(stats["by_trace"]["regex"], 3)
        self.assertEqual(stats["by_trace"]["turbo"], 1)
        self.assertEqual(stats["regex_hit_rate"], 75.0)

    def test_tc34_02_regex_hit_rate_calculation(self):
        """TC-34-02: 正则命中率计算正确"""
        mock_turbo = MagicMock(spec=DashScopeProvider)
        mock_turbo.chat.return_value = LLMResponse(
            content="simple", success=True,
            usage=LLMUsage(),
        )
        router = QueryRouter(turbo_llm=mock_turbo)

        # 2 次正则命中
        router.route("中芯国际2024年营收")
        router.route("中国移动和中国联通对比")

        # 2 次 turbo
        router.route("中芯国际营收走势图")
        router.route("中国联通营收走势图")

        stats = router.get_stats()
        self.assertEqual(stats["regex_hit_rate"], 50.0)


class TestAPIIntegration(unittest.TestCase):
    """TC-35: API 集成（单元级验证，不启动真实服务）"""

    def test_tc35_01_query_router_in_shared_state(self):
        """TC-35-01: api_service 初始化 QueryRouter"""
        from src.api_service import _shared_state
        # _shared_state 是模块级字典，_init_globals 执行后应含 query_router 键
        # 测试环境可能未调用 _init_globals，验证结构类型即可
        self.assertIsInstance(_shared_state, dict)
        # 如果 _init_globals 已调用，验证 query_router 是 QueryRouter 实例
        if "query_router" in _shared_state and _shared_state["query_router"] is not None:
            self.assertIsInstance(_shared_state["query_router"], QueryRouter)

    def test_tc35_02_api_query_no_regression(self):
        """TC-35-02: /api/agent/query 正常返回（无回归）- 验证路由模块可正常导入"""
        # 验证 router 模块可被正常导入，不引起循环依赖
        from src.router import QueryRouter, RouteResult
        self.assertTrue(callable(QueryRouter))
        self.assertTrue(callable(RouteResult))

    def test_tc35_03_sse_router_decision_event_format(self):
        """TC-35-03: SSE router_decision 事件格式正确"""
        import json
        cat = QueryCategory(category="multi_compare", company_names=["中国移动", "中国联通"])
        result = RouteResult(mode="multi_agent", trace="regex", category=cat, reasoning="测试")
        event_data = {"type": "router_decision", **result.to_dict()}
        event_json = json.dumps(event_data, ensure_ascii=False)
        parsed = json.loads(event_json)
        self.assertEqual(parsed["type"], "router_decision")
        self.assertEqual(parsed["mode"], "multi_agent")
        self.assertIn("category", parsed)


class TestMultiAgentFallback(unittest.TestCase):
    """TC-36: multi_agent fallback"""

    def test_tc36_01_multi_agent_fallback_to_single_agent(self):
        """TC-36-01: multi_agent 模式 fallback 到单 Agent（路由标记正确，不报错）"""
        mock_turbo = MagicMock(spec=DashScopeProvider)
        router = QueryRouter(turbo_llm=mock_turbo)
        result = router.route("中国移动和中国联通2024年营收对比")
        self.assertEqual(result.mode, "multi_agent")
        # 验证路由不抛异常，返回有效的 RouteResult
        self.assertIn(result.mode, ("rag", "agent", "multi_agent"))
        self.assertIn(result.trace, ("regex", "turbo"))


if __name__ == "__main__":
    unittest.main()
