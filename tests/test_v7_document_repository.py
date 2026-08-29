"""v7 文档版本与内容寻址 blob 的确定性测试。"""

from pathlib import Path


def _repository(tmp_path: Path):
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "v7_metadata.sqlite3")
    return V7DocumentRepository(store, tmp_path / "blobs")


def test_same_logical_document_and_hash_is_idempotent(tmp_path: Path):
    repository = _repository(tmp_path)

    first = repository.register_document_version(
        logical_document_key="annual-report-2024",
        display_name="年度报告",
        original_filename="年度报告.pdf",
        file_content=b"%PDF-1.7\ncontent",
        physical_page_count=2,
    )
    second = repository.register_document_version(
        logical_document_key="annual-report-2024",
        display_name="年度报告",
        original_filename="年度报告.pdf",
        file_content=b"%PDF-1.7\ncontent",
        physical_page_count=2,
    )

    assert first.created is True
    assert second.created is False
    assert second.document_version_id == first.document_version_id
    assert repository.count_document_versions() == 1
    assert repository.count_blobs() == 1


def test_same_blob_can_back_two_distinct_logical_documents(tmp_path: Path):
    repository = _repository(tmp_path)

    first = repository.register_document_version(
        logical_document_key="company-a-report",
        display_name="公司 A 报告",
        original_filename="company-a.pdf",
        file_content=b"%PDF-1.7\nshared",
        physical_page_count=1,
    )
    second = repository.register_document_version(
        logical_document_key="company-b-report",
        display_name="公司 B 报告",
        original_filename="company-b.pdf",
        file_content=b"%PDF-1.7\nshared",
        physical_page_count=1,
    )

    assert first.logical_document_id != second.logical_document_id
    assert first.document_version_id != second.document_version_id
    assert first.blob_sha256 == second.blob_sha256
    assert repository.count_document_versions() == 2
    assert repository.count_blobs() == 1
    assert (tmp_path / "blobs" / first.blob_sha256).read_bytes() == b"%PDF-1.7\nshared"


def test_blob_path_is_hash_addressed_and_does_not_use_original_filename(tmp_path: Path):
    repository = _repository(tmp_path)

    registration = repository.register_document_version(
        logical_document_key="safe-name",
        display_name="安全显示名",
        original_filename="safe-display.pdf",
        file_content=b"%PDF-1.7\ncontent",
        physical_page_count=1,
    )

    assert registration.blob_path.name == registration.blob_sha256
    assert registration.blob_path.parent == tmp_path / "blobs"
    assert not (tmp_path / "blobs" / "safe-display.pdf").exists()


def test_document_repository_rejects_unsafe_windows_display_filenames(tmp_path: Path):
    import pytest

    repository = _repository(tmp_path)
    for filename in ("..\\report.pdf", "CON.pdf", "report\x00.pdf"):
        with pytest.raises(ValueError, match="original_filename"):
            repository.register_document_version(
                logical_document_key=f"key-{len(filename)}",
                display_name="报告",
                original_filename=filename,
                file_content=b"%PDF-1.7\ncontent",
                physical_page_count=1,
            )
