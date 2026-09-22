"""金融 Agent 确定性评测平面。"""

from .models import EvaluationCase, EvaluationReport, CaseEvaluation, ValidationError
from .schema import load_jsonl_cases
from .evaluators import (
    compare_numeric,
    evaluate_case,
    evaluate_claim_evidence_support,
    match_expected_keywords,
)
from .runner import EvaluationRunner
from .coverage import (
    CoverageRequirements,
    MultimodalCoverageRequirements,
    build_coverage_report,
    build_baseline_readiness_report,
    build_multimodal_coverage_report,
    require_release_ready,
    require_multimodal_release_ready,
)
from .thresholds import load_thresholds
from .source_audit import audit_source_files
from .source_binding import audit_source_binding
from .source_integrity import audit_source_integrity
from .multimodal_readiness import build_m4_readiness_report, m4_readiness_to_markdown
from .legacy_migration import migrate_legacy_datasets
from .manual_signoff import (
    REQUIRED_REVIEW_CHECKS,
    SignoffLedgerError,
    append_signoff_record,
    load_signoff_ledger,
)

__all__ = [
    "CaseEvaluation",
    "EvaluationCase",
    "EvaluationReport",
    "EvaluationRunner",
    "ValidationError",
    "compare_numeric",
    "evaluate_case",
    "evaluate_claim_evidence_support",
    "match_expected_keywords",
    "load_jsonl_cases",
    "CoverageRequirements",
    "MultimodalCoverageRequirements",
    "build_coverage_report",
    "build_baseline_readiness_report",
    "build_multimodal_coverage_report",
    "require_release_ready",
    "require_multimodal_release_ready",
    "load_thresholds",
    "audit_source_files",
    "audit_source_binding",
    "audit_source_integrity",
    "build_m4_readiness_report",
    "m4_readiness_to_markdown",
    "migrate_legacy_datasets",
    "REQUIRED_REVIEW_CHECKS",
    "SignoffLedgerError",
    "append_signoff_record",
    "load_signoff_ledger",
]
