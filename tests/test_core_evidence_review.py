"""A1.5 核心评测集证据复核包契约。"""

import json
import re
from pathlib import Path

import fitz

from src.evaluation import ValidationError, load_jsonl_cases


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_DATASET = PROJECT_ROOT / "evals" / "datasets" / "core-v7-candidate.jsonl"
REVIEW_PACKET = PROJECT_ROOT / "evals" / "datasets" / "core-v7-candidate.review.jsonl"
REVIEW_METADATA = PROJECT_ROOT / "evals" / "datasets" / "core-v7-candidate.review.metadata.json"
MANUAL_SIGNOFF = PROJECT_ROOT / "evals" / "datasets" / "core-v7-candidate.manual-signoff.jsonl"
PDF_DIR = PROJECT_ROOT / "data" / "stock_data" / "pdf_reports"


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _review_records() -> list[dict]:
    try:
        lines = REVIEW_PACKET.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValidationError(f"无法读取证据复核包: {REVIEW_PACKET}") from exc
    records = [json.loads(line) for line in lines if line.strip()]
    if not records:
        raise ValidationError("证据复核包不能为空")
    return records


def test_every_core_case_has_a_review_record_and_auditable_evidence():
    cases = {case.case_id: case for case in load_jsonl_cases(CORE_DATASET)}
    records = _review_records()
    assert len(records) == len(cases) == 30
    assert {record["case_id"] for record in records} == set(cases)

    for record in records:
        case = cases[record["case_id"]]
        assert record["review_status"] == "verified"
        assert record["standard_answer"] == case.expected_answer
        assert record["numeric_tolerance"] == case.numeric_tolerance
        assert record["evidence"]
        for evidence in record["evidence"]:
            evidence_path = PROJECT_ROOT / evidence["source_file"]
            assert evidence_path.is_file()
            excerpt = evidence["excerpt"]
            assert excerpt.strip()
            if record["evidence_kind"] == "financial_fact":
                page = evidence["physical_page"]
                assert type(page) is int and page > 0
                with fitz.open(evidence_path) as document:
                    assert page <= len(document)
                    page_text = document[page - 1].get_text()
                assert _compact(excerpt) in _compact(page_text)
            else:
                assert evidence["physical_page"] is None
                assert evidence["locator"].strip()
                source_text = evidence_path.read_text(encoding="utf-8")
                assert _compact(excerpt) in _compact(source_text)

        contract_evidence = record.get("contract_evidence")
        if contract_evidence:
            contract_path = PROJECT_ROOT / contract_evidence["source_file"]
            assert contract_path.is_file()
            assert contract_evidence["locator"].strip()
            contract_text = contract_path.read_text(encoding="utf-8")
            assert _compact(contract_evidence["excerpt"]) in _compact(contract_text)


def test_financial_and_behavioral_review_boundaries_are_explicit():
    records = _review_records()
    financial = [record for record in records if record["evidence_kind"] == "financial_fact"]
    behavioral = [record for record in records if record["evidence_kind"] == "behavioral_contract"]
    assert len(financial) == 22
    assert len(behavioral) == 8
    assert {record["case_id"] for record in behavioral} == {
        "core-v7-019", "core-v7-020", "core-v7-021", "core-v7-022",
        "core-v7-023", "core-v7-024", "core-v7-025", "core-v7-026",
    }
    assert all(record["final_status"] == "approved" for record in records)


def test_review_metadata_records_verified_status():
    metadata = json.loads(REVIEW_METADATA.read_text(encoding="utf-8"))
    assert metadata["dataset_version"] == "v7-core-candidate-20260902"
    assert metadata["case_count"] == 30
    assert metadata["financial_fact_case_count"] == 22
    assert metadata["behavioral_contract_case_count"] == 8
    assert metadata["status"] == "verified"


def test_manual_signoff_ledger_is_complete_and_all_checks_pass():
    records = [
        json.loads(line)
        for line in MANUAL_SIGNOFF.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 30
    assert {record["case_id"] for record in records} == {f"core-v7-{index:03d}" for index in range(1, 31)}
    assert all(record["decision"] == "approved" for record in records)
    assert all(record["reviewer"] == "用户审核" for record in records)
    assert all(all(record["checks"].values()) for record in records)


def test_standard_answers_preserve_metric_and_period_semantics():
    cases = {case.case_id: case for case in load_jsonl_cases(CORE_DATASET)}

    net_profit = cases["core-v7-002"]
    assert net_profit.expected_facts[0]["metric_key"] == "net_profit_attributable_to_parent"
    assert "归属于上市公司股东的净利润" in net_profit.expected_answer
    assert "2024年" in net_profit.expected_answer

    future_revenue = cases["core-v7-019"]
    assert future_revenue.expected_behavior == "refuse"
    assert "2025年全年营业收入" in future_revenue.expected_answer
    assert "未提供" in future_revenue.expected_answer
    assert "只覆盖2024年及以前" not in future_revenue.expected_answer
