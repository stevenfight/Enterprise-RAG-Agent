"""A1.4 核心高风险评测候选集契约。"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.evaluation import (
    CoverageRequirements,
    ValidationError,
    build_coverage_report,
    load_jsonl_cases,
    require_release_ready,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_DATASET = PROJECT_ROOT / "evals" / "datasets" / "core-v7-candidate.jsonl"
CORE_METADATA = PROJECT_ROOT / "evals" / "datasets" / "core-v7-candidate.metadata.json"


def test_core_candidate_has_30_high_risk_cases_and_required_dimensions():
    cases = load_jsonl_cases(CORE_DATASET)
    assert len(cases) == 30
    assert len({case.case_id for case in cases}) == 30
    assert all(case.risk_level == "high" for case in cases)
    assert all(case.review_status == "verified" for case in cases)

    report = build_coverage_report(cases, CoverageRequirements())
    assert report["ready"] is True
    assert set(report["categories"]) == {"numeric", "unit", "period", "refusal", "conflict", "tool_trace"}
    assert len(report["companies"]) >= 4
    assert len(report["periods"]) >= 2


def test_core_candidate_is_not_release_ready_before_manual_review():
    cases = load_jsonl_cases(CORE_DATASET)
    cases = [replace(case, review_status="draft") for case in cases]
    with pytest.raises(ValidationError, match="发布准入"):
        require_release_ready(cases)


def test_core_candidate_metadata_records_verified_boundary():
    metadata = json.loads(CORE_METADATA.read_text(encoding="utf-8"))
    assert metadata["dataset_version"] == "v7-core-candidate-20260902"
    assert metadata["case_count"] == 30
    assert metadata["status"] == "verified"
    assert metadata["source_evidence_status"] == "verified"
    assert metadata["review_packet_status"] == "approved"
