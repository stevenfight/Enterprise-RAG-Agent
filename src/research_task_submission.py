# -*- coding: utf-8 -*-
"""研究任务提交与执行授权的只追加审计记录。"""

from __future__ import annotations

from dataclasses import dataclass

from src.v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class ResearchTaskSubmission:
    """任务当前提交状态的只读视图。"""

    task_id: str
    status: str
    requester: str
    reviewer: str | None


class ResearchTaskSubmissionRepository:
    """追加任务提交、批准和驳回记录，不覆盖历史审批事实。"""

    _VALID_STATUSES = frozenset({"submitted", "approved", "rejected"})

    def __init__(self, store: V7MetadataStore) -> None:
        self._store = store
        self._store.initialize()

    def submit(self, task_id: str, requester: str) -> ResearchTaskSubmission:
        """登记研究员提交的任务，任务首次提交必须从版本 1 开始。"""
        return self._append(task_id, "submitted", requester, None, require_submitted=False)

    def decide(self, task_id: str, status: str, reviewer: str) -> ResearchTaskSubmission:
        """由审批人对当前已提交任务追加批准或驳回结论。"""
        if status not in {"approved", "rejected"}:
            raise ValueError("任务审批状态只能为 approved 或 rejected")
        return self._append(task_id, status, None, reviewer, require_submitted=True)

    def current_for_task(self, task_id: str) -> ResearchTaskSubmission | None:
        with self._store.connect() as connection:
            row = connection.execute(
                "SELECT task_id, status, requester, reviewer FROM v7_research_task_submissions WHERE task_id=? ORDER BY submission_version DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def _append(
        self,
        task_id: str,
        status: str,
        requester: str | None,
        reviewer: str | None,
        *,
        require_submitted: bool,
    ) -> ResearchTaskSubmission:
        if status not in self._VALID_STATUSES:
            raise ValueError("未知任务提交状态")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("任务 ID 不能为空")
        with self._store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT submission_version, status, requester FROM v7_research_task_submissions WHERE task_id=? ORDER BY submission_version DESC LIMIT 1",
                    (task_id,),
                ).fetchone()
                if require_submitted:
                    if row is None or row[1] != "submitted":
                        raise ValueError("任务当前不处于待审批状态")
                    version = int(row[0]) + 1
                    stored_requester = row[2]
                else:
                    if row is not None:
                        raise ValueError("任务已经提交")
                    version = 1
                    stored_requester = requester
                if not isinstance(stored_requester, str) or not stored_requester.strip():
                    raise ValueError("任务提交人不能为空")
                connection.execute(
                    "INSERT INTO v7_research_task_submissions(task_id, submission_version, status, requester, reviewer) VALUES (?, ?, ?, ?, ?)",
                    (task_id, version, status, stored_requester, reviewer),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return ResearchTaskSubmission(task_id, status, stored_requester, reviewer)

    @staticmethod
    def _from_row(row: tuple[object, ...]) -> ResearchTaskSubmission:
        return ResearchTaskSubmission(str(row[0]), str(row[1]), str(row[2]), str(row[3]) if row[3] is not None else None)
