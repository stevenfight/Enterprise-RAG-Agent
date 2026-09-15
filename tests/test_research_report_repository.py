# -*- coding: utf-8 -*-
"""研究报告不可变持久化测试。"""

from pathlib import Path


def test_append_and_read_latest_report(tmp_path: Path):
    from src.research_delivery import Claim, ClaimSupportKind, ReportReviewStatus, ResearchReport
    from src.research_report_repository import ResearchReportRepository
    from src.v7_metadata_store import V7MetadataStore

    report = ResearchReport.create(
        report_id="report-1", task_id="task-1", plan_id="plan-1", report_version=1,
        data_version="facts-1", review_status=ReportReviewStatus.PENDING_REVIEW,
        claims=[Claim.create(claim_id="claim-1", text="收入增长", support_kind=ClaimSupportKind.FACT, fact_ids=["fact-1"])],
    )
    repository = ResearchReportRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    repository.append(report)

    restored = repository.latest_for_task("task-1")
    assert restored is not None
    assert restored.report_id == "report-1"
    assert restored.claims[0].fact_ids == ("fact-1",)
