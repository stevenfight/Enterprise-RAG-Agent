# -*- coding: utf-8 -*-
"""正式研究报告签发记录的只追加仓储。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from src.v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class ResearchReportSignoff:
    """一次正式签发；原报告本身保持不可变。"""

    signoff_id: str
    report_id: str
    task_id: str
    approval_id: str
    actor: str
    signed_at: str


class ResearchReportSignoffRepository:
    """以事务内插入配合治理审批消费，避免只消费审批而没有签发记录。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self._store = store
        store.initialize()

    def find_for_report(self, report_id: str) -> ResearchReportSignoff | None:
        """读取指定不可变报告的唯一签发记录；未签发时明确返回空。"""
        with self._store.connect() as connection:
            row = connection.execute(
                "SELECT signoff_id, report_id, task_id, approval_id, actor, signed_at "
                "FROM v7_research_report_signoffs WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        if row is None:
            return None
        return ResearchReportSignoff(*row)

    @staticmethod
    def append_in_transaction(connection, *, report_id: str, task_id: str, approval_id: str, actor: str, now: datetime) -> ResearchReportSignoff:
        record = ResearchReportSignoff(
            signoff_id=uuid.uuid4().hex,
            report_id=report_id,
            task_id=task_id,
            approval_id=approval_id,
            actor=actor,
            signed_at=now.isoformat(),
        )
        connection.execute(
            "INSERT INTO v7_research_report_signoffs(signoff_id, report_id, task_id, approval_id, actor, signed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (record.signoff_id, record.report_id, record.task_id, record.approval_id, record.actor, record.signed_at),
        )
        return record
