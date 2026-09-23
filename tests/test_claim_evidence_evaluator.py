"""A2.4 声明—证据支持度评估契约。"""

import pytest

from src.evaluation import EvaluationCase, evaluate_claim_evidence_support


def _case(*, expected_facts=None, expected_sources=None) -> EvaluationCase:
    expected_facts = expected_facts or [
        {
            "metric_key": "revenue",
            "value": 0,
            "unit": "亿元",
            "currency": "CNY",
            "period": "2024",
        }
    ]
    expected_sources = expected_sources or [{"source_file": "示例公司.pdf", "pages": [12]}]
    return EvaluationCase.from_dict(
        {
            "id": "claim-evidence-case-001",
            "category": "numeric",
            "query": "示例公司 2024 年营业收入是多少？",
            "companies": ["示例公司"],
            "expected_answer": "示例公司 2024 年营业收入为 0 亿元。",
            "expected_facts": expected_facts,
            "expected_sources": expected_sources,
            "expected_pages": [12],
            "numeric_tolerance": 0.01,
            "expected_behavior": "answer",
            "expected_tools": ["retrieve"],
            "risk_level": "high",
            "review_status": "verified",
            "dataset_version": "v1",
        }
    )


def test_complete_structured_fact_and_source_are_fully_supported():
    result = evaluate_claim_evidence_support(
        _case(),
        {
            "facts": [
                {
                    "metric_key": "revenue",
                    "value": 0,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                    "normalized_value": 0,
                    "normalized_unit": "元",
                }
            ],
            "sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
        },
    )

    assert result == 1.0


def test_missing_structured_fields_are_unknown_not_implicitly_supported():
    result = evaluate_claim_evidence_support(
        _case(),
        {
            "facts": [{"metric_key": "revenue", "value": 0}],
            "sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
        },
    )

    assert result is None


def test_missing_source_is_explicitly_unsupported():
    result = evaluate_claim_evidence_support(
        _case(),
        {
            "facts": [
                {
                    "metric_key": "revenue",
                    "value": 0,
                    "normalized_value": 0,
                    "normalized_unit": "元",
                }
            ],
            "sources": [],
        },
    )

    assert result == 0.0


@pytest.mark.parametrize(
    ("field", "value"),
    [("value", 1), ("unit", "万元"), ("currency", "USD"), ("period", "2023")],
)
def test_mismatched_fact_fields_are_not_supported(field, value):
    actual_fact = {
        "metric_key": "revenue",
        "value": 0,
        "unit": "亿元",
        "currency": "CNY",
        "period": "2024",
        "normalized_value": 0,
        "normalized_unit": "元",
    }
    actual_fact[field] = value

    result = evaluate_claim_evidence_support(
        _case(),
        {
            "facts": [actual_fact],
            "sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
        },
    )

    assert result == 0.0


def test_multiple_facts_are_scored_individually():
    result = evaluate_claim_evidence_support(
        _case(
            expected_facts=[
                {
                    "metric_key": "revenue",
                    "value": 100,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                },
                {
                    "metric_key": "net_profit",
                    "value": 10,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                },
            ]
        ),
        {
            "facts": [
                {
                    "metric_key": "revenue",
                    "value": 100,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                    "normalized_value": 10000000000,
                    "normalized_unit": "元",
                },
                {
                    "metric_key": "net_profit",
                    "value": 11,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                    "normalized_value": 1100000000,
                    "normalized_unit": "元",
                },
            ],
            "sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
        },
    )

    assert result == 0.5


def test_company_specific_facts_do_not_match_the_first_same_metric():
    result = evaluate_claim_evidence_support(
        _case(
            expected_facts=[
                {
                    "metric_key": "revenue",
                    "company": "中国移动",
                    "value": 100,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                },
                {
                    "metric_key": "revenue",
                    "company": "中国电信",
                    "value": 50,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                },
            ],
            expected_sources=[
                {"source_file": "移动.pdf", "pages": [1]},
                {"source_file": "电信.pdf", "pages": [2]},
            ],
        ),
        {
            "facts": [
                {
                    "metric_key": "revenue",
                    "company": "中国电信",
                    "value": 50,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                    "normalized_value": 5000000000,
                    "normalized_unit": "元",
                },
            ],
            "sources": [
                {"source_file": "移动.pdf", "pages": [1]},
                {"source_file": "电信.pdf", "pages": [2]},
            ],
        },
    )

    assert result == 0.5


def test_missing_one_expected_source_is_not_fully_supported():
    result = evaluate_claim_evidence_support(
        _case(expected_sources=[
            {"source_file": "示例公司.pdf", "pages": [12]},
            {"source_file": "示例公司补充.pdf", "pages": [3]},
        ]),
        {
            "facts": [
                {
                    "metric_key": "revenue",
                    "value": 0,
                    "unit": "亿元",
                    "currency": "CNY",
                    "period": "2024",
                    "normalized_value": 0,
                    "normalized_unit": "元",
                }
            ],
            "sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
        },
    )

    assert result == 0.0
