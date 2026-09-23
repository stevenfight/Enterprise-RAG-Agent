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


@dataclass(frozen=True)
class MultimodalCoverageRequirements:
    """区域级多模态评测集的独立发布门禁。"""

    minimum_region_cases: int = 40
    minimum_holdout_ratio: float = 0.25


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


def build_baseline_readiness_report(cases: list[EvaluationCase]) -> dict[str, Any]:
    """生成真实基线前的数据集就绪报告，不触发评测或外部调用。"""
    coverage = build_coverage_report(cases)
    unverified_case_ids = [
        case.case_id
        for case in cases
        if case.review_status != "verified"
    ]
    blockers = []
    if not coverage["ready"]:
        blockers.append("评测集覆盖未达到发布准入")
    if unverified_case_ids:
        blockers.append(f"存在未人工核验的评测样本: {len(unverified_case_ids)}")
    return {
        "ready": not blockers,
        "coverage": coverage,
        "review": {
            "verified_case_count": len(cases) - len(unverified_case_ids),
            "unverified_case_count": len(unverified_case_ids),
            "unverified_case_ids": unverified_case_ids,
        },
        "blockers": blockers,
    }


def build_multimodal_coverage_report(
    cases: list[EvaluationCase],
    requirements: MultimodalCoverageRequirements | None = None,
) -> dict[str, Any]:
    """统计区域级样本的独立分母，防止同文档或同公司泄漏到留出集。"""
    requirements = requirements or MultimodalCoverageRequirements()
    region_cases = [case for case in cases if case.dataset_split is not None]
    development = [case for case in region_cases if case.dataset_split == "development"]
    holdout = [case for case in region_cases if case.dataset_split == "holdout"]
    development_documents = {case.source_document_id for case in development}
    holdout_documents = {case.source_document_id for case in holdout}
    development_companies = {company for case in development for company in case.companies}
    holdout_companies = {company for case in holdout for company in case.companies}
    development_source_pages = {
        (case.source_sha256, case.physical_page_number)
        for case in development
        if case.source_sha256 is not None and case.physical_page_number is not None
    }
    holdout_source_pages = {
        (case.source_sha256, case.physical_page_number)
        for case in holdout
        if case.source_sha256 is not None and case.physical_page_number is not None
    }
    document_overlap = sorted(development_documents & holdout_documents)
    company_overlap = sorted(development_companies & holdout_companies)
    source_page_overlap = sorted(development_source_pages & holdout_source_pages)
    total = len(region_cases)
    holdout_ratio = len(holdout) / total if total else 0.0
    deficits: dict[str, Any] = {}
    if total < requirements.minimum_region_cases:
        deficits["minimum_region_cases"] = requirements.minimum_region_cases - total
    if holdout_ratio < requirements.minimum_holdout_ratio:
        deficits["minimum_holdout_ratio"] = requirements.minimum_holdout_ratio - holdout_ratio
    if document_overlap:
        deficits["document_overlap"] = document_overlap
    if company_overlap:
        deficits["company_overlap"] = company_overlap
    if source_page_overlap:
        deficits["source_page_overlap"] = source_page_overlap
    return {
        "region_case_count": total,
        "development": {"case_count": len(development), "document_ids": sorted(development_documents), "companies": sorted(development_companies)},
        "holdout": {"case_count": len(holdout), "ratio": holdout_ratio, "document_ids": sorted(holdout_documents), "companies": sorted(holdout_companies)},
        "document_overlap": document_overlap,
        "company_overlap": company_overlap,
        "source_page_overlap": source_page_overlap,
        "deficits": deficits,
        "ready": not deficits,
    }


def require_multimodal_release_ready(cases: list[EvaluationCase]) -> dict[str, Any]:
    """拒绝不满足区域独立分母、冻结留出或人工复核条件的数据集。"""
    report = build_multimodal_coverage_report(cases)
    if report["document_overlap"]:
        raise ValidationError(f"区域级评测集存在文档交叉污染: {report['document_overlap']}")
    if report["company_overlap"]:
        raise ValidationError(f"区域级评测集存在公司交叉污染: {report['company_overlap']}")
    if report["source_page_overlap"]:
        raise ValidationError(f"区域级评测集存在源页交叉污染: {report['source_page_overlap']}")
    unverified = [case.case_id for case in cases if case.dataset_split is not None and case.review_status != "verified"]
    if unverified:
        report["deficits"]["unverified_case_ids"] = unverified
    if report["deficits"]:
        raise ValidationError(f"区域级评测集未达到发布准入: {report['deficits']}")
    return report
