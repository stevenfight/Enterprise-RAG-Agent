"""既有 PDF 派生产物复用决策的确定性测试。"""

import json
from pathlib import Path


def _source(filename: str, readability: str = "readable") -> dict:
    return {
        "filename": filename,
        "sha256": "a" * 64,
        "physical_page_count": 10,
        "readability_status": readability,
        "encryption_status": "not_encrypted",
    }


def test_existing_markdown_without_provenance_is_enrich_not_reuse():
    from src.document_reuse_decision import build_reuse_decisions

    decisions = build_reuse_decisions(
        [_source("报告.pdf")],
        [{"filename": "报告.pdf", "markdown_status": "matched", "asset_status": "complete"}],
    )

    decision = decisions["documents"][0]
    assert decision["decision"] == "ENRICH"
    assert "missing_parser_provenance" in decision["reasons"]
    assert decision["error_status"] is None


def test_missing_images_stays_enrich_and_records_missing_asset_evidence():
    from src.document_reuse_decision import build_reuse_decisions

    decisions = build_reuse_decisions(
        [_source("报告.pdf")],
        [
            {
                "filename": "报告.pdf",
                "markdown_status": "matched",
                "asset_status": "incomplete",
                "missing_local_image_count": 3,
            }
        ],
    )

    decision = decisions["documents"][0]
    assert decision["decision"] == "ENRICH"
    assert "missing_local_assets" in decision["reasons"]
    assert decision["error_status"] == "missing_local_assets"


def test_missing_markdown_requires_full_reextract_with_explicit_reason():
    from src.document_reuse_decision import build_reuse_decisions

    decision = build_reuse_decisions(
        [_source("报告.pdf")],
        [{"filename": "报告.pdf", "markdown_status": "missing", "asset_status": "incomplete"}],
    )["documents"][0]

    assert decision["decision"] == "FULL_REEXTRACT"
    assert decision["reasons"] == ["missing_markdown"]
    assert decision["error_status"] == "missing_markdown"


def test_unreadable_source_is_explicitly_blocked_without_guessing_a_reuse_path():
    from src.document_reuse_decision import build_reuse_decisions

    decision = build_reuse_decisions(
        [_source("报告.pdf", readability="unreadable")],
        [{"filename": "报告.pdf", "markdown_status": "matched", "asset_status": "complete"}],
    )["documents"][0]

    assert decision["decision"] == "FULL_REEXTRACT"
    assert decision["error_status"] == "source_unreadable"
    assert decision["reasons"] == ["source_unreadable"]


def test_reuse_decision_report_is_written_atomically(tmp_path: Path):
    from src.document_reuse_decision import write_reuse_decisions

    output_path = tmp_path / "reuse_decisions.json"
    decisions = {"schema_version": 1, "documents": []}

    write_reuse_decisions(decisions, output_path)

    assert not output_path.with_name(output_path.name + ".writing").exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == decisions
