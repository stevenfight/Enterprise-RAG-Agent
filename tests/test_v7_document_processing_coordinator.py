"""V7 文档处理协调器的版本、物理页和完整性边界。"""

from pathlib import Path

import fitz
import pytest


def _registered_document(tmp_path: Path, page_count: int = 2):
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    source_pdf = tmp_path / "source.pdf"
    document = fitz.open()
    for _ in range(page_count):
        document.new_page()
    document.save(source_pdf)
    document.close()
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    repository = V7DocumentRepository(store, tmp_path / "blobs")
    registration = repository.register_document_version(
        logical_document_key="issuer-report-2025",
        display_name="公司报告",
        original_filename="公司报告.pdf",
        file_content=source_pdf.read_bytes(),
        physical_page_count=page_count,
    )
    return store, registration, source_pdf


def _coordinator(tmp_path: Path, store):
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer
    from src.parse_batch_repository import ParseBatchRepository
    from src.v7_document_processing_coordinator import V7DocumentProcessingCoordinator

    return V7DocumentProcessingCoordinator(
        manifest_repository=DocumentAssetManifestRepository(store),
        parse_batch_repository=ParseBatchRepository(store),
        page_image_renderer=PageImageRenderer(tmp_path / "rendered"),
        page_artifact_repository=PageArtifactRepository(store),
    )


def test_coordinator_processes_registered_blob_by_physical_pages(tmp_path: Path):
    store, registration, _ = _registered_document(tmp_path)
    coordinator = _coordinator(tmp_path, store)

    manifest = coordinator.start(
        document_version_id=registration.document_version_id,
        source_pdf_path=registration.blob_path,
        source_sha256=registration.blob_sha256,
        physical_page_count=2,
    )
    coordinator.record_parse_batch(
        manifest_id=manifest.manifest_id,
        batch_id="pages-1-2",
        physical_page_start=1,
        physical_page_end=2,
        parser_name="mineru",
        parser_version="v4",
        batch_status="complete",
    )
    page_artifacts = coordinator.render_all_page_images(
        manifest_id=manifest.manifest_id,
        document_version_id=registration.document_version_id,
        source_pdf_path=registration.blob_path,
    )
    completed = coordinator.finalize(manifest.manifest_id)

    assert [artifact.physical_page_number for artifact in page_artifacts] == [1, 2]
    assert completed.complete is True
    assert completed.missing_physical_pages == ()
    assert completed.missing_parse_physical_pages == ()


def test_coordinator_rejects_source_sha_or_page_count_that_do_not_match_version(
    tmp_path: Path,
):
    store, registration, source_pdf = _registered_document(tmp_path)
    coordinator = _coordinator(tmp_path, store)

    with pytest.raises(ValueError, match="source_sha256"):
        coordinator.start(
            document_version_id=registration.document_version_id,
            source_pdf_path=registration.blob_path,
            source_sha256="0" * 64,
            physical_page_count=2,
        )
    with pytest.raises(ValueError, match="physical_page_count"):
        coordinator.start(
            document_version_id=registration.document_version_id,
            source_pdf_path=registration.blob_path,
            source_sha256=registration.blob_sha256,
            physical_page_count=1,
        )

    manifest = coordinator.start(
        document_version_id=registration.document_version_id,
        source_pdf_path=registration.blob_path,
        source_sha256=registration.blob_sha256,
        physical_page_count=2,
    )
    source_pdf.write_bytes(b"%PDF-1.7\nchanged")
    with pytest.raises(ValueError, match="source_pdf_path"):
        coordinator.render_all_page_images(
            manifest_id=manifest.manifest_id,
            document_version_id=registration.document_version_id,
            source_pdf_path=source_pdf,
        )
