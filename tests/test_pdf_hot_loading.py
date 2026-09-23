"""PDF 热加载清单的确定性测试。"""

import json
from pathlib import Path

import pytest

import src.knowledge_service as knowledge_service
from src.knowledge_service import (
    get_documents,
    get_pending_documents,
    sync_pdf_directory,
    delete_pdf,
    mark_pdf_index_failed,
    mark_pdf_indexed,
    retry_pdf_index,
    upload_pdf,
)


@pytest.fixture
def isolated_pdf_store(tmp_path: Path, monkeypatch):
    pdf_dir = tmp_path / "pdf_reports"
    monkeypatch.setattr(knowledge_service, "_PDF_DIR", pdf_dir)
    monkeypatch.setattr(knowledge_service, "_VECTOR_DB_DIR", tmp_path / "vector_dbs")
    monkeypatch.setattr(knowledge_service, "_MANIFEST_PATH", tmp_path / "manifest.json")
    return pdf_dir


def test_upload_pdf_is_atomic_and_enters_pending_index(isolated_pdf_store):
    result = upload_pdf(b"%PDF-1.7\ncontent", "新增报告.pdf")
    assert result["index_status"] == "pending_index"
    assert result["sha256"]
    assert get_pending_documents()[0]["filename"] == "新增报告.pdf"
    assert not list(isolated_pdf_store.glob("*.uploading"))


def test_manifest_indexed_status_sets_document_indexed_flag(isolated_pdf_store):
    uploaded = upload_pdf(b"%PDF-1.7\\nmanifest-indexed", "清单已索引.pdf")
    assert mark_pdf_indexed("清单已索引.pdf", uploaded["sha256"], "generation-1") is True

    document = get_documents()[0]

    assert document["index_status"] == "indexed"
    assert document["indexed"] is True


def test_same_pdf_upload_is_idempotent(isolated_pdf_store):
    first = upload_pdf(b"%PDF-1.7\nsame", "同一报告.pdf")
    second = upload_pdf(b"%PDF-1.7\nsame", "同一报告.pdf")
    assert first["sha256"] == second["sha256"]
    assert len(get_documents()) == 1
    manifest = json.loads(knowledge_service._MANIFEST_PATH.read_text(encoding="utf-8"))
    assert len(manifest["documents"]) == 1


def test_index_status_cannot_update_a_replaced_document(isolated_pdf_store):
    upload_pdf(b"%PDF-1.7\nold", "版本报告.pdf")
    first = mark_pdf_indexed("版本报告.pdf", "old-sha", "gen-1")
    assert first is False
    upload_pdf(b"%PDF-1.7\nnew", "版本报告.pdf")
    assert mark_pdf_indexed("版本报告.pdf", "old-sha", "gen-1") is False
    assert mark_pdf_indexed("版本报告.pdf", knowledge_service._sha256_bytes(b"%PDF-1.7\nnew"), "gen-2") is True


def test_index_failure_is_visible_and_retryable(isolated_pdf_store):
    uploaded = upload_pdf(b"%PDF-1.7\nfailure", "失败报告.pdf")
    assert mark_pdf_index_failed("失败报告.pdf", uploaded["sha256"], "解析失败") is True
    doc = get_documents()[0]
    assert doc["index_status"] == "index_failed"
    assert doc["index_error"] == "解析失败"


def test_retry_pdf_index_resets_bounded_attempts(isolated_pdf_store):
    uploaded = upload_pdf(b"%PDF-1.7\nretry", "可重试报告.pdf")
    assert mark_pdf_index_failed(
        "可重试报告.pdf", uploaded["sha256"], "暂时失败", index_attempts=3
    ) is True
    assert retry_pdf_index("可重试报告.pdf") is True
    doc = get_documents()[0]
    assert doc["index_status"] == "pending_index"
    assert doc["index_error"] is None
    assert doc["index_attempts"] == 0


def test_delete_removes_manifest_so_same_name_is_hot_loaded_again(isolated_pdf_store):
    uploaded = upload_pdf(b"%PDF-1.7\nreadd", "重新放回.pdf")
    assert mark_pdf_indexed("重新放回.pdf", uploaded["sha256"], "generation-old") is True
    assert delete_pdf("重新放回.pdf") is True
    assert get_documents() == []

    upload_pdf(b"%PDF-1.7\nreadd", "重新放回.pdf")
    document = get_documents()[0]
    assert document["index_status"] == "pending_index"
    assert document["index_generation"] is None


def test_delete_manifest_failure_restores_pdf(isolated_pdf_store, monkeypatch):
    upload_pdf(b"%PDF-1.7\nkeep-on-failure", "删除失败恢复.pdf")

    def fail_manifest(_manifest):
        raise OSError("manifest unavailable")

    monkeypatch.setattr(knowledge_service, "_write_manifest", fail_manifest)
    with pytest.raises(OSError, match="manifest unavailable"):
        delete_pdf("删除失败恢复.pdf")
    assert (isolated_pdf_store / "删除失败恢复.pdf").read_bytes() == b"%PDF-1.7\nkeep-on-failure"


def test_non_pdf_magic_is_rejected(isolated_pdf_store):
    with pytest.raises(ValueError, match="PDF 文件内容无效"):
        upload_pdf(b"not a pdf", "伪装报告.pdf")


def test_manifest_failure_restores_existing_pdf(isolated_pdf_store, monkeypatch):
    upload_pdf(b"%PDF-1.7\nold", "清单失败.pdf")

    def fail_manifest(_manifest):
        raise OSError("manifest unavailable")

    monkeypatch.setattr(knowledge_service, "_write_manifest", fail_manifest)
    with pytest.raises(OSError, match="manifest unavailable"):
        upload_pdf(b"%PDF-1.7\nnew", "清单失败.pdf")
    assert (isolated_pdf_store / "清单失败.pdf").read_bytes() == b"%PDF-1.7\nold"


def test_directory_sync_registers_new_pdf_for_hot_loading(isolated_pdf_store):
    isolated_pdf_store.mkdir(parents=True, exist_ok=True)
    (isolated_pdf_store / "目录新增.pdf").write_bytes(b"%PDF-1.7\ndropped")
    result = sync_pdf_directory()
    assert result["registered"] == ["目录新增.pdf"]
    assert get_pending_documents()[0]["filename"] == "目录新增.pdf"
    assert sync_pdf_directory()["registered"] == []


def test_directory_sync_adopts_existing_legacy_index_without_reprocessing(isolated_pdf_store):
    isolated_pdf_store.mkdir(parents=True, exist_ok=True)
    (isolated_pdf_store / "历史报告.pdf").write_bytes(b"%PDF-1.7\nlegacy")
    knowledge_service._VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    (knowledge_service._VECTOR_DB_DIR / "company_registry.json").write_text(
        '{"companies":{"示例公司":{"source_files":["历史报告.pdf"]}}}',
        encoding="utf-8",
    )
    result = sync_pdf_directory()
    assert result["registered"] == []
    assert get_documents()[0]["index_status"] == "indexed"
