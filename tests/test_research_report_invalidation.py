# -*- coding: utf-8 -*-
"""E1.7 事实修订后的声明局部失效契约。"""

from src.research_delivery import Claim, ClaimSupportKind, ReportReviewStatus, ResearchReport
from src.research_report_invalidation import ResearchReportInvalidationService


def _report() -> ResearchReport:
    first = Claim.create(claim_id="claim-a", text="收入增长", support_kind=ClaimSupportKind.FACT, fact_ids=("fact-revenue",))
    second = Claim.create(claim_id="claim-b", text="现金充足", support_kind=ClaimSupportKind.FACT, fact_ids=("fact-cash",))
    return ResearchReport.create(report_id="report-1", task_id="task-1", plan_id="plan-1", report_version=1, data_version="publication-1", review_status=ReportReviewStatus.APPROVED, claims=(first, second), created_at="2026-08-30T12:00:00+00:00")


def test_fact_revision_only_marks_dependent_claim_pending_review() -> None:
    result = ResearchReportInvalidationService.invalidate_for_facts(_report(), revised_fact_ids=("fact-revenue",), next_report_id="report-2", next_data_version="publication-2")
    assert result.invalidated_claim_ids == ("claim-a",)
    assert result.unaffected_claim_ids == ("claim-b",)
    assert result.report.report_id == "report-2"
    assert result.report.report_version == 2
    assert result.report.review_status is ReportReviewStatus.PENDING_REVIEW
    assert result.claim_review_statuses == {"claim-a": ReportReviewStatus.PENDING_REVIEW, "claim-b": ReportReviewStatus.APPROVED}
