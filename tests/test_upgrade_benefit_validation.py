"""B2.7 用 A 评测集验证 B 阶段升级收益。

验证语义：
- 启用声明级证据支持率硬门禁（spec-evaluation-quality-gate.md 分阶段证据指标场景）；
- 升级候选（携带 B2.6 声明级证据载荷）通过门禁且相对基线无新增失败；
- 缺声明级载荷或调低通过率都无法让门禁通过（未达到门禁则修正而不是降低阈值）。

所有用例只使用固定夹具，不调用外部模型或网络服务。
"""

import json
from pathlib import Path

from src.evaluation import EvaluationRunner, load_jsonl_cases, load_thresholds


SEED_CASES = load_jsonl_cases(Path("evals/datasets/core.jsonl"))
THRESHOLDS = load_thresholds(Path("evals/config/thresholds.yaml"))


def _baseline_fixture(case_id: str) -> dict:
    """升级前基线输出：答案级载荷，不含声明级证据字段。"""
    return {
        "answer": "2024年营业收入为100亿元。",
        "facts": [
            {"metric_key": "revenue", "value": 100, "unit": "亿元", "currency": "CNY", "period": "2024"}
        ],
        "sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
        "tools": ["retrieve"],
    }


def _upgraded_fixture(case_id: str) -> dict:
    """升级后候选输出：同一答案追加 B2.6 声明级证据载荷。"""
    baseline = _baseline_fixture(case_id)
    facts = [
        {
            **fact,
            "raw_value": "100亿元",
            "raw_unit": "亿元",
            "normalized_value": "10000000000",
            "normalized_unit": "元",
        }
        for fact in baseline["facts"]
    ]
    return {
        **baseline,
        "facts": facts,
        "calculations": [],
        "conflicts": [],
    }


def test_upgraded_candidate_passes_claim_evidence_gate():
    runner = EvaluationRunner(mode="offline-core")
    report = runner.run(
        SEED_CASES,
        {case.case_id: _upgraded_fixture(case.case_id) for case in SEED_CASES},
    )
    result = report.results[0]
    assert result.metrics["claim_level_evidence_support"] == 1.0
    assert EvaluationRunner.passes_quality_gate(report, thresholds=THRESHOLDS) is True


def test_upgrade_diff_shows_benefit_without_new_failures():
    runner = EvaluationRunner(mode="offline-core")
    baseline_report = runner.run(
        SEED_CASES,
        {case.case_id: _baseline_fixture(case.case_id) for case in SEED_CASES},
    )
    candidate_report = runner.run(
        SEED_CASES,
        {case.case_id: _upgraded_fixture(case.case_id) for case in SEED_CASES},
    )
    baseline = {result.case_id: {"passed": result.passed} for result in baseline_report.results}
    candidate = {result.case_id: {"passed": result.passed} for result in candidate_report.results}
    diff = EvaluationRunner.diff(baseline, candidate)
    assert diff["new_failures"] == []
    # 升级收益可见：候选新增了基线不存在的声明级证据支持率指标。
    assert "claim_level_evidence_support" not in baseline_report.results[0].metrics
    assert candidate_report.results[0].metrics["claim_level_evidence_support"] == 1.0


def test_missing_claim_evidence_fails_gate_when_enabled():
    runner = EvaluationRunner(mode="offline-core")
    report = runner.run(
        SEED_CASES,
        {case.case_id: _baseline_fixture(case.case_id) for case in SEED_CASES},
    )
    # 声明级门禁启用后，答案类样本缺失声明级证据支持率指标不得自动通过。
    assert EvaluationRunner.passes_quality_gate(report, thresholds=THRESHOLDS) is False


def test_lower_pass_rate_cannot_rescue_missing_claim_evidence():
    runner = EvaluationRunner(mode="offline-core")
    report = runner.run(
        SEED_CASES,
        {case.case_id: _baseline_fixture(case.case_id) for case in SEED_CASES},
    )
    # 调低总体通过率无法弥补声明级门禁失败：未达标就修正，而不是降低阈值。
    assert (
        EvaluationRunner.passes_quality_gate(report, minimum_pass_rate=0.5, thresholds=THRESHOLDS)
        is False
    )
