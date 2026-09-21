# -*- coding: utf-8 -*-
"""E1.5 冲突裁决的 RED→GREEN 契约。"""

from datetime import datetime, timedelta, timezone

import pytest

from src.financial_fact_conflict_repository import FinancialFactConflictRepository
from src.financial_fact_conflict_service import FinancialFactConflictDecision
from src.governance.approval import ApprovalBinding, ApprovalRequest, GovernanceApprovalStore, SUBJECT_CONFLICT_RESOLUTION
from src.research_conflict_review import ConflictReviewAction, ResearchConflictReviewStore
from src.v7_metadata_store import V7MetadataStore


NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _binding() -> ApprovalBinding:
    return ApprovalBinding(0, "plan-v1", "facts-v1", "artifacts-v1", "generation-v1")


def test_keep_pending_and_approved_resolution_preserve_original_conflict(tmp_path) -> None:
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    conflicts = FinancialFactConflictRepository(store)
    conflicts.save("conflict-1", FinancialFactConflictDecision("pending_review", "VALUE_CONFLICT", ("fact-a", "fact-b"), "0.10", "fact-a"))
    reviews = ResearchConflictReviewStore(store, clock=lambda: NOW)

    pending = reviews.resolve(task_id="task-1", run_id="research:task-1", conflict_id="conflict-1", action=ConflictReviewAction.KEEP_PENDING, selected_fact_id=None, binding=_binding(), actor="reviewer", approvals=None, approval_id=None)
    assert pending.action is ConflictReviewAction.KEEP_PENDING
    assert pending.fact_ids == ("fact-a", "fact-b")
    assert conflicts.get("conflict-1").status == "pending_review"

    approvals = GovernanceApprovalStore(store, clock=lambda: NOW)
    granted = approvals.grant(ApprovalRequest("task-1", "research:task-1", SUBJECT_CONFLICT_RESOLUTION, "conflict-1", {"action": "approve", "selected_fact_id": "fact-a"}, _binding(), "auditor", NOW + timedelta(hours=1)))
    approved = reviews.resolve(task_id="task-1", run_id="research:task-1", conflict_id="conflict-1", action=ConflictReviewAction.APPROVE, selected_fact_id="fact-a", binding=_binding(), actor="reviewer", approvals=approvals, approval_id=granted.approval_id)
    assert approved.action is ConflictReviewAction.APPROVE
    assert approved.selected_fact_id == "fact-a"
    assert approvals.approval_status(granted.approval_id) == "consumed"
    assert [item.action for item in reviews.history("conflict-1")] == [ConflictReviewAction.KEEP_PENDING, ConflictReviewAction.APPROVE]


def test_reject_requires_matching_approval_and_never_consumes_on_mismatch(tmp_path) -> None:
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    FinancialFactConflictRepository(store).save("conflict-2", FinancialFactConflictDecision("pending_review", "VALUE_CONFLICT", ("fact-a", "fact-b"), "0.10"))
    reviews = ResearchConflictReviewStore(store, clock=lambda: NOW)
    approvals = GovernanceApprovalStore(store, clock=lambda: NOW)
    granted = approvals.grant(ApprovalRequest("task-2", "research:task-2", SUBJECT_CONFLICT_RESOLUTION, "conflict-2", {"action": "reject", "selected_fact_id": None}, _binding(), "auditor", NOW + timedelta(hours=1)))

    with pytest.raises(ValueError, match="审批"):
        reviews.resolve(task_id="task-2", run_id="research:task-2", conflict_id="conflict-2", action=ConflictReviewAction.REJECT, selected_fact_id=None, binding=_binding(), actor="reviewer", approvals=approvals, approval_id="wrong")
    assert approvals.approval_status(granted.approval_id) == "granted"
