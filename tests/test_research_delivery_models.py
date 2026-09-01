# -*- coding: utf-8 -*-
"""E1.1 研究交付领域模型的 RED→GREEN 契约。"""

from decimal import Decimal

import pytest

from src.research_delivery import (
    Claim,
    ClaimSupportKind,
    ReportReviewStatus,
    ResearchPlan,
    ResearchReport,
)


def test_research_plan_captures_stable_scope_budget_and_risks() -> None:
    """计划必须保存稳定任务边界，不能从缺失字段推测范围或预算。"""
    plan = ResearchPlan.create(
        plan_id="plan-2026-001",
        task_id="task-2026-001",
        objective="比较三家运营商的营业收入",
        scope=("中国移动", "中国电信", "中国联通"),
        step_ids=("retrieve", "compare", "review"),
        estimated_cost="12.50",
        risks=("跨公司口径差异",),
        plan_version=1,
    )

    assert plan.estimated_cost == Decimal("12.50")
    assert plan.scope == ("中国移动", "中国电信", "中国联通")
    assert plan.step_ids == ("retrieve", "compare", "review")


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"operation": "unknown", "current": 120, "previous": 100}, "不支持的计算操作"),
        ({"operation": "yoy_growth", "current": 120}, "缺少字段"),
        ({"operation": "yoy_growth", "current": 120, "previous": 100, "unapproved": 1}, "包含未批准字段"),
        ({"operation": "yoy_growth", "current": True, "previous": 100}, "必须是有限数值"),
    ],
)
def test_calculate_step_input_requires_a_known_exact_calculator_contract(
    payload: dict[str, object], expected: str
) -> None:
    """审批快照必须拒绝 calculator 的未知操作、字段和非数值参数。"""
    with pytest.raises(ValueError, match=expected):
        ResearchPlan.create(
            plan_id="plan-calc-input",
            task_id="task-calc-input",
            objective="计算营业收入同比",
            scope=("营业收入",),
            step_ids=("calculate",),
            estimated_cost="1.00",
            step_inputs={"calculate": payload},
        )


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"companies": ["中国移动"], "metric": "营收", "year": "2024", "top_n": 3}, "至少需要两家"),
        ({"companies": ["中国移动", "中国电信"], "metric": "营收", "year": "20", "top_n": 3}, "年份"),
        ({"companies": ["中国移动", "中国电信"], "metric": "营收", "year": "2024", "top_n": 6}, "top_n"),
        ({"companies": ["中国移动", "中国电信"], "metric": "营收", "year": "2024", "top_n": 3, "unapproved": 1}, "包含未批准字段"),
    ],
)
def test_compare_step_input_requires_an_exact_approved_contract(
    payload: dict[str, object], expected: str
) -> None:
    """对比审批参数必须完整、受限且不能携带自由字段。"""
    with pytest.raises(ValueError, match=expected):
        ResearchPlan.create(
            plan_id="plan-compare-input",
            task_id="task-compare-input",
            objective="比较运营商营收",
            scope=("营收",),
            step_ids=("compare",),
            estimated_cost="1.00",
            step_inputs={"compare": payload},
        )


@pytest.mark.parametrize("payload", [
    {"data": {"中国移动": 100}, "chart_type": "scatter"},
    {"data": {"中国移动": True}, "chart_type": "bar"},
    {"data": {"中国移动": 100}, "chart_type": "bar", "unapproved": 1},
])
def test_chart_step_input_rejects_unapproved_type_data_and_fields(payload: dict[str, object]) -> None:
    """图表参数必须由审批快照完整给出，不接受自由类型和数值。"""
    with pytest.raises(ValueError):
        ResearchPlan.create(plan_id="plan-chart", task_id="task-chart", objective="生成图表", scope=("营收",), step_ids=("chart",), estimated_cost="1", step_inputs={"chart": payload})


def test_claim_requires_evidence_or_explicit_analysis_judgement() -> None:
    """关键声明不得在没有事实、计算、来源或分析判断标签时进入报告。"""
    with pytest.raises(ValueError, match="声明必须关联"):
        Claim.create(claim_id="claim-empty", text="某公司表现良好")

    analysed_claim = Claim.create(
        claim_id="claim-analysis",
        text="行业竞争正在加剧",
        support_kind=ClaimSupportKind.ANALYSIS,
        analysis_label="基于公开财报披露的定性分析",
    )

    assert analysed_claim.analysis_label == "基于公开财报披露的定性分析"
    assert analysed_claim.fact_ids == ()


def test_claim_rejects_duplicate_or_mismatched_support_references() -> None:
    """声明引用必须可审计，重复或与声明类型不匹配的引用一律拒绝。"""
    with pytest.raises(ValueError, match="重复"):
        Claim.create(
            claim_id="claim-duplicate",
            text="营业收入为 100 亿元",
            support_kind=ClaimSupportKind.FACT,
            fact_ids=("fact-1", "fact-1"),
        )

    with pytest.raises(ValueError, match="计算"):
        Claim.create(
            claim_id="claim-mismatch",
            text="营业收入同比增长 10%",
            support_kind=ClaimSupportKind.CALCULATION,
            fact_ids=("fact-1",),
        )


def test_research_report_uses_immutable_claims_and_explicit_review_status() -> None:
    """报告必须绑定计划和数据版本，并将审核状态作为显式领域字段。"""
    claim = Claim.create(
        claim_id="claim-fact",
        text="中国电信营业收入为 5,236 亿元",
        support_kind=ClaimSupportKind.FACT,
        fact_ids=("fact-telecom-revenue-2024",),
        source_ids=("source-annual-report-p87",),
    )

    report = ResearchReport.create(
        report_id="report-2026-001",
        task_id="task-2026-001",
        plan_id="plan-2026-001",
        report_version=1,
        data_version="publication-2026-001",
        review_status=ReportReviewStatus.PENDING_REVIEW,
        claims=(claim,),
    )

    assert report.review_status is ReportReviewStatus.PENDING_REVIEW
    assert report.claims == (claim,)

    with pytest.raises(ValueError, match="重复"):
        ResearchReport.create(
            report_id="report-duplicate-claims",
            task_id="task-2026-001",
            plan_id="plan-2026-001",
            report_version=1,
            data_version="publication-2026-001",
            review_status=ReportReviewStatus.DRAFT,
            claims=(claim, claim),
        )
