"""v7 评测平面最小闭环测试。

这些测试只使用固定输入，不调用外部模型或网络服务。
"""

from pathlib import Path
import hashlib
import json
import platform
import subprocess
import sys

import pytest

from src.evaluation import (
    CaseEvaluation,
    EvaluationCase,
    EvaluationReport,
    EvaluationRunner,
    ValidationError,
    CoverageRequirements,
    build_coverage_report,
    require_release_ready,
    compare_numeric,
    evaluate_case,
    evaluate_claim_evidence_support,
    load_jsonl_cases,
    load_thresholds,
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


def test_refusal_contract_accepts_non_deterministic_answer_language():
    case = EvaluationCase.from_dict(
        make_case(
            expected_behavior="refuse",
            expected_facts=[],
            expected_sources=[],
            expected_pages=[],
            expected_keywords=[],
            expected_tools=[],
        )
    )
    result = evaluate_case(
        case,
        {
            "answer": "年度与季度期间不同，不能直接视为冲突，应先对齐期间和来源口径。",
            "facts": [],
            "sources": [],
            "tools": [],
        },
    )
    assert result.passed is True
    assert result.metrics["refusal_accuracy"] == 1.0


def test_claim_evidence_matches_duplicate_metric_by_period():
    case = EvaluationCase.from_dict(
        make_case(
            expected_facts=[
                {
                    "metric_key": "revenue",
                    "value": 100,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                },
                {
                    "metric_key": "revenue",
                    "value": 80,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2023",
                },
            ]
        )
    )
    support = evaluate_claim_evidence_support(
        case,
        {
            "facts": [
                {
                    "metric_key": "revenue",
                    "value": 100,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                    "normalized_value": 100,
                },
                {
                    "metric_key": "revenue",
                    "value": 80,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2023",
                    "normalized_value": 80,
                },
            ],
            "sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
        },
    )
    assert support == 1.0


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


def test_baseline_diff_reports_case_set_score_and_performance_changes():
    baseline = {
        "case-001": {
            "passed": True,
            "metrics": {"answer_accuracy": 0.8},
            "performance": {"latency_ms": 120, "token_count": 100},
        },
        "case-removed": {"passed": True},
    }
    candidate = {
        "case-001": {
            "passed": True,
            "metrics": {"answer_accuracy": 1.0},
            "performance": {"latency_ms": 150, "token_count": 100},
        },
        "case-added": {"passed": False},
    }

    report = EvaluationRunner.diff(baseline, candidate)

    assert report["added_cases"] == ["case-added"]
    assert report["removed_cases"] == ["case-removed"]
    assert report["unchanged_cases"] == []
    assert report["score_changes"] == [
        {
            "case_id": "case-001",
            "metric": "answer_accuracy",
            "baseline": 0.8,
            "candidate": 1.0,
            "delta": 0.2,
        }
    ]
    assert report["performance_changes"] == [
        {
            "case_id": "case-001",
            "metric": "latency_ms",
            "baseline": 120,
            "candidate": 150,
            "delta": 30,
        }
    ]


def test_report_comparison_preserves_release_metadata_and_pass_rate():
    baseline = EvaluationReport(
        mode="local-full",
        metadata={
            "code_sha": "old-code",
            "model_id": "old-model",
            "prompt_version": "p1",
            "index_version": "idx1",
            "dataset_version": "v5.19",
        },
        results=[CaseEvaluation("case-001", True, {"answer_accuracy": 0.8})],
    )
    candidate = EvaluationReport(
        mode="local-full",
        metadata={
            "code_sha": "new-code",
            "model_id": "new-model",
            "prompt_version": "p2",
            "index_version": "idx2",
            "dataset_version": "v7-core",
        },
        results=[CaseEvaluation("case-001", True, {"answer_accuracy": 1.0})],
    )

    report = EvaluationRunner.compare_reports(baseline, candidate)

    assert report["metadata"] == {
        "baseline": {
            "code_sha": "old-code",
            "model_id": "old-model",
            "prompt_version": "p1",
            "index_version": "idx1",
            "dataset_version": "v5.19",
        },
        "candidate": {
            "code_sha": "new-code",
            "model_id": "new-model",
            "prompt_version": "p2",
            "index_version": "idx2",
            "dataset_version": "v7-core",
        },
    }
    assert report["pass_rate"] == {"baseline": 1.0, "candidate": 1.0, "delta": 0.0}
    assert report["score_changes"][0]["metric"] == "answer_accuracy"


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


def test_thresholds_drive_overall_pass_rate_instead_of_callsite_default():
    report = EvaluationReport(
        mode="offline-core",
        metadata={},
        results=[
            *[CaseEvaluation(f"case-{index}", True) for index in range(9)],
            CaseEvaluation("case-failed", False),
        ],
    )

    assert EvaluationRunner.passes_quality_gate(
        report,
        minimum_pass_rate=0.5,
        thresholds={
            "minimum_pass_rate": 0.95,
            "high_risk_failure_limit": 0,
        },
    ) is False


def test_thresholds_control_high_risk_failure_limit_without_disabling_hard_count():
    report = EvaluationReport(
        mode="offline-core",
        metadata={},
        results=[
            CaseEvaluation("case-high-risk", False, risk_level="high"),
            CaseEvaluation("case-ok", True),
        ],
    )

    assert EvaluationRunner.passes_quality_gate(
        report,
        thresholds={
            "minimum_pass_rate": 0.5,
            "high_risk_failure_limit": 1,
        },
    ) is True
    assert EvaluationRunner.passes_quality_gate(
        report,
        thresholds={
            "minimum_pass_rate": 0.5,
            "high_risk_failure_limit": 0,
        },
    ) is False


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


def test_cli_uses_threshold_file_for_exit_code(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        "\n".join(
            json.dumps(
                make_case(
                    id=case_id,
                    category="refusal",
                    expected_answer="证据不足时拒答。",
                    expected_facts=[],
                    expected_sources=[],
                    expected_pages=[],
                    expected_behavior="refuse",
                    expected_tools=[],
                    risk_level="medium",
                ),
                ensure_ascii=False,
            )
            for case_id in ("refuse-pass", "refuse-fail")
        ),
        encoding="utf-8",
    )
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text(
        json.dumps(
            {
                "refuse-pass": {"answer": "无法确认", "facts": [], "sources": [], "tools": []},
                "refuse-fail": {"answer": "已确认", "facts": [], "sources": [], "tools": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    thresholds = tmp_path / "thresholds.yaml"
    thresholds.write_text(
        "minimum_pass_rate: 0.5\n"
        "high_risk_failure_limit: 0\n"
        "claim_level_evidence_support: disabled\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset", str(dataset),
            "--fixtures", str(fixtures),
            "--output-dir", str(tmp_path / "report"),
            "--thresholds", str(thresholds),
        ],
    )

    assert evaluation_cli_main() == 0


def test_cli_fails_when_threshold_file_is_missing(tmp_path: Path, monkeypatch):
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset", "evals/datasets/core.jsonl",
            "--fixtures", str(fixtures),
            "--output-dir", str(tmp_path / "report"),
            "--thresholds", str(tmp_path / "missing-thresholds.yaml"),
        ],
    )

    with pytest.raises(FileNotFoundError):
        evaluation_cli_main()


def test_cli_runs_local_full_only_with_local_context(tmp_path: Path, monkeypatch):
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text(
        json.dumps(
            {
                "seed-revenue-001": {
                    "answer": "100 亿元",
                    "facts": [
                        {
                            "metric_key": "revenue",
                            "value": 100,
                            "normalized_value": 100,
                            "unit": "亿元",
                            "currency": "CNY",
                            "period": "2024",
                        }
                    ],
                    "sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
                    "tools": ["retrieve"],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "report"
    thresholds = tmp_path / "thresholds.yaml"
    thresholds.write_text(
        "minimum_pass_rate: 0.98\n"
        "high_risk_failure_limit: 0\n"
        "claim_level_evidence_support: disabled\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset", "evals/datasets/core.jsonl",
            "--fixtures", str(fixtures),
            "--output-dir", str(output_dir),
            "--mode", "local-full",
            "--execution-context", "local",
            "--code-sha", "v5.19-local-commit",
            "--model-id", "local-financial-model",
            "--prompt-version", "v5.19-prompt",
            "--index-version", "v5.19-index",
            "--dataset-version", "v5.19-full-candidate",
            "--thresholds", str(thresholds),
            "--minimum-pass-rate", "0.97",
        ],
    )

    assert evaluation_cli_main() == 0
    report = json.loads((output_dir / "evaluation-report.json").read_text(encoding="utf-8"))
    assert report["mode"] == "local-full"
    assert report["metadata"]["mode"] == "local-full"
    assert report["metadata"]["execution_context"] == "local"
    assert report["metadata"]["code_sha"] == "v5.19-local-commit"
    assert report["metadata"]["model_id"] == "local-financial-model"
    assert report["metadata"]["prompt_version"] == "v5.19-prompt"
    assert report["metadata"]["index_version"] == "v5.19-index"
    assert report["metadata"]["dataset_version"] == "v5.19-full-candidate"
    assert report["metadata"]["input_sha256"] == {
        "dataset": hashlib.sha256(Path("evals/datasets/core.jsonl").read_bytes()).hexdigest(),
        "fixtures": hashlib.sha256(fixtures.read_bytes()).hexdigest(),
        "thresholds": hashlib.sha256(thresholds.read_bytes()).hexdigest(),
    }
    assert report["metadata"]["quality_gate_thresholds"] == {
        "minimum_pass_rate": 0.97,
        "high_risk_failure_limit": 0,
        "claim_level_evidence_support": "disabled",
    }
    assert report["metadata"]["python_runtime"] == {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
    }


def test_cli_rejects_local_full_baseline_candidate_without_explicit_provenance(tmp_path: Path, monkeypatch):
    """local-full 不得把缺少版本来源的报告误作可复现基线。"""
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset", "evals/datasets/core.jsonl",
            "--fixtures", str(fixtures),
            "--output-dir", str(tmp_path / "report"),
            "--mode", "local-full",
            "--execution-context", "local",
        ],
    )

    with pytest.raises(ValueError, match="local-full 基线候选运行缺少可追溯元数据"):
        evaluation_cli_main()


def test_cli_writes_baseline_readiness_without_fixtures_or_provider(tmp_path: Path, monkeypatch):
    """基线前置检查只能读取数据集，并如实输出当前核验状态。"""
    output_path = tmp_path / "baseline-readiness.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset", "evals/datasets/full-v7-candidate.jsonl",
            "--baseline-readiness-output", str(output_path),
        ],
    )

    assert evaluation_cli_main() == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["ready"] is True
    assert report["review"] == {
        "verified_case_count": 100,
        "unverified_case_count": 0,
        "unverified_case_ids": [],
    }
    assert report["blockers"] == []


@pytest.mark.parametrize("mode", ["local-full", "release-full"])
def test_cli_rejects_full_mode_in_pr_context(tmp_path: Path, monkeypatch, mode: str):
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset", "evals/datasets/core.jsonl",
            "--fixtures", str(fixtures),
            "--output-dir", str(tmp_path / "report"),
            "--mode", mode,
            "--execution-context", "pr",
        ],
    )

    expected_context = "local" if mode == "local-full" else "release"
    with pytest.raises(ValueError, match=f"{mode} 必须使用 {expected_context} 执行上下文"):
        evaluation_cli_main()


def test_cli_rejects_release_mode_without_release_context(tmp_path: Path, monkeypatch):
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset", "evals/datasets/core.jsonl",
            "--fixtures", str(fixtures),
            "--output-dir", str(tmp_path / "report"),
            "--mode", "release-full",
            "--execution-context", "local",
        ],
    )

    with pytest.raises(ValueError, match="release-full 必须使用 release 执行上下文"):
        evaluation_cli_main()


def test_v7_evaluation_docs_describe_context_boundaries():
    usage = Path("tests/README.md").read_text(encoding="utf-8")

    assert "offline-core" in usage
    assert "local-full" in usage
    assert "release-full" in usage
    assert "execution-context" in usage
    assert "--code-sha" in usage
    assert "--model-id" in usage
    assert "--prompt-version" in usage
    assert "--index-version" in usage
    assert "--dataset-version" in usage
    assert "input_sha256" in usage
    assert "quality_gate_thresholds" in usage
    assert "python_runtime" in usage
    assert "baseline-readiness-output" in usage
    assert "真实 provider" in usage
    assert "--source-binding-manifest" in usage


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


def test_offline_cli_process_isolated_from_monitoring_and_passes_default_gate(tmp_path: Path):
    """真实模块入口不得触发监控初始化，默认离线夹具应通过现行门禁。"""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.evaluation.cli",
            "--dataset",
            "evals/datasets/core.jsonl",
            "--fixtures",
            "evals/fixtures/offline-core.json",
            "--output-dir",
            str(tmp_path / "report"),
            "--mode",
            "offline-core",
            "--execution-context",
            "pr",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        check=False,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined_output
    assert "monitoring" not in combined_output.lower()
    assert "langsmith" not in combined_output.lower()
    report = json.loads((tmp_path / "report" / "evaluation-report.json").read_text(encoding="utf-8"))
    assert report["metadata"]["external_service_called"] is False
    assert report["results"][0]["metrics"]["claim_level_evidence_support"] == 1.0


def test_v7_core_offline_gate_replays_all_approved_cases_without_provider():
    """A-GATE-1 必须完整回放已签核核心集，并且重复运行结果稳定。"""
    dataset_path = Path("evals/datasets/core-v7-candidate.jsonl")
    fixture_path = Path("evals/fixtures/offline-core-v7.json")
    cases = load_jsonl_cases(dataset_path)
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    require_release_ready(cases)

    assert len(cases) == 30
    assert {case.case_id for case in cases} == set(fixtures)
    runner = EvaluationRunner(
        mode="offline-core",
        provider=lambda _: pytest.fail("A-GATE-1 不得调用外部 provider"),
    )
    first = runner.run(cases, fixtures)
    second = runner.run(cases, fixtures)

    assert first.to_dict() == second.to_dict()
    assert first.metadata["external_service_called"] is False
    assert first.metadata["coverage"]["case_count"] == 30
    assert all(result.passed for result in first.results)
    assert EvaluationRunner.passes_quality_gate(
        first,
        thresholds=load_thresholds(Path("evals/config/thresholds.yaml")),
    ) is True


def test_v7_core_offline_cli_process_writes_complete_report(tmp_path: Path):
    """A-GATE-1 必须通过真实模块入口生成 30 条结果报告。"""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.evaluation.cli",
            "--dataset",
            "evals/datasets/core-v7-candidate.jsonl",
            "--fixtures",
            "evals/fixtures/offline-core-v7.json",
            "--output-dir",
            str(tmp_path / "v7-core-report"),
            "--mode",
            "offline-core",
            "--execution-context",
            "pr",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        check=False,
    )
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined_output
    report = json.loads(
        (tmp_path / "v7-core-report" / "evaluation-report.json").read_text(encoding="utf-8")
    )
    assert report["passed"] is True
    assert len(report["results"]) == 30
    assert all(item["passed"] for item in report["results"])
