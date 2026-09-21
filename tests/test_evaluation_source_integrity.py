"""评测来源文件与冻结清单绑定的 RED/GREEN 测试。"""

import hashlib
import json
import sys
from pathlib import Path

import fitz

from src.evaluation import EvaluationCase
from src.evaluation.source_integrity import audit_source_integrity
from src.evaluation.cli import main as evaluation_cli_main


def _case(source_file: str = "source.pdf") -> EvaluationCase:
    return EvaluationCase.from_dict(
        {
            "id": "integrity-001",
            "category": "numeric",
            "query": "公司 2024 年营业收入是多少？",
            "companies": ["示例公司"],
            "expected_answer": "2024 年营业收入为 100 亿元。",
            "expected_facts": [],
            "expected_sources": [{"source_file": source_file, "pages": [1]}],
            "expected_pages": [1],
            "numeric_tolerance": 0.01,
            "expected_behavior": "answer",
            "expected_tools": ["retrieve"],
            "risk_level": "high",
            "review_status": "draft",
            "dataset_version": "integrity-test",
        }
    )


def _write_pdf(path: Path, pages: int) -> None:
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    document.save(path)
    document.close()


def _write_inventory(path: Path, pdf_path: Path, pages: int) -> None:
    payload = {
        "schema_version": 1,
        "documents": [
            {
                "filename": pdf_path.name,
                "relative_source_path": pdf_path.name,
                "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                "size_bytes": pdf_path.stat().st_size,
                "physical_page_count": pages,
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_source_integrity_accepts_matching_hash_size_and_pages(tmp_path: Path):
    source = tmp_path / "source.pdf"
    inventory = tmp_path / "inventory.json"
    _write_pdf(source, 1)
    _write_inventory(inventory, source, 1)

    report = audit_source_integrity([_case()], [tmp_path], inventory)

    assert report["ready"] is True
    assert report["missing_inventory_files"] == []
    assert report["missing_source_files"] == []
    assert report["sha256_mismatches"] == []
    assert report["size_mismatches"] == []
    assert report["physical_page_mismatches"] == []


def test_source_integrity_reports_hash_and_size_drift(tmp_path: Path):
    source = tmp_path / "source.pdf"
    inventory = tmp_path / "inventory.json"
    _write_pdf(source, 1)
    _write_inventory(inventory, source, 1)
    source.write_bytes(source.read_bytes() + b"drift")

    report = audit_source_integrity([_case()], [tmp_path], inventory)

    assert report["ready"] is False
    assert report["sha256_mismatches"] == ["source.pdf"]
    assert report["size_mismatches"] == ["source.pdf"]


def test_source_integrity_reports_physical_page_drift(tmp_path: Path):
    source = tmp_path / "source.pdf"
    inventory = tmp_path / "inventory.json"
    _write_pdf(source, 1)
    _write_inventory(inventory, source, 1)
    source.unlink()
    _write_pdf(source, 2)

    report = audit_source_integrity([_case()], [tmp_path], inventory)

    assert report["ready"] is False
    assert report["physical_page_mismatches"] == ["source.pdf"]


def test_source_integrity_reports_unregistered_source(tmp_path: Path):
    source = tmp_path / "source.pdf"
    inventory = tmp_path / "inventory.json"
    _write_pdf(source, 1)
    inventory.write_text('{"schema_version": 1, "documents": []}', encoding="utf-8")

    report = audit_source_integrity([_case()], [tmp_path], inventory)

    assert report["ready"] is False
    assert report["missing_inventory_files"] == ["source.pdf"]


def test_source_integrity_reports_missing_source_file(tmp_path: Path):
    source = tmp_path / "source.pdf"
    inventory = tmp_path / "inventory.json"
    _write_pdf(source, 1)
    _write_inventory(inventory, source, 1)
    source.unlink()

    report = audit_source_integrity([_case()], [tmp_path], inventory)

    assert report["ready"] is False
    assert report["missing_source_files"] == ["source.pdf"]


def test_cli_writes_source_integrity_report_for_inventory_mismatch(
    tmp_path: Path, monkeypatch
):
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text(
        Path("evals/fixtures/offline-core.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    inventory = tmp_path / "inventory.json"
    inventory.write_text('{"schema_version": 1, "documents": []}', encoding="utf-8")
    output_dir = tmp_path / "report"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--dataset",
            "evals/datasets/core.jsonl",
            "--fixtures",
            str(fixtures),
            "--output-dir",
            str(output_dir),
            "--source-root",
            str(tmp_path),
            "--source-inventory",
            str(inventory),
        ],
    )

    assert evaluation_cli_main() == 1
    report = json.loads(
        (output_dir / "evaluation-report.json").read_text(encoding="utf-8")
    )
    assert report["metadata"]["source_integrity"]["ready"] is False
