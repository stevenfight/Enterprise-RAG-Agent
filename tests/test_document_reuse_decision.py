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


def test_reuse_execution_plan_reuses_complete_markdown_and_local_assets(tmp_path: Path):
    from src.document_reuse_execution import build_reuse_execution_plan

    markdown_dir = tmp_path / "markdown"
    image_dir = markdown_dir / "images"
    image_dir.mkdir(parents=True)
    markdown_path = markdown_dir / "报告.md"
    markdown_path.write_text("![图](images/chart.png)\n\n| 指标 | 数值 |", encoding="utf-8")
    (image_dir / "chart.png").write_bytes(b"chart")

    plan = build_reuse_execution_plan(
        [{"filename": "报告.pdf", "decision": "ENRICH", "error_status": None}],
        [{"filename": "报告.pdf", "markdown_status": "matched", "markdown_filename": "报告.md", "asset_status": "complete"}],
        markdown_dir,
    )

    document = plan["documents"][0]
    assert document["action"] == "REUSE_EXISTING_ASSETS"
    assert document["markdown_path"] == str(markdown_path.resolve())
    assert document["local_asset_paths"] == [str((image_dir / "chart.png").resolve())]
    assert document["targeted_tasks"] == []


def test_reuse_execution_plan_only_creates_explicit_targeted_scope(tmp_path: Path):
    from src.document_reuse_execution import build_reuse_execution_plan

    markdown_dir = tmp_path / "markdown"
    markdown_dir.mkdir()
    (markdown_dir / "报告.md").write_text("# 已有文本", encoding="utf-8")

    plan = build_reuse_execution_plan(
        [{"filename": "报告.pdf", "decision": "ENRICH", "error_status": "missing_local_assets"}],
        [{"filename": "报告.pdf", "markdown_status": "matched", "markdown_filename": "报告.md", "asset_status": "incomplete"}],
        markdown_dir,
        targeted_requests=[
            {"filename": "报告.pdf", "task_kind": "complex_table", "physical_pages": [18], "reason": "table_cell_merge"},
        ],
    )

    document = plan["documents"][0]
    assert document["action"] == "REUSE_EXISTING_ASSETS"
    assert document["targeted_tasks"] == [
        {"task_kind": "complex_table", "physical_pages": [18], "reason": "table_cell_merge"},
    ]


def test_reuse_execution_plan_does_not_infer_targeted_work_from_incomplete_inventory(tmp_path: Path):
    from src.document_reuse_execution import build_reuse_execution_plan

    markdown_dir = tmp_path / "markdown"
    markdown_dir.mkdir()
    (markdown_dir / "报告.md").write_text("![缺失](missing.png)", encoding="utf-8")

    plan = build_reuse_execution_plan(
        [{"filename": "报告.pdf", "decision": "ENRICH", "error_status": "missing_local_assets"}],
        [{"filename": "报告.pdf", "markdown_status": "matched", "markdown_filename": "报告.md", "asset_status": "incomplete"}],
        markdown_dir,
    )

    assert plan["documents"][0]["targeted_tasks"] == []


def test_reuse_execution_plan_rejects_unsafe_markdown_filename(tmp_path: Path):
    from src.document_reuse_execution import build_reuse_execution_plan

    markdown_dir = tmp_path / "markdown"
    markdown_dir.mkdir()

    plan = build_reuse_execution_plan(
        [{"filename": "报告.pdf", "decision": "ENRICH", "error_status": None}],
        [{"filename": "报告.pdf", "markdown_status": "matched", "markdown_filename": "../outside.md", "asset_status": "complete"}],
        markdown_dir,
    )

    document = plan["documents"][0]
    assert document["action"] == "FULL_REEXTRACT"
    assert document["error_status"] == "unsafe_markdown_path"
