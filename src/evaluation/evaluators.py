"""不依赖模型的确定性评估器。"""

import math
from typing import Any

from .models import CaseEvaluation, EvaluationCase, NumericComparison


def compare_numeric(expected: float, actual: float, tolerance: float) -> NumericComparison:
    """按相对误差比较数字，避免把数量级错误当作舍入误差。"""
    if not isinstance(expected, (int, float)) or not isinstance(actual, (int, float)):
        return NumericComparison(False, "not_numeric")
    if not math.isfinite(float(expected)) or not math.isfinite(float(actual)):
        return NumericComparison(False, "not_finite")
    denominator = max(abs(float(expected)), 1.0)
    passed = abs(float(expected) - float(actual)) / denominator <= tolerance
    return NumericComparison(passed, "within_tolerance" if passed else "value_mismatch")


def _first_fact(facts: list[dict[str, Any]], metric_key: str) -> dict[str, Any] | None:
    for fact in facts:
        if fact.get("metric_key") == metric_key:
            return fact
    return None


def _source_hit(expected, actual_sources: list[dict[str, Any]]) -> bool:
    for actual in actual_sources:
        if actual.get("source_file") != expected.source_file:
            continue
        if set(expected.pages).issubset(set(actual.get("pages", []))):
            return True
    return False


def _claim_evidence_support(case: EvaluationCase, actual: dict[str, Any]) -> float | None:
    """B 阶段声明级证据支持率：每个期望声明都要有可追溯的归一事实与来源证据。

    候选完全未携带声明级字段时返回 None（A 阶段行为保持不变，不得冒充声明级指标）；
    部分携带或证据不完整时按不支持计分，无法确定时不得自动通过。
    """
    actual_facts = actual.get("facts", [])
    if not case.expected_facts:
        return None
    if all("normalized_value" not in fact for fact in actual_facts):
        return None
    actual_sources = actual.get("sources", [])
    supported = 0
    for expected_fact in case.expected_facts:
        actual_fact = _first_fact(actual_facts, expected_fact.get("metric_key"))
        has_normalized = bool(actual_fact and actual_fact.get("normalized_value"))
        has_source = any(_source_hit(source, actual_sources) for source in case.expected_sources)
        if has_normalized and has_source:
            supported += 1
    return supported / len(case.expected_facts)


def evaluate_case(case: EvaluationCase, actual: dict[str, Any]) -> CaseEvaluation:
    """评估一个固定输出，A 阶段只报告答案级证据。"""
    metrics: dict[str, float] = {}
    failures: list[str] = []
    actual_facts = actual.get("facts", [])
    if case.expected_behavior == "refuse":
        answer = str(actual.get("answer", ""))
        refused = any(word in answer for word in ("无法", "不足", "不确定", "待确认"))
        metrics["refusal_accuracy"] = 1.0 if refused else 0.0
        if not refused:
            failures.append("expected_refusal")
    elif case.expected_facts:
        expected_fact = case.expected_facts[0]
        actual_fact = _first_fact(actual_facts, expected_fact.get("metric_key"))
        value_result = compare_numeric(
            expected_fact.get("value"),
            actual_fact.get("value") if actual_fact else None,
            case.numeric_tolerance,
        )
        metrics["value_accuracy"] = float(value_result.passed)
        metrics["unit_accuracy"] = float(bool(actual_fact and actual_fact.get("unit") == expected_fact.get("unit")))
        metrics["currency_accuracy"] = float(bool(actual_fact and actual_fact.get("currency") == expected_fact.get("currency")))
        metrics["period_accuracy"] = float(bool(actual_fact and actual_fact.get("period") == expected_fact.get("period")))
        if not value_result.passed:
            failures.append(value_result.reason)
        for key in ("unit_accuracy", "currency_accuracy", "period_accuracy"):
            if metrics[key] == 0.0:
                failures.append(key)
    expected_sources = case.expected_sources
    actual_sources = actual.get("sources", [])
    source_hits = sum(_source_hit(expected, actual_sources) for expected in expected_sources)
    metrics["answer_level_source_hit"] = source_hits / len(expected_sources) if expected_sources else 1.0
    if expected_sources and source_hits != len(expected_sources):
        failures.append("source_or_page_mismatch")
    actual_tools = list(actual.get("tools", []))
    metrics["tool_trace_accuracy"] = float(actual_tools == case.expected_tools)
    if actual_tools != case.expected_tools:
        failures.append("tool_trace_mismatch")
    claim_support = _claim_evidence_support(case, actual)
    if claim_support is not None:
        metrics["claim_level_evidence_support"] = claim_support
        if claim_support < 1.0:
            failures.append("claim_evidence_unsupported")
    return CaseEvaluation(case.case_id, not failures, metrics, failures, case.risk_level)
