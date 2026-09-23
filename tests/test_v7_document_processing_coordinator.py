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


def test_coordinator_recovers_only_its_configured_page_artifact_root(tmp_path: Path):
    store, _, _ = _registered_document(tmp_path)
    coordinator = _coordinator(tmp_path, store)
    pending = tmp_path / "rendered" / "orphan.png.deleting"
    pending.parent.mkdir()
    pending.write_bytes(b"orphan")

    assert coordinator.recover_pending_page_file_cleanup() == (pending,)
    assert coordinator.recover_pending_page_file_cleanup() == ()


def test_coordinator_routes_real_pages_and_never_dispatches_vision_for_text_only_page(
    tmp_path: Path,
):
    """迁移编排使用真实 PDF 信号；普通文本页不进入视觉分发器。"""
    store, registration, source_pdf = _registered_document(tmp_path)
    document = fitz.open(source_pdf)
    document[0].insert_text((50, 50), "ordinary text page")
    document.save(tmp_path / "with-text.pdf")
    document.close()
    routed_pdf = tmp_path / "with-text.pdf"
    routed_content = routed_pdf.read_bytes()
    from src.v7_document_repository import V7DocumentRepository

    routed_registration = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="routed-report-2025",
        display_name="路由报告",
        original_filename="路由报告.pdf",
        file_content=routed_content,
        physical_page_count=2,
    )
    coordinator = _coordinator(tmp_path, store)
    manifest = coordinator.start(
        document_version_id=routed_registration.document_version_id,
        source_pdf_path=routed_registration.blob_path,
        source_sha256=routed_registration.blob_sha256,
        physical_page_count=2,
    )
    dispatched = []

    snapshot = coordinator.route_document_pages(
        manifest_id=manifest.manifest_id,
        document_version_id=routed_registration.document_version_id,
        source_pdf_path=routed_registration.blob_path,
        vision_dispatcher=dispatched.append,
    )

    assert [decision.page_type for decision in snapshot.decisions] == ["text", "scan"]
    assert snapshot.decisions[0].use_vision is False
    assert [decision.page_number for decision in dispatched] == [2]
