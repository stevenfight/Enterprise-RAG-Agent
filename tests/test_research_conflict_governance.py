# -*- coding: utf-8 -*-
"""E-T16 服务端冲突治理上下文与审批绑定契约。"""

from datetime import datetime, timedelta, timezone

import pytest

from src.durable_execution import DurableExecutionStore
from src.financial_fact_conflict_repository import FinancialFactConflictRepository
from src.financial_fact_conflict_service import FinancialFactConflictDecision
from src.research_delivery import ResearchPlan
from src.research_plan_repository import ResearchPlanRepository
from src.research_task_adapter import ResearchTaskAdapter
from src.v7_metadata_store import V7MetadataStore


NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)


def _harness(tmp_path):
    from src.research_conflict_governance import (
        ResearchConflictApprovalService,
        ResearchConflictContext,
        ResearchConflictContextRepository,
    )

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    execution_store = DurableExecutionStore(store)
    adapter = ResearchTaskAdapter(execution_store)
    adapter.create_task("task-1", ["review"])
    plan = ResearchPlan.create(
        plan_id="plan-1", task_id="task-1", objective="核查冲突",
        scope=["收入"], step_ids=["review"], estimated_cost="1.00",
    )
    ResearchPlanRepository(store).append(plan)
    FinancialFactConflictRepository(store).save(
        "conflict-1",
        FinancialFactConflictDecision("pending_review", "VALUE_CONFLICT", ("fact-a", "fact-b"), "0.10"),
    )
    contexts = ResearchConflictContextRepository(store)
    service = ResearchConflictApprovalService(execution_store, contexts, clock=lambda: NOW)
    context = ResearchConflictContext.create(
        task_id="task-1", run_id="research:task-1", conflict_id="conflict-1",
        fact_version="facts-v1", artifact_version="artifacts-v1", index_generation="generation-v1",
    )
    return store, contexts, service, context


def test_context_versions_are_append_only_and_current_context_is_latest(tmp_path) -> None:
    _, contexts, _, context = _harness(tmp_path)

    first = contexts.append(context)
    second = contexts.append(context.with_versions(
        fact_version="facts-v2", artifact_version="artifacts-v2", index_generation="generation-v2",
    ))

    assert first.context_version == 1
    assert second.context_version == 2
    assert contexts.current_for("task-1", "conflict-1") == second
    assert contexts.history("task-1", "conflict-1") == (first, second)


def test_server_grants_conflict_approval_from_current_task_plan_and_context(tmp_path) -> None:
    _, contexts, service, context = _harness(tmp_path)
    contexts.append(context)

    granted = service.grant(
        task_id="task-1", conflict_id="conflict-1", action="approve",
        selected_fact_id="fact-a", approver="auditor", expires_at=NOW + timedelta(hours=1),
    )

    assert granted.approval.status == "granted"
    assert granted.binding.task_revision == 0
    assert granted.binding.fact_version == "facts-v1"
    assert granted.binding.artifact_version == "artifacts-v1"
    assert granted.binding.index_generation == "generation-v1"
    assert granted.binding.plan_hash


def test_plan_binding_hash_includes_approved_step_inputs_and_agent_bindings() -> None:
    """审批绑定必须覆盖所有会影响研究执行权限和结果的计划字段。"""
    from src.research_conflict_governance import _plan_hash

    calculated = ResearchPlan.create(
        plan_id="plan-binding", task_id="task-binding", objective="计算收入同比",
        scope=["营业收入"], step_ids=["calculate"], estimated_cost="1.00",
        step_bindings={"calculate": {"agent_name": "CalcAgent", "tool_names": ["calculator"]}},
        step_inputs={"calculate": {"operation": "yoy_growth", "current": 120, "previous": 100}},
    )
    changed_input = ResearchPlan.create(
        plan_id="plan-binding", task_id="task-binding", objective="计算收入同比",
        scope=["营业收入"], step_ids=["calculate"], estimated_cost="1.00",
        step_bindings={"calculate": {"agent_name": "CalcAgent", "tool_names": ["calculator"]}},
        step_inputs={"calculate": {"operation": "yoy_growth", "current": 121, "previous": 100}},
    )
    changed_binding = ResearchPlan.create(
        plan_id="plan-binding", task_id="task-binding", objective="计算收入同比",
        scope=["营业收入"], step_ids=["calculate"], estimated_cost="1.00",
        step_bindings={"calculate": {"agent_name": "RestrictedCalcAgent", "tool_names": ["calculator"]}},
        step_inputs={"calculate": {"operation": "yoy_growth", "current": 120, "previous": 100}},
    )

    assert _plan_hash(calculated) != _plan_hash(changed_input)
    assert _plan_hash(calculated) != _plan_hash(changed_binding)


def test_server_refuses_approval_when_context_is_missing_or_action_is_not_approvable(tmp_path) -> None:
    _, contexts, service, context = _harness(tmp_path)

    with pytest.raises(ValueError, match="上下文"):
        service.grant(
            task_id="task-1", conflict_id="conflict-1", action="approve",
            selected_fact_id="fact-a", approver="auditor", expires_at=NOW + timedelta(hours=1),
        )

    contexts.append(context)
    with pytest.raises(ValueError, match="不需要审批"):
        service.grant(
            task_id="task-1", conflict_id="conflict-1", action="keep_pending",
            selected_fact_id=None, approver="auditor", expires_at=NOW + timedelta(hours=1),
        )


def test_server_refuses_an_expired_conflict_approval(tmp_path) -> None:
    _, contexts, service, context = _harness(tmp_path)
    contexts.append(context)

    with pytest.raises(ValueError, match="有效期"):
        service.grant(
            task_id="task-1", conflict_id="conflict-1", action="reject",
            selected_fact_id=None, approver="auditor", expires_at=NOW,
        )
