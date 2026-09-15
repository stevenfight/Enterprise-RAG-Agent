# -*- coding: utf-8 -*-
"""研究报告不可变版本的 SQLite 仓储。"""

from __future__ import annotations

import json
import sqlite3

from src.research_delivery import Claim, ClaimSupportKind, ReportReviewStatus, ResearchReport
from src.v7_metadata_store import V7MetadataStore


class ResearchReportRepository:
    def __init__(self, metadata_store: V7MetadataStore) -> None:
        self._store = metadata_store
        self._store.initialize()

    def append(self, report: ResearchReport) -> None:
        with self._store.connect() as connection:
            self.append_in_transaction(connection, report)
            connection.commit()

    def append_in_transaction(self, connection: sqlite3.Connection, report: ResearchReport) -> None:
        """在调用方事务中追加不可变报告，不自行提交。"""
        claims = [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "support_kind": claim.support_kind.value,
                "fact_ids": claim.fact_ids,
                "calculation_ids": claim.calculation_ids,
                "source_ids": claim.source_ids,
                "analysis_label": claim.analysis_label,
            }
            for claim in report.claims
        ]
        connection.execute(
            "INSERT INTO v7_research_reports(report_id, task_id, plan_id, report_version, data_version, review_status, claims_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                report.report_id,
                report.task_id,
                report.plan_id,
                report.report_version,
                report.data_version,
                report.review_status.value,
                json.dumps(claims, ensure_ascii=False),
                report.created_at,
            ),
        )

    def latest_for_task(self, task_id: str) -> ResearchReport | None:
        with self._store.connect() as connection:
            row = connection.execute("SELECT report_id, task_id, plan_id, report_version, data_version, review_status, claims_json, created_at FROM v7_research_reports WHERE task_id=? ORDER BY report_version DESC LIMIT 1", (task_id,)).fetchone()
        if row is None:
            return None
        claims = [Claim.create(claim_id=c["claim_id"], text=c["text"], support_kind=ClaimSupportKind(c["support_kind"]), fact_ids=c["fact_ids"], calculation_ids=c["calculation_ids"], source_ids=c["source_ids"], analysis_label=c["analysis_label"]) for c in json.loads(row[6])]
        return ResearchReport.create(report_id=row[0], task_id=row[1], plan_id=row[2], report_version=row[3], data_version=row[4], review_status=ReportReviewStatus(row[5]), claims=claims, created_at=row[7])
