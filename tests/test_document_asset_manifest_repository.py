"""v7 DocumentAssetManifest 持久化的确定性测试。"""

from pathlib import Path


def _document_version_id(tmp_path: Path) -> tuple[object, str]:
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    repository = V7DocumentRepository(
        V7MetadataStore(tmp_path / "metadata.sqlite3"),
        tmp_path / "blobs",
    )
    registration = repository.register_document_version(
        logical_document_key="report-2024",
        display_name="报告",
        original_filename="报告.pdf",
        file_content=b"%PDF-1.7\nsource",
        physical_page_count=3,
    )
    return repository.store, registration.document_version_id


def test_manifest_persists_incomplete_asset_state_and_is_idempotent(tmp_path: Path):
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository

    store, document_version_id = _document_version_id(tmp_path)
    repository = DocumentAssetManifestRepository(store)

    first = repository.create_or_get(
        document_version_id=document_version_id,
        source_sha256="a" * 64,
        physical_page_count=3,
        asset_status="incomplete",
    )
    second = repository.create_or_get(
        document_version_id=document_version_id,
        source_sha256="a" * 64,
        physical_page_count=3,
        asset_status="incomplete",
    )

    assert first.created is True
    assert second.created is False
    assert second.manifest_id == first.manifest_id
    assert repository.get(first.manifest_id).asset_status == "incomplete"


def test_manifest_rejects_invalid_status_and_page_count(tmp_path: Path):
    import pytest

    from src.document_asset_manifest_repository import DocumentAssetManifestRepository

    store, document_version_id = _document_version_id(tmp_path)
    repository = DocumentAssetManifestRepository(store)
    with pytest.raises(ValueError, match="asset_status"):
        repository.create_or_get(
            document_version_id=document_version_id,
            source_sha256="a" * 64,
            physical_page_count=3,
            asset_status="unknown",
        )
    with pytest.raises(ValueError, match="physical_page_count"):
        repository.create_or_get(
            document_version_id=document_version_id,
            source_sha256="a" * 64,
            physical_page_count=0,
            asset_status="incomplete",
        )


def test_manifest_does_not_silently_accept_conflicting_evidence(tmp_path: Path):
    import pytest

    from src.document_asset_manifest_repository import DocumentAssetManifestRepository

    store, document_version_id = _document_version_id(tmp_path)
    repository = DocumentAssetManifestRepository(store)
    repository.create_or_get(
        document_version_id=document_version_id,
        source_sha256="a" * 64,
        physical_page_count=3,
        asset_status="incomplete",
    )

    with pytest.raises(ValueError, match="source_sha256"):
        repository.create_or_get(
            document_version_id=document_version_id,
            source_sha256="b" * 64,
            physical_page_count=3,
            asset_status="incomplete",
        )
    with pytest.raises(ValueError, match="asset_status"):
        repository.create_or_get(
            document_version_id=document_version_id,
            source_sha256="a" * 64,
            physical_page_count=3,
            asset_status="complete",
        )


def _page_manifest(tmp_path: Path):
    import hashlib

    import fitz

    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    pdf_path = tmp_path / "pages.pdf"
    pdf_document = fitz.open()
    pdf_document.new_page()
    pdf_document.new_page()
    pdf_document.save(pdf_path)
    pdf_document.close()
    pdf_bytes = pdf_path.read_bytes()
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    document = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="pages-report",
        display_name="页图报告",
        original_filename="页图报告.pdf",
        file_content=pdf_bytes,
        physical_page_count=2,
    )
    repository = DocumentAssetManifestRepository(store)
    manifest = repository.create_or_get(
        document_version_id=document.document_version_id,
        source_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        physical_page_count=2,
        asset_status="incomplete",
    )
    return repository, store, manifest, document, pdf_path


def test_manifest_marks_complete_only_when_every_physical_page_has_intact_images(
    tmp_path: Path,
):
    from src.parse_batch_repository import ParseBatchRepository
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer

    repository, store, manifest, document, pdf_path = _page_manifest(tmp_path)
    renderer = PageImageRenderer(tmp_path / "rendered")
    page_repository = PageArtifactRepository(store)
    for physical_page_number in (1, 2):
        artifact = renderer.render(
            document.document_version_id,
            pdf_path,
            physical_page_number=physical_page_number,
        )
        page_repository.register_page_image(manifest.manifest_id, artifact)
    ParseBatchRepository(store).record(
        manifest_id=manifest.manifest_id,
        batch_id="pages-1-2",
        physical_page_start=1,
        physical_page_end=2,
        parser_name="mineru",
        parser_version="v4",
        batch_status="complete",
    )

    result = repository.verify_page_image_completeness(manifest.manifest_id)

    assert result.complete is True
    assert result.missing_physical_pages == ()
    assert result.invalid_physical_pages == ()
    assert repository.get(manifest.manifest_id).asset_status == "complete"


def test_manifest_keeps_incomplete_when_physical_page_is_missing_or_file_is_deleted(
    tmp_path: Path,
):
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer

    repository, store, manifest, document, pdf_path = _page_manifest(tmp_path)
    artifact = PageImageRenderer(tmp_path / "rendered").render(
        document.document_version_id,
        pdf_path,
        physical_page_number=1,
    )
    PageArtifactRepository(store).register_page_image(manifest.manifest_id, artifact)
    artifact.thumbnail_path.unlink()

    result = repository.verify_page_image_completeness(manifest.manifest_id)

    assert result.complete is False
    assert result.missing_physical_pages == (2,)
    assert result.invalid_physical_pages == (1,)
    assert repository.get(manifest.manifest_id).asset_status == "incomplete"


def test_manifest_requires_complete_parse_batch_coverage_before_complete(tmp_path: Path):
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer

    repository, store, manifest, document, pdf_path = _page_manifest(tmp_path)
    renderer = PageImageRenderer(tmp_path / "rendered")
    page_repository = PageArtifactRepository(store)
    for physical_page_number in (1, 2):
        artifact = renderer.render(
            document.document_version_id,
            pdf_path,
            physical_page_number=physical_page_number,
        )
        page_repository.register_page_image(manifest.manifest_id, artifact)

    result = repository.verify_page_image_completeness(manifest.manifest_id)

    assert result.complete is False
    assert result.missing_parse_physical_pages == (1, 2)
    assert repository.get(manifest.manifest_id).asset_status == "incomplete"
