"""D1.2/D1.2.1/D1.3/D1.4.1 审批模块测试。

覆盖：
- D-T02 关键冲突裁决或正式报告签发无审批时阻止（D1.3 门禁）；
- D-T03 审批参数变化后失效（D1.2 参数绑定）与过期失效（D1.2 时效限制）；
- D-T11 task revision、事实/制品版本或索引代际变化使审批失效（D1.2.1）；
- D-T12 审批消费、业务状态与审计事件同事务提交（D1.4.1）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.governance.approval import (
    SUBJECT_CONFLICT_RESOLUTION,
    SUBJECT_REPORT_SIGNOFF,
    SUBJECT_TOOL_EXECUTION,
    ApprovalBinding,
    ApprovalRequest,
    GovernanceApprovalStore,
)
from src.v7_metadata_store import V7MetadataStore

FIXED_NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
LATER_NOW = FIXED_NOW + timedelta(hours=2)


@pytest.fixture()
def metadata_store(tmp_path):
    """每个用例独立初始化的 V7 元数据库。"""
    store = V7MetadataStore(tmp_path / "governance.db")
    store.initialize()
    return store


def _binding(**overrides) -> ApprovalBinding:
    """构造审批依赖绑定，允许逐字段覆盖以验证 D-T11。"""
    values = dict(
        task_revision=3,
        plan_hash="plan-abc",
        fact_version="fact-v1",
        artifact_version="artifact-v1",
        index_generation="gen-7",
    )
    values.update(overrides)
    return ApprovalBinding(**values)


def _request(**overrides) -> ApprovalRequest:
    """构造审批请求，允许逐字段覆盖。"""
    values = dict(
        task_id="task-1",
        run_id="run-1",
        subject=SUBJECT_CONFLICT_RESOLUTION,
        subject_id="conflict-42",
        params={"resolution": "use_fact_v2", "fact_id": "F1"},
        binding=_binding(),
        approver="auditor-a",
        expires_at=FIXED_NOW + timedelta(hours=1),
    )
    values.update(overrides)
    return ApprovalRequest(**values)


def test_gate_blocks_conflict_and_report_without_approval(metadata_store) -> None:
    """D-T02：关键冲突裁决与正式报告签发在无审批时必须被阻止。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    conflict = approvals.check_gate("task-1", SUBJECT_CONFLICT_RESOLUTION, "conflict-42", {"resolution": "use_fact_v2"}, _binding())
    report = approvals.check_gate("task-1", SUBJECT_REPORT_SIGNOFF, "report-9", {"format": "markdown"}, _binding())
    assert conflict.allowed is False
    assert report.allowed is False
    assert conflict.reason == "missing"
    assert report.reason == "missing"


def test_gate_allows_with_valid_approval(metadata_store) -> None:
    """D-T02：持有效审批且参数与依赖一致时门禁放行。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    granted = approvals.grant(_request())
    decision = approvals.check_gate(
        "task-1", SUBJECT_CONFLICT_RESOLUTION, "conflict-42", {"resolution": "use_fact_v2", "fact_id": "F1"}, _binding()
    )
    assert decision.allowed is True
    assert decision.approval_id == granted.approval_id


def test_params_change_invalidates_approval(metadata_store) -> None:
    """D-T03：审批与规范化参数绑定，参数变化后必须重新审批。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    approvals.grant(_request())
    decision = approvals.check_gate(
        "task-1", SUBJECT_CONFLICT_RESOLUTION, "conflict-42", {"resolution": "keep_pending", "fact_id": "F1"}, _binding()
    )
    assert decision.allowed is False
    assert decision.reason == "params_changed"


def test_expiry_invalidates_approval(metadata_store) -> None:
    """D1.2 时效限制：超过 expires_at 后旧审批失效，需重新审批。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    approvals.grant(_request())
    later = GovernanceApprovalStore(metadata_store, clock=lambda: LATER_NOW)
    decision = later.check_gate(
        "task-1", SUBJECT_CONFLICT_RESOLUTION, "conflict-42", {"resolution": "use_fact_v2", "fact_id": "F1"}, _binding()
    )
    assert decision.allowed is False
    assert decision.reason == "expired"


@pytest.mark.parametrize(
    "changed",
    [
        {"task_revision": 4},
        {"plan_hash": "plan-xyz"},
        {"fact_version": "fact-v2"},
        {"artifact_version": "artifact-v2"},
        {"index_generation": "gen-8"},
    ],
)
def test_dependency_change_invalidates_approval(metadata_store, changed) -> None:
    """D-T11：任一依赖变化（revision/计划/事实/制品/索引代际）使旧审批失效。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    approvals.grant(_request())
    stale_binding = _binding(**changed)
    decision = approvals.check_gate(
        "task-1",
        SUBJECT_CONFLICT_RESOLUTION,
        "conflict-42",
        {"resolution": "use_fact_v2", "fact_id": "F1"},
        stale_binding,
    )
    assert decision.allowed is False
    assert decision.reason == "dependencies_changed"


def test_consume_marks_consumed_and_appends_audit(metadata_store) -> None:
    """D1.4.1：消费审批与审计事件在同一事务提交，审批不可重复消费。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    granted = approvals.grant(_request())
    consumed = approvals.consume(granted.approval_id, actor="orchestrator")
    assert consumed.status == "consumed"
    assert consumed.consumed_at is not None
    audit_events = approvals.audit.replay_task("task-1")
    assert [event.action for event in audit_events][-1] == "approval_consumed"
    with pytest.raises(ValueError):
        approvals.consume(granted.approval_id, actor="orchestrator")


def test_consumed_approval_no_longer_passes_gate(metadata_store) -> None:
    """已消费的审批不能再次通过门禁，防止一次审批多次放行。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    granted = approvals.grant(_request())
    approvals.consume(granted.approval_id, actor="orchestrator")
    decision = approvals.check_gate(
        "task-1", SUBJECT_CONFLICT_RESOLUTION, "conflict-42", {"resolution": "use_fact_v2", "fact_id": "F1"}, _binding()
    )
    assert decision.allowed is False
    assert decision.reason == "missing"


def test_same_transaction_commits_business_consumption_and_audit(metadata_store) -> None:
    """D-T12：业务状态迁移、审批消费与审计事件同事务提交，三者要么全部生效。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    granted = approvals.grant(_request())

    def business_transition(connection) -> None:
        connection.execute(
            "INSERT INTO v7_store_metadata(key, value) VALUES ('governance-dt12', 'conflict_resolved')"
        )

    approvals.consume_in_transaction(granted.approval_id, actor="orchestrator", business_transition=business_transition)
    with metadata_store.connect() as connection:
        business_value = connection.execute(
            "SELECT value FROM v7_store_metadata WHERE key = 'governance-dt12'"
        ).fetchone()[0]
    assert business_value == "conflict_resolved"
    assert approvals.valid_approval(
        "task-1", SUBJECT_CONFLICT_RESOLUTION, "conflict-42", {"resolution": "use_fact_v2", "fact_id": "F1"}, _binding()
    ) is None
    assert [event.action for event in approvals.audit.replay_task("task-1")][-1] == "approval_consumed"


def test_same_transaction_rolls_back_on_business_failure(metadata_store) -> None:
    """D-T12：业务迁移失败时回滚全部——审批保持 granted 且不产生审计。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    granted = approvals.grant(_request())

    def failing_transition(_connection) -> None:
        raise RuntimeError("业务状态迁移失败")

    with pytest.raises(RuntimeError):
        approvals.consume_in_transaction(
            granted.approval_id, actor="orchestrator", business_transition=failing_transition
        )
    status = approvals.approval_status(granted.approval_id)
    assert status == "granted"
    assert approvals.audit.replay_task("task-1") == ()


def test_tool_execution_subject_channel_available(metadata_store) -> None:
    """D1.3：工具执行审批通道可用，但当前无真实高风险工具时不强制启用。"""
    approvals = GovernanceApprovalStore(metadata_store, clock=lambda: FIXED_NOW)
    granted = approvals.grant(
        _request(
            subject=SUBJECT_TOOL_EXECUTION,
            subject_id="publish_index",
            params={"target": "index-gen-8"},
        )
    )
    decision = approvals.check_gate(
        "task-1", SUBJECT_TOOL_EXECUTION, "publish_index", {"target": "index-gen-8"}, _binding()
    )
    assert decision.allowed is True
    assert decision.approval_id == granted.approval_id
