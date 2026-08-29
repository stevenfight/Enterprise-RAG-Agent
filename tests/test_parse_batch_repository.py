"""解析批次必须以 PDF 物理页段为边界持久化。"""

from pathlib import Path

import pytest


def _manifest(tmp_path: Path):
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    document = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="batch-report",
        display_name="批次报告",
        original_filename="批次报告.pdf",
        file_content=b"%PDF-1.7\nbatch-source",
        physical_page_count=5,
    )
    manifest = DocumentAssetManifestRepository(store).create_or_get(
        document_version_id=document.document_version_id,
        source_sha256=document.blob_sha256,
        physical_page_count=5,
        asset_status="incomplete",
    )
    return store, manifest


def test_parse_batches_keep_physical_ranges_and_report_failed_pages(tmp_path: Path):
    from src.parse_batch_repository import ParseBatchRepository

    store, manifest = _manifest(tmp_path)
    repository = ParseBatchRepository(store)
    first = repository.record(
        manifest_id=manifest.manifest_id,
        batch_id="pages-1-3",
        physical_page_start=1,
        physical_page_end=3,
        parser_name="mineru",
        parser_version="v4",
        batch_status="complete",
    )
    second = repository.record(
        manifest_id=manifest.manifest_id,
        batch_id="pages-4-5",
        physical_page_start=4,
        physical_page_end=5,
        parser_name="mineru",
        parser_version="v4",
        batch_status="failed",
        error_code="remote_timeout",
    )

    coverage = repository.summarize(manifest.manifest_id)

    assert first.created is True
    assert second.created is True
    assert coverage.complete is False
    assert coverage.missing_physical_pages == ()
    assert coverage.failed_physical_pages == (4, 5)


def test_parse_batches_are_idempotent_and_reject_overlapping_or_out_of_range_pages(
    tmp_path: Path,
):
    from src.parse_batch_repository import ParseBatchRepository

    store, manifest = _manifest(tmp_path)
    repository = ParseBatchRepository(store)
    first = repository.record(
        manifest_id=manifest.manifest_id,
        batch_id="pages-1-3",
        physical_page_start=1,
        physical_page_end=3,
        parser_name="mineru",
        parser_version="v4",
        batch_status="complete",
    )
    repeated = repository.record(
        manifest_id=manifest.manifest_id,
        batch_id="pages-1-3",
        physical_page_start=1,
        physical_page_end=3,
        parser_name="mineru",
        parser_version="v4",
        batch_status="complete",
    )

    assert first.created is True
    assert repeated.created is False
    with pytest.raises(ValueError, match="重叠"):
        repository.record(
            manifest_id=manifest.manifest_id,
            batch_id="pages-3-5",
            physical_page_start=3,
            physical_page_end=5,
            parser_name="mineru",
            parser_version="v4",
            batch_status="complete",
        )
    with pytest.raises(ValueError, match="物理页段"):
        repository.record(
            manifest_id=manifest.manifest_id,
            batch_id="pages-6-6",
            physical_page_start=6,
            physical_page_end=6,
            parser_name="mineru",
            parser_version="v4",
            batch_status="complete",
        )
