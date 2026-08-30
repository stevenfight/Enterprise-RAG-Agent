"""D1.4 只追加审计事件与任务回放测试（D-T07）。

规格依据：spec-governance-operations.md「审计与脱敏」——审核人员查询任务时，
可按时间还原计划、工具、审批、关键输入输出、模型版本和最终结论；
审计事件只追加，不提供覆盖历史的路径。
"""

from __future__ import annotations

import pytest

from src.governance.audit import AuditEvent, GovernanceAuditStore
from src.v7_metadata_store import V7MetadataStore


@pytest.fixture()
def metadata_store(tmp_path):
    """每个用例独立初始化的 V7 元数据库。"""
    store = V7MetadataStore(tmp_path / "governance.db")
    store.initialize()
    return store


def _event(
    task_id: str,
    action: str,
    resource: str,
    result: str = "ok",
    actor: str = "planner",
    detail: dict | None = None,
    correlation_id: str = "corr-1",
    run_id: str = "run-1",
) -> AuditEvent:
    """构造审计事件，字段与 design.md 审计事件定义对齐。"""
    return AuditEvent(
        task_id=task_id,
        run_id=run_id,
        actor=actor,
        action=action,
        resource=resource,
        result=result,
        detail=detail or {},
        correlation_id=correlation_id,
    )


def test_append_and_replay_rebuilds_critical_path(metadata_store) -> None:
    """D-T07：审计事件按时间重建计划、工具、关键输入输出、模型版本与结论。"""
    audit = GovernanceAuditStore(metadata_store)
    audit.append(_event("task-1", "plan_created", "task:task-1", detail={"steps": ["fetch", "analyze"]}))
    audit.append(
        _event(
            "task-1",
            "route_selected",
            "task:task-1",
            actor="router",
            detail={"path": "single", "reason": "复杂度低"},
        )
    )
    audit.append(
        _event(
            "task-1",
            "tool_executed",
            "tool:retrieve_financial_fact",
            actor="worker",
            detail={"params": {"fact_id": "F1"}, "model_version": "qwen-max"},
        )
    )
    audit.append(_event("task-1", "conclusion_recorded", "task:task-1", detail={"summary": "营收增长"}))

    records = audit.replay_task("task-1")
    assert [record.event.action for record in records] == [
        "plan_created",
        "route_selected",
        "tool_executed",
        "conclusion_recorded",
    ]
    created_at = [record.created_at for record in records]
    assert created_at == sorted(created_at)
    tool_record = records[2]
    assert tool_record.event.detail["model_version"] == "qwen-max"
    assert tool_record.event.detail["params"] == {"fact_id": "F1"}
    assert tool_record.event.actor == "worker"
    assert tool_record.audit_id > 0


def test_audit_store_is_append_only(metadata_store) -> None:
    """审计账本只追加：同动作重复记录只新增行，不覆盖历史。"""
    audit = GovernanceAuditStore(metadata_store)
    first = audit.append(_event("task-2", "plan_created", "task:task-2"))
    second = audit.append(_event("task-2", "plan_created", "task:task-2"))
    assert second.audit_id > first.audit_id
    assert len(audit.replay_task("task-2")) == 2


def test_replay_is_isolated_per_task(metadata_store) -> None:
    """回放按任务隔离，不返回其他任务的事件。"""
    audit = GovernanceAuditStore(metadata_store)
    audit.append(_event("task-a", "plan_created", "task:task-a"))
    audit.append(_event("task-b", "plan_created", "task:task-b"))
    assert [record.event.task_id for record in audit.replay_task("task-a")] == ["task-a"]


def test_append_rejects_empty_action(metadata_store) -> None:
    """action 为空的审计事件拒绝写入，保证回放语义完整。"""
    audit = GovernanceAuditStore(metadata_store)
    with pytest.raises(ValueError):
        audit.append(_event("task-3", "", "task:task-3"))
