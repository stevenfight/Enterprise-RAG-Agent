"""v7 评测平面最小闭环测试。

这些测试只使用固定输入，不调用外部模型或网络服务。
"""

from pathlib import Path
import sys

import pytest

from src.evaluation import (
    EvaluationCase,
    EvaluationRunner,
    ValidationError,
    CoverageRequirements,
    build_coverage_report,
    require_release_ready,
    compare_numeric,
    evaluate_case,
    load_jsonl_cases,
)
from src.evaluation.cli import main as evaluation_cli_main


def make_case(**overrides):
    data = {
        "id": "case-001",
        "category": "numeric",
        "query": "公司 2024 年营业收入是多少？",
        "companies": ["示例公司"],
        "expected_answer": "2024 年营业收入为 100 亿元。",
        "expected_facts": [
            {
                "metric_key": "revenue",
                "value": 100,
                "unit": "亿元",
                "currency": "CNY",
                "period": "2024",
            }
        ],
        "expected_sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
        "expected_pages": [12],
        "numeric_tolerance": 0.01,
        "expected_behavior": "answer",
        "expected_tools": ["retrieve"],
        "risk_level": "high",
        "review_status": "verified",
        "dataset_version": "v1",
    }
    data.update(overrides)
    return data


def test_valid_case_passes_schema():
    case = EvaluationCase.from_dict(make_case())
    assert case.case_id == "case-001"
    assert case.expected_sources[0].pages == [12]


def test_missing_source_or_page_is_rejected():
    with pytest.raises(ValidationError):
        EvaluationCase.from_dict(make_case(expected_sources=[]))

    with pytest.raises(ValidationError):
        EvaluationCase.from_dict(make_case(expected_pages=[]))


def test_duplicate_case_ids_are_rejected(tmp_path: Path):
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        "\n".join([
            __import__("json").dumps(make_case(), ensure_ascii=False),
            __import__("json").dumps(make_case(), ensure_ascii=False),
        ]),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="重复样本 ID"):
        load_jsonl_cases(dataset)


def test_numeric_value_within_tolerance_passes():
    result = compare_numeric(100, 100.5, tolerance=0.01)
    assert result.passed is True


def test_numeric_magnitude_error_fails_even_when_other_metrics_pass():
    result = compare_numeric(100, 10, tolerance=0.01)
    assert result.passed is False
    assert result.reason == "value_mismatch"


def test_unit_currency_and_period_are_scored_separately():
    actual = {
        "metric_key": "revenue",
        "value": 100,
        "unit": "万元",
        "currency": "USD",
        "period": "2023",
    }
    result = evaluate_case(
        EvaluationCase.from_dict(make_case()),
        {"answer": "100", "facts": [actual], "sources": [], "tools": []},
    )
    assert result.metrics["value_accuracy"] == 1.0
    assert result.metrics["unit_accuracy"] == 0.0
    assert result.metrics["currency_accuracy"] == 0.0
    assert result.metrics["period_accuracy"] == 0.0


def test_expected_refusal_is_evaluated_as_refusal():
    case = EvaluationCase.from_dict(
        make_case(expected_behavior="refuse", expected_facts=[], expected_sources=[], expected_pages=[])
    )
    result = evaluate_case(case, {"answer": "证据不足，无法确认。", "facts": [], "sources": [], "tools": []})
    assert result.metrics["refusal_accuracy"] == 1.0


def test_expected_tools_and_order_are_checked():
    case = EvaluationCase.from_dict(make_case(expected_tools=["retrieve", "verify"]))
    result = evaluate_case(
        case,
        {"answer": "100 亿元", "facts": make_case()["expected_facts"], "sources": make_case()["expected_sources"], "tools": ["retrieve"]},
    )
    assert result.metrics["tool_trace_accuracy"] == 0.0


def test_offline_runner_does_not_call_external_service():
    case = EvaluationCase.from_dict(make_case())
    runner = EvaluationRunner(mode="offline-core", provider=lambda _: pytest.fail("不应调用外部服务"))
    report = runner.run([case], {"case-001": {"answer": "100 亿元", "facts": make_case()["expected_facts"], "sources": make_case()["expected_sources"], "tools": ["retrieve"]}})
    assert report.mode == "offline-core"
    assert report.metadata["external_service_called"] is False


def test_baseline_diff_reports_new_failures_and_repairs():
    baseline = {"case-001": {"passed": False}, "case-002": {"passed": True}}
    candidate = {"case-001": {"passed": True}, "case-002": {"passed": False}}
    report = EvaluationRunner.diff(baseline, candidate)
    assert report["repaired"] == ["case-001"]
    assert report["new_failures"] == ["case-002"]


def test_report_metadata_contains_required_versions():
    case = EvaluationCase.from_dict(make_case())
    runner = EvaluationRunner(
        mode="offline-core",
        code_sha="abc",
        model_id="fixture",
        prompt_version="p1",
        index_version="idx1",
        dataset_version="v1",
    )
    report = runner.run([case], {"case-001": {"answer": "100 亿元", "facts": make_case()["expected_facts"], "sources": make_case()["expected_sources"], "tools": ["retrieve"]}})
    assert report.metadata == {
        "mode": "offline-core",
        "code_sha": "abc",
        "model_id": "fixture",
        "prompt_version": "p1",
        "index_version": "idx1",
        "dataset_version": "v1",
        "external_service_called": False,
        "coverage": {
            "case_count": 1,
            "high_risk_case_count": 1,
            "companies": ["示例公司"],
            "periods": ["2024"],
            "categories": ["numeric"],
            "missing_categories": ["conflict", "period", "refusal", "tool_trace", "unit"],
            "deficits": {
                "minimum_cases": 29,
                "minimum_high_risk_cases": 9,
                "minimum_companies": 3,
                "minimum_periods": 1,
                "missing_categories": ["conflict", "period", "refusal", "tool_trace", "unit"],
            },
            "ready": False,
        },
    }


def test_answer_level_baseline_does_not_claim_statement_level_support():
    case = EvaluationCase.from_dict(make_case())
    report = evaluate_case(
        case,
        {"answer": "100 亿元", "facts": [], "sources": [], "tools": ["retrieve"]},
    )
    assert report.metrics["answer_level_source_hit"] == 0.0
    assert "claim_level_evidence_support" not in report.metrics


def test_report_writes_json_and_markdown_without_hiding_failures(tmp_path: Path):
    case = EvaluationCase.from_dict(make_case())
    report = EvaluationRunner().run(
        [case],
        {"case-001": {"answer": "10 亿元", "facts": [], "sources": [], "tools": []}},
    )
    json_path, markdown_path = EvaluationRunner.write_reports(report, tmp_path)
    assert json_path.exists() and markdown_path.exists()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "case-001" in markdown and "失败" in markdown


def test_high_risk_failure_blocks_quality_gate():
    case = EvaluationCase.from_dict(make_case())
    report = EvaluationRunner().run(
        [case],
        {"case-001": {"answer": "10 亿元", "facts": [], "sources": [], "tools": []}},
    )
    assert EvaluationRunner.passes_quality_gate(report) is False


def test_dataset_seed_is_loadable():
    cases = load_jsonl_cases(Path("evals/datasets/core.jsonl"))
    assert [case.case_id for case in cases] == ["seed-revenue-001"]


def test_cli_returns_nonzero_when_quality_gate_fails(tmp_path: Path, monkeypatch):
    fixtures = tmp_path / "failed-fixtures.json"
    fixtures.write_text('{"seed-revenue-001":{"answer":"无法确认","facts":[],"sources":[],"tools":[]}}', encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset", "evals/datasets/core.jsonl",
            "--fixtures", str(fixtures),
            "--output-dir", str(tmp_path / "report"),
        ],
    )
    assert evaluation_cli_main() == 1


def test_coverage_report_exposes_missing_dimensions_without_lowering_requirements():
    cases = [EvaluationCase.from_dict(make_case())]
    report = build_coverage_report(cases, CoverageRequirements(minimum_cases=2, minimum_high_risk_cases=2, minimum_companies=2, minimum_periods=2))
    assert report["ready"] is False
    assert report["deficits"]["minimum_cases"] == 1
    assert "refusal" in report["missing_categories"]


def test_release_ready_rejects_unverified_dataset():
    case = EvaluationCase.from_dict(make_case(review_status="draft"))
    with pytest.raises(ValidationError, match="发布准入"):
        require_release_ready([case])


def test_release_mode_rejects_incomplete_dataset_before_running_fixtures():
    case = EvaluationCase.from_dict(make_case(review_status="verified"))
    with pytest.raises(ValidationError, match="发布准入"):
        EvaluationRunner(mode="release-full").run([case], {"case-001": {}})


def test_runner_derives_dataset_version_when_not_explicitly_configured():
    case = EvaluationCase.from_dict(make_case(dataset_version="v1-seed"))
    report = EvaluationRunner().run(
        [case],
        {"case-001": {"answer": "100 亿元", "facts": make_case()["expected_facts"], "sources": make_case()["expected_sources"], "tools": ["retrieve"]}},
    )
    assert report.metadata["dataset_version"] == "v1-seed"
