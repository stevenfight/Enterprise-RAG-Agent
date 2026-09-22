"""A2.5 期望关键词确定性评估契约。"""

from pathlib import Path

from src.evaluation import EvaluationCase, evaluate_case, match_expected_keywords


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _case(expected_keywords: list[str]) -> EvaluationCase:
    return EvaluationCase.from_dict(
        {
            "id": "keyword-case-001",
            "category": "simple_fact",
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
            "expected_keywords": expected_keywords,
        }
    )


def test_keyword_match_is_case_insensitive_substring_and_reports_missing():
    hit_rate, matched, missing = match_expected_keywords(
        ["营业收入", "100", "CNY"],
        "本公司的营业收入为 100 亿元，币种为 cny。",
    )

    assert hit_rate == 1.0
    assert matched == ["营业收入", "100", "CNY"]
    assert missing == []

    hit_rate, matched, missing = match_expected_keywords(
        ["营业收入", "100", "CNY"],
        "本公司的营业收入为 100 亿元。",
    )
    assert hit_rate == 2 / 3
    assert matched == ["营业收入", "100"]
    assert missing == ["CNY"]


def test_empty_expected_keywords_are_not_scored():
    assert match_expected_keywords([], "任意答案") == (None, [], [])


def test_evaluate_case_reports_keyword_hit_rate_and_legacy_threshold():
    case = _case(["营业收入", "100", "亿元"])
    result = evaluate_case(
        case,
        {
            "answer": "营业收入为 100 亿元。",
            "facts": case.expected_facts,
            "sources": [{"source_file": "示例公司.pdf", "pages": [12]}],
            "tools": ["retrieve"],
        },
    )
    assert result.metrics["keyword_hit_rate"] == 1.0
    assert result.passed is True

    low_match = evaluate_case(
        _case(["营业收入", "100", "亿元"]),
        {
            "answer": "营业收入已核对。",
            "facts": [],
            "sources": [],
            "tools": [],
        },
    )
    assert low_match.metrics["keyword_hit_rate"] == 1 / 3
    assert "expected_keywords_below_threshold" in low_match.failures


def test_legacy_evaluation_scripts_delegate_keyword_matching():
    for script_name in ("tests/eval_langsmith.py", "tests/eval_openevals.py"):
        source = (PROJECT_ROOT / script_name).read_text(encoding="utf-8")
        assert "from src.evaluation import match_expected_keywords" in source
        assert "answer_lower = answer.lower()" not in source
