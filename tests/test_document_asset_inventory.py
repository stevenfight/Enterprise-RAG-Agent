"""现有 Markdown 制品清点的确定性测试。"""

import json
from pathlib import Path


def test_asset_inventory_reports_existing_and_missing_local_assets_without_guessing(tmp_path: Path):
    from src.document_asset_inventory import build_document_asset_inventory

    pdf_dir = tmp_path / "pdf_reports"
    markdown_dir = tmp_path / "markdown"
    image_dir = markdown_dir / "images"
    pdf_dir.mkdir()
    image_dir.mkdir(parents=True)
    (pdf_dir / "示例报告.pdf").write_bytes(b"%PDF-1.7\nplaceholder")
    (image_dir / "exists.png").write_bytes(b"image")
    (markdown_dir / "示例报告.md").write_text(
        """# 示例

![已有](images/exists.png)
![缺失](images/missing.png)
![远程](https://example.com/chart.png)

| 指标 | 数值 |
| --- | --- |
| 收入 | 1 |

<table><tr><td>结构化表格</td></tr></table>

公式：$x+y$。
""",
        encoding="utf-8",
    )

    inventory = build_document_asset_inventory(pdf_dir, markdown_dir)

    document = inventory["documents"][0]
    assert document["filename"] == "示例报告.pdf"
    assert document["markdown_status"] == "matched"
    assert document["asset_status"] == "incomplete"
    assert document["markdown_table_count"] == 1
    assert document["html_table_count"] == 1
    assert document["formula_marker_count"] == 2
    assert document["local_image_reference_count"] == 2
    assert document["existing_local_image_count"] == 1
    assert document["missing_local_image_count"] == 1
    assert document["remote_image_reference_count"] == 1
    assert document["missing_local_assets"] == ["images/missing.png"]


def test_asset_inventory_marks_missing_markdown_incomplete(tmp_path: Path):
    from src.document_asset_inventory import build_document_asset_inventory

    pdf_dir = tmp_path / "pdf_reports"
    markdown_dir = tmp_path / "markdown"
    pdf_dir.mkdir()
    markdown_dir.mkdir()
    (pdf_dir / "无Markdown.pdf").write_bytes(b"%PDF-1.7\nplaceholder")

    document = build_document_asset_inventory(pdf_dir, markdown_dir)["documents"][0]

    assert document["markdown_status"] == "missing"
    assert document["asset_status"] == "incomplete"
    assert document["missing_local_assets"] == []


def test_asset_inventory_diagnostic_write_is_atomic(tmp_path: Path):
    from src.document_asset_inventory import write_document_asset_inventory

    output_path = tmp_path / "asset_inventory.json"
    inventory = {"schema_version": 1, "documents": []}

    write_document_asset_inventory(inventory, output_path)

    assert not output_path.with_name(output_path.name + ".writing").exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == inventory
