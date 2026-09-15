"""评测来源证据审计的 RED/GREEN 测试。"""

from pathlib import Path

from src.evaluation import EvaluationCase
from src.evaluation.source_audit import audit_source_files


def make_case() -> EvaluationCase:
    return EvaluationCase.from_dict(
        {
            "id": "source-audit-001",
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
            "dataset_version": "test",
        }
    )


def test_source_audit_reports_missing_file(tmp_path: Path):
    report = audit_source_files([make_case()], [tmp_path])

    assert report == {
        "checked_source_count": 1,
        "missing_source_files": ["示例公司.pdf"],
        "ready": False,
    }


def test_source_audit_accepts_file_in_any_root(tmp_path: Path):
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "示例公司.pdf").write_bytes(b"%PDF-test")

    report = audit_source_files([make_case()], [tmp_path, source_root])

    assert report == {
        "checked_source_count": 1,
        "missing_source_files": [],
        "ready": True,
    }
