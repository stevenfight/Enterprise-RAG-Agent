"""评测集覆盖率和发布准入校验。"""

from dataclasses import dataclass
from typing import Any

from .models import EvaluationCase, ValidationError


@dataclass(frozen=True)
class CoverageRequirements:
    """核心集的最低覆盖要求，避免样本数量掩盖维度缺口。"""

    minimum_cases: int = 30
    minimum_high_risk_cases: int = 10
    minimum_companies: int = 4
    minimum_periods: int = 2
    required_categories: tuple[str, ...] = (
        "numeric", "unit", "period", "refusal", "conflict", "tool_trace",
    )


def build_coverage_report(
    cases: list[EvaluationCase],
    requirements: CoverageRequirements | None = None,
) -> dict[str, Any]:
    """生成可审阅的覆盖报告；缺口只报告，不自动放宽要求。"""
    requirements = requirements or CoverageRequirements()
    categories = sorted({case.category for case in cases})
    companies = sorted({company for case in cases for company in case.companies})
    periods = sorted({fact.get("period") for case in cases for fact in case.expected_facts if fact.get("period")})
    high_risk_cases = sum(case.risk_level == "high" for case in cases)
    missing_categories = sorted(set(requirements.required_categories) - set(categories))
    deficits = {}
    if len(cases) < requirements.minimum_cases:
        deficits["minimum_cases"] = requirements.minimum_cases - len(cases)
    if high_risk_cases < requirements.minimum_high_risk_cases:
        deficits["minimum_high_risk_cases"] = requirements.minimum_high_risk_cases - high_risk_cases
    if len(companies) < requirements.minimum_companies:
        deficits["minimum_companies"] = requirements.minimum_companies - len(companies)
    if len(periods) < requirements.minimum_periods:
        deficits["minimum_periods"] = requirements.minimum_periods - len(periods)
    if missing_categories:
        deficits["missing_categories"] = missing_categories
    return {
        "case_count": len(cases),
        "high_risk_case_count": high_risk_cases,
        "companies": companies,
        "periods": periods,
        "categories": categories,
        "missing_categories": missing_categories,
        "deficits": deficits,
        "ready": not deficits,
    }


def require_release_ready(cases: list[EvaluationCase]) -> dict[str, Any]:
    """发布模式拒绝未完成覆盖或未完成来源复核的数据集。"""
    report = build_coverage_report(cases)
    unverified = [case.case_id for case in cases if case.review_status != "verified"]
    if unverified:
        report["unverified_case_ids"] = unverified
        report["ready"] = False
        report["deficits"]["unverified_cases"] = unverified
    if not report["ready"]:
        raise ValidationError(f"评测集未达到发布准入: {report['deficits']}")
    return report
