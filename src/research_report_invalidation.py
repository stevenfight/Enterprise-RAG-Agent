# -*- coding: utf-8 -*-
"""E1.7 事实修订后的研究报告局部失效。"""

from __future__ import annotations

from dataclasses import dataclass

from src.research_delivery import ReportReviewStatus, ResearchReport


@dataclass(frozen=True)
class ResearchReportInvalidationResult:
    """新报告版本及逐声明审核状态，旧报告保持不可变。"""

    report: ResearchReport
    invalidated_claim_ids: tuple[str, ...]
    unaffected_claim_ids: tuple[str, ...]
    claim_review_statuses: dict[str, ReportReviewStatus]


class ResearchReportInvalidationService:
    """仅按事实 ID 反向定位依赖声明，禁止扩大失效范围。"""

    @classmethod
    def invalidate_for_facts(cls, report: ResearchReport, *, revised_fact_ids: tuple[str, ...] | list[str], next_report_id: str, next_data_version: str) -> ResearchReportInvalidationResult:
        if not isinstance(report, ResearchReport):
            raise ValueError("report 必须是 ResearchReport")
        revised = cls._ids(revised_fact_ids, "revised_fact_ids")
        if not isinstance(next_report_id, str) or not next_report_id.strip() or next_report_id == report.report_id:
            raise ValueError("next_report_id 必须是不同的非空报告 ID")
        if not isinstance(next_data_version, str) or not next_data_version.strip():
            raise ValueError("next_data_version 不能为空")
        revised_set = set(revised)
        invalidated = tuple(claim.claim_id for claim in report.claims if revised_set.intersection(claim.fact_ids))
        unaffected = tuple(claim.claim_id for claim in report.claims if claim.claim_id not in invalidated)
        statuses = {claim_id: ReportReviewStatus.PENDING_REVIEW for claim_id in invalidated}
        statuses.update({claim_id: report.review_status for claim_id in unaffected})
        next_report = ResearchReport.create(report_id=next_report_id, task_id=report.task_id, plan_id=report.plan_id, report_version=report.report_version + 1, data_version=next_data_version, review_status=ReportReviewStatus.PENDING_REVIEW if invalidated else report.review_status, claims=report.claims)
        return ResearchReportInvalidationResult(next_report, invalidated, unaffected, statuses)

    @staticmethod
    def _ids(values: tuple[str, ...] | list[str], field_name: str) -> tuple[str, ...]:
        if isinstance(values, str) or not isinstance(values, (tuple, list)) or not values:
            raise ValueError(f"{field_name} 必须包含至少一个事实 ID")
        if any(not isinstance(value, str) or not value.strip() for value in values) or len(set(values)) != len(values):
            raise ValueError(f"{field_name} 必须是无重复的非空事实 ID")
        return tuple(values)
