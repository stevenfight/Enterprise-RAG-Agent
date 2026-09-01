# -*- coding: utf-8 -*-
"""E1.6 声明级可追溯报告导出的 RED→GREEN 契约。"""

from src.research_delivery import Claim, ClaimSupportKind, ReportReviewStatus, ResearchReport
from src.research_report_export import ResearchReportExporter


def _report() -> ResearchReport:
    claim = Claim.create(claim_id="claim-1", text="收入 < 增长", support_kind=ClaimSupportKind.FACT, fact_ids=("fact-1",), source_ids=("source-p12",))
    return ResearchReport.create(report_id="report-1", task_id="task-1", plan_id="plan-1", report_version=2, data_version="publication-7", review_status=ReportReviewStatus.PENDING_REVIEW, claims=(claim,), created_at="2026-08-30T12:00:00+00:00")


def test_markdown_export_preserves_report_claim_and_evidence_ids() -> None:
    exported = ResearchReportExporter.to_markdown(_report())
    assert "report-1" in exported and "plan-1" in exported and "publication-7" in exported
    assert "claim-1" in exported and "fact-1" in exported and "source-p12" in exported


def test_html_export_escapes_claim_text_and_preserves_traceability() -> None:
    exported = ResearchReportExporter.to_html(_report())
    assert "收入 &lt; 增长" in exported
    assert 'data-claim-id="claim-1"' in exported
    assert "fact-1" in exported and "source-p12" in exported
