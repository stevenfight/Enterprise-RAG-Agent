"""M1.1 区域级多模态评测集的分层与冻结留出治理测试。"""

import hashlib
import json
from pathlib import Path

import pytest


def _case(case_id: str, document_id: str, split: str, *, source_sha256: str | None = None):
    from src.evaluation import EvaluationCase

    return EvaluationCase.from_dict({
        "id": case_id,
        "category": "multimodal_region",
        "query": "该区域表达的财务指标是什么？",
        "companies": [f"公司-{document_id}"],
        "expected_answer": "已核验区域结论。",
        "expected_facts": [{"metric_key": "revenue", "period": "2024"}],
        "expected_sources": [{"source_file": f"{document_id}.pdf", "pages": [1]}],
        "expected_pages": [1],
        "numeric_tolerance": 0.01,
        "expected_behavior": "answer",
        "expected_tools": ["retrieve"],
        "risk_level": "high",
        "review_status": "verified",
        "dataset_version": "v7-multimodal-candidate",
        "source_document_id": document_id,
        "region_id": f"{document_id}:page-1:{case_id}",
        "region_type": "table",
        "modality": "table",
        "dataset_split": split,
        "source_sha256": source_sha256 or hashlib.sha256(document_id.encode("utf-8")).hexdigest(),
        "physical_page_number": 1,
    })


def test_multimodal_coverage_uses_independent_document_level_holdout_denominators():
    from src.evaluation import build_multimodal_coverage_report

    cases = [
        *[_case(f"dev-{index:02d}", f"dev-doc-{index // 3}", "development") for index in range(30)],
        *[_case(f"holdout-{index:02d}", f"holdout-doc-{index // 2}", "holdout") for index in range(10)],
    ]

    report = build_multimodal_coverage_report(cases)

    assert report["region_case_count"] == 40
    assert report["development"]["case_count"] == 30
    assert report["holdout"]["case_count"] == 10
    assert report["holdout"]["ratio"] == 0.25
    assert report["document_overlap"] == []
    assert report["ready"] is True


def test_multimodal_coverage_rejects_document_leakage_between_development_and_holdout():
    from src.evaluation import ValidationError, require_multimodal_release_ready

    cases = [_case("dev-1", "same-document", "development"), _case("holdout-1", "same-document", "holdout")]

    with pytest.raises(ValidationError, match="文档交叉污染"):
        require_multimodal_release_ready(cases)


def test_multimodal_coverage_rejects_same_pdf_page_even_when_document_ids_differ():
    from src.evaluation import ValidationError, require_multimodal_release_ready

    same_hash = "a" * 64
    cases = [
        _case("dev-1", "derived-document-a", "development", source_sha256=same_hash),
        _case("holdout-1", "derived-document-b", "holdout", source_sha256=same_hash),
    ]

    with pytest.raises(ValidationError, match="源页交叉污染"):
        require_multimodal_release_ready(cases)


def test_region_identity_fields_are_declared_in_json_schema():
    schema_path = Path("evals/schema/case.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["properties"]["source_sha256"]["pattern"] == "^[0-9a-f]{64}$"
    assert schema["properties"]["physical_page_number"]["minimum"] == 1
