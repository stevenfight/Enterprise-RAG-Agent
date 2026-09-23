# -*- coding: utf-8 -*-
"""M3.6 delete_pdf 与 V7 删除协调器集成测试。"""

import pytest

import src.knowledge_service as knowledge_service
from src.knowledge_service import delete_pdf, upload_pdf


@pytest.fixture
def isolated_pdf_store(tmp_path, monkeypatch):
    pdf_dir = tmp_path / "pdf_reports"
    monkeypatch.setattr(knowledge_service, "_PDF_DIR", pdf_dir)
    monkeypatch.setattr(knowledge_service, "_MANIFEST_PATH", tmp_path / "manifest.json")
    return pdf_dir


def _seed_v7_versions(tmp_path, original_filename):
    """按同一原始文件名登记两个不同内容的 V7 文档版本并依次激活。"""
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    document_repository = V7DocumentRepository(store, tmp_path / "blobs")
    version_ids = []
    for content in (b"%PDF-1.7\nfirst", b"%PDF-1.7\nsecond"):
        version = document_repository.register_document_version(
            logical_document_key="annual-report",
            display_name="年度报告",
            original_filename=original_filename,
            file_content=content,
            physical_page_count=1,
        )
        document_repository.promote_document_version_to_active(version.document_version_id)
        version_ids.append(version.document_version_id)
    return store, version_ids


def test_delete_pdf_creates_deletion_requests_for_all_versions_of_filename(tmp_path, isolated_pdf_store):
    """删除 PDF 时为同名全部未删除 V7 版本创建删除请求并完成 legacy 清理。"""
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator

    store, version_ids = _seed_v7_versions(tmp_path, "年度报告.pdf")
    upload_pdf(b"%PDF-1.7\nlegacy-file", "年度报告.pdf")
    coordinator = V7DocumentDeletionCoordinator(store)

    result = delete_pdf("年度报告.pdf", deletion_coordinator=coordinator)

    assert result is True
    assert not (isolated_pdf_store / "年度报告.pdf").exists()
    with store.connect() as connection:
        requests = connection.execute(
            "SELECT document_version_id, status FROM v7_document_deletion_requests"
        ).fetchall()
        statuses = [row[0] for row in connection.execute(
            "SELECT index_status FROM v7_document_versions"
        ).fetchall()]
    assert sorted(row[0] for row in requests) == sorted(version_ids)
    # 无活动租约且无 active publication：请求状态为 rebuild_required
    assert all(row[1] == "rebuild_required" for row in requests)
    # 全部版本已线性化为 deleting
    assert all(status == "deleting" for status in statuses)


def test_delete_pdf_without_coordinator_keeps_v7_tables_untouched(tmp_path, isolated_pdf_store):
    """不注入协调器时删除行为与现状完全一致，不触碰 V7 表。"""
    store, version_ids = _seed_v7_versions(tmp_path, "年度报告.pdf")
    upload_pdf(b"%PDF-1.7\nlegacy-file", "年度报告.pdf")

    result = delete_pdf("年度报告.pdf")

    assert result is True
    with store.connect() as connection:
        request_count = connection.execute(
            "SELECT COUNT(*) FROM v7_document_deletion_requests"
        ).fetchone()[0]
        statuses = [row[0] for row in connection.execute(
            "SELECT index_status FROM v7_document_versions"
        ).fetchall()]
    assert request_count == 0
    assert "deleting" not in statuses


def test_delete_pdf_with_coordinator_without_matching_versions_still_cleans_legacy(tmp_path, isolated_pdf_store):
    """协调器存在但无同名 V7 版本时，legacy 清理照常且不创建删除请求。"""
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator

    store, version_ids = _seed_v7_versions(tmp_path, "其他文件.pdf")
    upload_pdf(b"%PDF-1.7\nlegacy-file", "年度报告.pdf")
    coordinator = V7DocumentDeletionCoordinator(store)

    result = delete_pdf("年度报告.pdf", deletion_coordinator=coordinator)

    assert result is True
    with store.connect() as connection:
        request_count = connection.execute(
            "SELECT COUNT(*) FROM v7_document_deletion_requests"
        ).fetchone()[0]
    assert request_count == 0


def test_deletion_requests_by_filename_skip_already_deleting_versions(tmp_path):
    """已处于 deleting 的版本被幂等跳过，不重复创建删除请求。"""
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator

    store, version_ids = _seed_v7_versions(tmp_path, "年度报告.pdf")
    coordinator = V7DocumentDeletionCoordinator(store)

    first = coordinator.request_deletion_by_original_filename("年度报告.pdf")
    second = coordinator.request_deletion_by_original_filename("年度报告.pdf")

    assert [r.document_version_id for r in first] == sorted(version_ids)
    assert second == []
    with store.connect() as connection:
        request_count = connection.execute(
            "SELECT COUNT(*) FROM v7_document_deletion_requests"
        ).fetchone()[0]
    assert request_count == len(version_ids)
