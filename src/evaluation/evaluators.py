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


def _matching_fact(
    facts: list[dict[str, Any]],
    expected_fact: dict[str, Any],
) -> dict[str, Any] | None:
    """按指标键及已声明的口径字段匹配事实，避免同指标事实串用。"""
    metric_key = expected_fact.get("metric_key")
    if not metric_key:
        return None
    for fact in facts:
        if fact.get("metric_key") != metric_key:
            continue
        if any(
            field in expected_fact and fact.get(field) != expected_fact[field]
            for field in ("company", "unit", "currency", "period")
        ):
            continue
        return fact
    return None


def _has_normalized_value(fact: dict[str, Any] | None) -> bool:
    """判断归一值是否已提供，保留合法零值并拒绝空值。"""
    return bool(
        fact
        and "normalized_value" in fact
        and fact["normalized_value"] is not None
        and fact["normalized_value"] != ""
    )


def _fact_matches_expected(
    expected_fact: dict[str, Any],
    actual_fact: dict[str, Any] | None,
    tolerance: float,
) -> bool:
    """校验声明事实的归一值存在性及已声明的口径字段。"""
    if not _has_normalized_value(actual_fact):
        return False
    if "value" in expected_fact:
        actual_value = actual_fact.get("value") if actual_fact else None
        if not compare_numeric(expected_fact["value"], actual_value, tolerance).passed:
            return False
    for field in ("unit", "currency", "period"):
        if field in expected_fact and (not actual_fact or actual_fact.get(field) != expected_fact[field]):
            return False
    return True


def _source_hit(expected, actual_sources: list[dict[str, Any]]) -> bool:
    for actual in actual_sources:
        if actual.get("source_file") != expected.source_file:
            continue
        if set(expected.pages).issubset(set(actual.get("pages", []))):
            return True
    return False


def evaluate_claim_evidence_support(case: EvaluationCase, actual: dict[str, Any]) -> float | None:
    """计算声明级证据支持率，并区分未知、明确不支持和完全支持。

    候选完全未携带声明级字段时返回 None（A 阶段行为保持不变，不得冒充声明级指标）；
    部分携带或证据不完整时按不支持计分，无法确定时不得自动通过。
    """
    actual_facts = actual.get("facts", [])
    if not case.expected_facts:
        return None
    if not any(_has_normalized_value(fact) for fact in actual_facts):
        return None
    actual_sources = actual.get("sources", [])
    sources_supported = bool(case.expected_sources) and all(
        _source_hit(expected_source, actual_sources)
        for expected_source in case.expected_sources
    )
    supported = 0
    for expected_fact in case.expected_facts:
        actual_fact = _matching_fact(actual_facts, expected_fact)
        if _fact_matches_expected(expected_fact, actual_fact, case.numeric_tolerance) and sources_supported:
            supported += 1
    return supported / len(case.expected_facts)


def _claim_evidence_support(case: EvaluationCase, actual: dict[str, Any]) -> float | None:
    """保留旧版私有调用入口，统一复用公开声明级评估器。"""
    return evaluate_claim_evidence_support(case, actual)


KEYWORD_MINIMUM_HIT_RATE = 0.5
REFUSAL_MARKERS = (
    "无法",
    "不足",
    "不确定",
    "待确认",
    "暂停确定性",
    "不能直接",
    "不能自动",
    "人工复核",
)


def _is_refusal_answer(answer: str) -> bool:
    """识别拒答契约的确定性边界表达，不要求固定某一个措辞。"""
    return any(marker in answer for marker in REFUSAL_MARKERS)


def match_expected_keywords(
    expected_keywords: list[str],
    answer: str,
) -> tuple[float | None, list[str], list[str]]:
    """按旧版评测兼容规则计算答案关键词命中率。

    关键词使用大小写不敏感的子串匹配；空关键词不参与匹配，直接视为调用错误。
    没有配置期望关键词时返回 ``None``，让调用方区分“未配置”和“零命中”。
    """
    if not expected_keywords:
        return None, [], []
    if any(not isinstance(keyword, str) or not keyword.strip() for keyword in expected_keywords):
        raise ValueError("expected_keywords 必须是非空字符串列表")
    normalized_answer = str(answer or "").casefold()
    matched = [keyword for keyword in expected_keywords if keyword.casefold() in normalized_answer]
    missing = [keyword for keyword in expected_keywords if keyword not in matched]
    return len(matched) / len(expected_keywords), matched, missing


def evaluate_case(case: EvaluationCase, actual: dict[str, Any]) -> CaseEvaluation:
    """评估一个固定输出，A 阶段只报告答案级证据。"""
    metrics: dict[str, float] = {}
    failures: list[str] = []
    actual_facts = actual.get("facts", [])
    keyword_hit_rate, _, _ = match_expected_keywords(
        case.expected_keywords,
        str(actual.get("answer") or ""),
    )
    if keyword_hit_rate is not None:
        metrics["keyword_hit_rate"] = keyword_hit_rate
        if keyword_hit_rate < KEYWORD_MINIMUM_HIT_RATE:
            failures.append("expected_keywords_below_threshold")
    if case.expected_behavior == "refuse":
        answer = str(actual.get("answer", ""))
        refused = _is_refusal_answer(answer)
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
