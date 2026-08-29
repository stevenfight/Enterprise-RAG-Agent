"""源 PDF 冻结清单的确定性测试。"""

import json
from pathlib import Path

import fitz


def _create_pdf(path: Path, pages: int) -> None:
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    document.save(path)
    document.close()


def test_source_inventory_records_hash_page_readability_and_legacy_company(tmp_path: Path):
    from src.source_inventory import build_source_inventory

    pdf_dir = tmp_path / "pdf_reports"
    pdf_dir.mkdir()
    _create_pdf(pdf_dir / "甲公司年报.pdf", 2)
    _create_pdf(pdf_dir / "未映射研报.pdf", 1)
    registry_path = tmp_path / "company_registry.json"
    registry_path.write_text(
        json.dumps(
            {"companies": {"甲公司": {"source_files": ["甲公司年报.pdf"]}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    inventory = build_source_inventory(pdf_dir, registry_path)

    documents = {item["filename"]: item for item in inventory["documents"]}
    mapped = documents["甲公司年报.pdf"]
    assert mapped["sha256"]
    assert mapped["physical_page_count"] == 2
    assert mapped["readability_status"] == "readable"
    assert mapped["encryption_status"] == "not_encrypted"
    assert mapped["company_name"] == "甲公司"
    assert mapped["logical_document_key"] == "legacy:甲公司:甲公司年报.pdf"

    unmapped = documents["未映射研报.pdf"]
    assert unmapped["company_name"] is None
    assert unmapped["logical_document_key"] is None


def test_source_inventory_write_is_atomic_and_does_not_change_pdf_bytes(tmp_path: Path):
    from src.source_inventory import build_source_inventory, write_source_inventory

    pdf_dir = tmp_path / "pdf_reports"
    pdf_dir.mkdir()
    pdf_path = pdf_dir / "只读源文件.pdf"
    _create_pdf(pdf_path, 1)
    original = pdf_path.read_bytes()

    inventory = build_source_inventory(pdf_dir, tmp_path / "missing-registry.json")
    output_path = tmp_path / "source_inventory.json"
    write_source_inventory(inventory, output_path)

    assert pdf_path.read_bytes() == original
    assert not output_path.with_name(output_path.name + ".writing").exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == inventory


def test_source_inventory_does_not_guess_duplicate_legacy_company_mapping(tmp_path: Path):
    from src.source_inventory import build_source_inventory

    pdf_dir = tmp_path / "pdf_reports"
    pdf_dir.mkdir()
    _create_pdf(pdf_dir / "冲突来源.pdf", 1)
    registry_path = tmp_path / "company_registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "companies": {
                    "甲公司": {"source_files": ["冲突来源.pdf"]},
                    "乙公司": {"source_files": ["冲突来源.pdf"]},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    document = build_source_inventory(pdf_dir, registry_path)["documents"][0]

    assert document["logical_mapping_status"] == "ambiguous"
    assert document["company_name"] is None
    assert document["logical_document_key"] is None
