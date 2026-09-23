"""M0.11 输入冲突、staging 孤儿与 blob 可见性测试。"""

import hashlib
import os
from pathlib import Path

import fitz
import pytest


def _repository(tmp_path: Path):
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    return V7DocumentRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"), tmp_path / "blobs")


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page()
    content = document.tobytes()
    document.close()
    return content


def test_database_hash_size_conflict_is_rejected_without_new_document_version(tmp_path: Path):
    from src.v7_document_repository import ContentHashConflictError

    repository = _repository(tmp_path)
    content = b"%PDF-1.7\nconsistent"
    registration = repository.register_document_version(
        logical_document_key="report", display_name="报告", original_filename="报告.pdf",
        file_content=content, physical_page_count=1,
    )
    with repository.store.connect() as connection:
        connection.execute("UPDATE v7_blobs SET size_bytes = size_bytes + 1 WHERE sha256 = ?", (registration.blob_sha256,))
        connection.commit()

    with pytest.raises(ContentHashConflictError, match="数据库大小"):
        repository.register_document_version(
            logical_document_key="another-report", display_name="另一报告", original_filename="另一报告.pdf",
            file_content=content, physical_page_count=1,
        )
    assert repository.count_document_versions() == 1


def test_document_blob_lookup_never_exposes_unregistered_orphan_blob(tmp_path: Path):
    repository = _repository(tmp_path)
    registration = repository.register_document_version(
        logical_document_key="report", display_name="报告", original_filename="报告.pdf",
        file_content=b"%PDF-1.7\nregistered", physical_page_count=1,
    )
    orphan_content = b"%PDF-1.7\norphan"
    orphan_sha256 = hashlib.sha256(orphan_content).hexdigest()
    repository.blob_root.mkdir(parents=True, exist_ok=True)
    (repository.blob_root / orphan_sha256).write_bytes(orphan_content)

    assert repository.resolve_document_blob_path(registration.document_version_id) == registration.blob_path
    with pytest.raises(ValueError, match="document_version_id"):
        repository.resolve_document_blob_path("unknown-version")
    assert orphan_sha256 != registration.blob_sha256


def test_staging_cleanup_only_removes_expired_uploading_files_and_is_idempotent(tmp_path: Path):
    from src.v7_pdf_upload_service import V7PdfUploadService

    repository = _repository(tmp_path)
    service = V7PdfUploadService(repository, tmp_path / "staging")
    service.staging_root.mkdir()
    expired = service.staging_root / "expired.uploading"
    fresh = service.staging_root / "fresh.uploading"
    expired.write_bytes(b"expired")
    fresh.write_bytes(b"fresh")
    os.utime(expired, (1, 1))
    os.utime(fresh, (95, 95))

    assert service.cleanup_expired_staging(older_than_seconds=10, now=100) == ["expired.uploading"]
    assert not expired.exists()
    assert fresh.exists()
    assert service.cleanup_expired_staging(older_than_seconds=10, now=100) == []
