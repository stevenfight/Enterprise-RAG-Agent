# -*- coding: utf-8 -*-
"""E1.5 研究任务关键冲突的可审计裁决工作流。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable

from src.financial_fact_conflict_repository import FinancialFactConflictRepository
from src.governance.approval import ApprovalBinding, GovernanceApprovalStore, SUBJECT_CONFLICT_RESOLUTION
from src.v7_metadata_store import V7MetadataStore


class ConflictReviewAction(str, Enum):
    """用户对关键冲突的明确裁决动作。"""

    APPROVE = "approve"
    REJECT = "reject"
    KEEP_PENDING = "keep_pending"


@dataclass(frozen=True)
class ConflictReviewRecord:
    """不可变裁决记录，双方事实 ID 始终随记录保留。"""

    review_id: str
    task_id: str
    run_id: str
    conflict_id: str
    action: ConflictReviewAction
    selected_fact_id: str | None
    fact_ids: tuple[str, str]
    actor: str
    approval_id: str | None


class ResearchConflictReviewStore:
    """保存裁决历史；不修改原始 FinancialFactConflict 证据。"""

    def __init__(self, store: V7MetadataStore, *, clock: Callable[[], datetime]) -> None:
        self._store = store
        self._clock = clock
        self._conflicts = FinancialFactConflictRepository(store)
        store.initialize()

    def resolve(self, *, task_id: str, run_id: str, conflict_id: str, action: ConflictReviewAction,
                selected_fact_id: str | None, binding: ApprovalBinding, actor: str,
                approvals: GovernanceApprovalStore | None, approval_id: str | None) -> ConflictReviewRecord:
        """追加一次裁决；批准/驳回必须消费匹配且仍有效的治理审批。"""
        if not isinstance(action, ConflictReviewAction):
            raise ValueError("action 必须是受支持的冲突裁决动作")
        if not task_id or not run_id or not conflict_id or not actor:
            raise ValueError("任务、运行、冲突和操作人不能为空")
        conflict = self._conflicts.get(conflict_id)
        if conflict is None or conflict.status != "pending_review":
            raise ValueError("仅可裁决存在的待审核冲突")
        if action is ConflictReviewAction.APPROVE:
            if selected_fact_id not in conflict.fact_ids:
                raise ValueError("批准时必须选择冲突双方之一")
        elif selected_fact_id is not None:
            raise ValueError("驳回或保持未决不得选择事实")

        params = {"action": action.value, "selected_fact_id": selected_fact_id}
        if action is ConflictReviewAction.KEEP_PENDING:
            if approvals is not None or approval_id is not None:
                raise ValueError("保持未决不消费审批")
            return self._append(task_id, run_id, conflict_id, action, selected_fact_id, conflict.fact_ids, actor, None)
        if approvals is None or not approval_id:
            raise ValueError("批准或驳回必须提供有效审批")
        gate = approvals.check_gate(task_id, SUBJECT_CONFLICT_RESOLUTION, conflict_id, params, binding)
        if not gate.allowed or gate.approval_id != approval_id:
            raise ValueError("审批无效、已过期或与冲突裁决参数不匹配")

        result: ConflictReviewRecord | None = None
        def write(connection) -> None:
            nonlocal result
            result = self._append_in_transaction(connection, task_id, run_id, conflict_id, action, selected_fact_id, conflict.fact_ids, actor, approval_id)
        approvals.consume_in_transaction(approval_id, actor=actor, business_transition=write)
        assert result is not None
        return result

    def history(self, conflict_id: str) -> tuple[ConflictReviewRecord, ...]:
        with self._store.connect() as connection:
            rows = connection.execute("SELECT review_id, task_id, run_id, conflict_id, action, selected_fact_id, fact_ids_json, actor, approval_id FROM v7_research_conflict_reviews WHERE conflict_id=? ORDER BY rowid", (conflict_id,)).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def _append(self, *values) -> ConflictReviewRecord:
        with self._store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                result = self._append_in_transaction(connection, *values)
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _append_in_transaction(connection, task_id, run_id, conflict_id, action, selected_fact_id, fact_ids, actor, approval_id) -> ConflictReviewRecord:
        record = ConflictReviewRecord(uuid.uuid4().hex, task_id, run_id, conflict_id, action, selected_fact_id, tuple(fact_ids), actor, approval_id)
        connection.execute("INSERT INTO v7_research_conflict_reviews(review_id, task_id, run_id, conflict_id, action, selected_fact_id, fact_ids_json, actor, approval_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (record.review_id, record.task_id, record.run_id, record.conflict_id, record.action.value, record.selected_fact_id, json.dumps(record.fact_ids), record.actor, record.approval_id))
        return record

    @staticmethod
    def _from_row(row) -> ConflictReviewRecord:
        return ConflictReviewRecord(row[0], row[1], row[2], row[3], ConflictReviewAction(row[4]), row[5], tuple(json.loads(row[6])), row[7], row[8])
