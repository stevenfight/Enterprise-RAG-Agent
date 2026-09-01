# -*- coding: utf-8 -*-
"""E1.4 范围调整与受影响步骤重规划的 RED→GREEN 契约。"""

from decimal import Decimal

import pytest

from src.research_delivery import ResearchPlan, ResearchPlanReplanner


def _plan() -> ResearchPlan:
    return ResearchPlan.create(
        plan_id="plan-2026-scope",
        task_id="task-2026-scope",
        objective="比较三家运营商的营业收入",
        scope=("移动", "电信", "联通"),
        step_ids=("retrieve", "compare", "review"),
        estimated_cost="10.00",
        risks=("口径差异",),
    )


def test_scope_change_recalculates_only_affected_steps_and_budget() -> None:
    """移除联通时，检索、其下游比较与审核重算，其他步骤不得被标记。"""
    result = ResearchPlanReplanner.replan(
        plan=_plan(),
        task_status="pending",
        new_scope=("移动", "电信"),
        step_scope_dependencies={
            "retrieve": ("移动", "电信", "联通"),
            "compare": (),
            "review": (),
        },
        step_dependencies={
            "retrieve": (),
            "compare": ("retrieve",),
            "review": ("compare",),
        },
        current_step_costs={"retrieve": "4.00", "compare": "4.00", "review": "2.00"},
        recalculated_step_costs={"retrieve": "3.00", "compare": "3.00", "review": "2.00"},
    )

    assert result.plan.plan_version == 2
    assert result.plan.scope == ("移动", "电信")
    assert result.affected_step_ids == ("retrieve", "compare", "review")
    assert result.unchanged_step_ids == ()
    assert result.plan.estimated_cost == Decimal("8.00")
    assert result.recalculated_step_costs == {
        "retrieve": Decimal("3.00"),
        "compare": Decimal("3.00"),
        "review": Decimal("2.00"),
    }


def test_unrelated_steps_keep_previous_cost_without_recalculation() -> None:
    """范围变更只影响目标检索；独立摘要步骤保留旧成本且不能传入新估算。"""
    plan = ResearchPlan.create(
        plan_id="plan-2026-isolated",
        task_id="task-2026-isolated",
        objective="比较两项指标",
        scope=("收入", "利润"),
        step_ids=("retrieve-revenue", "retrieve-profit", "summarize"),
        estimated_cost="9.00",
    )

    result = ResearchPlanReplanner.replan(
        plan=plan,
        task_status="pending",
        new_scope=("收入",),
        step_scope_dependencies={
            "retrieve-revenue": ("收入",),
            "retrieve-profit": ("利润",),
            "summarize": (),
        },
        step_dependencies={
            "retrieve-revenue": (),
            "retrieve-profit": (),
            "summarize": ("retrieve-revenue",),
        },
        current_step_costs={
            "retrieve-revenue": "3.00",
            "retrieve-profit": "4.00",
            "summarize": "2.00",
        },
        recalculated_step_costs={"retrieve-profit": "1.50"},
    )

    assert result.affected_step_ids == ("retrieve-profit",)
    assert result.unchanged_step_ids == ("retrieve-revenue", "summarize")
    assert result.plan.estimated_cost == Decimal("6.50")
    assert result.recalculated_step_costs == {"retrieve-profit": Decimal("1.50")}


def test_scope_change_is_rejected_after_execution_starts() -> None:
    """E1.4 仅允许执行前调整，避免覆盖运行中步骤的检查点。"""
    with pytest.raises(ValueError, match="pending"):
        ResearchPlanReplanner.replan(
            plan=_plan(),
            task_status="running",
            new_scope=("移动", "电信"),
            step_scope_dependencies={"retrieve": ("移动", "电信", "联通"), "compare": (), "review": ()},
            step_dependencies={"retrieve": (), "compare": ("retrieve",), "review": ("compare",)},
            current_step_costs={"retrieve": "4.00", "compare": "4.00", "review": "2.00"},
            recalculated_step_costs={"retrieve": "3.00", "compare": "3.00", "review": "2.00"},
        )


def test_replanning_rejects_incomplete_costs_and_cyclic_dag() -> None:
    """不完整预算或环形依赖不得生成看似可执行的新计划。"""
    with pytest.raises(ValueError, match="无环 DAG"):
        ResearchPlanReplanner.replan(
            plan=_plan(),
            task_status="pending",
            new_scope=("移动", "电信"),
            step_scope_dependencies={"retrieve": ("移动", "电信", "联通"), "compare": (), "review": ()},
            step_dependencies={"retrieve": ("review",), "compare": ("retrieve",), "review": ("compare",)},
            current_step_costs={"retrieve": "4.00", "compare": "4.00", "review": "2.00"},
            recalculated_step_costs={"retrieve": "3.00", "compare": "3.00", "review": "2.00"},
        )

    with pytest.raises(ValueError, match="计划预算"):
        ResearchPlanReplanner.replan(
            plan=_plan(),
            task_status="pending",
            new_scope=("移动", "电信"),
            step_scope_dependencies={"retrieve": ("移动", "电信", "联通"), "compare": (), "review": ()},
            step_dependencies={"retrieve": (), "compare": ("retrieve",), "review": ("compare",)},
            current_step_costs={"retrieve": "4.00", "compare": "4.00", "review": "1.00"},
            recalculated_step_costs={"retrieve": "3.00", "compare": "3.00", "review": "2.00"},
        )
