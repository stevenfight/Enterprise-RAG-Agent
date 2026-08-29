"""PageArtifact 与 DocumentAssetManifest 关联的确定性测试。"""

import hashlib
from pathlib import Path

import fitz
import pytest


def _pdf_file(path: Path) -> bytes:
    document = fitz.open()
    document.new_page()
    document.new_page()
    document.save(path)
    document.close()
    return path.read_bytes()


def _manifest(tmp_path: Path):
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    pdf_path = tmp_path / "report.pdf"
    pdf_bytes = _pdf_file(pdf_path)
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    document = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="report",
        display_name="报告",
        original_filename="报告.pdf",
        file_content=pdf_bytes,
        physical_page_count=2,
    )
    manifest = DocumentAssetManifestRepository(store).create_or_get(
        document_version_id=document.document_version_id,
        source_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        physical_page_count=2,
        asset_status="incomplete",
    )
    return store, manifest, document, pdf_path


def test_page_artifact_registration_links_cached_image_to_matching_manifest(tmp_path: Path):
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer

    store, manifest, document, pdf_path = _manifest(tmp_path)
    rendered = PageImageRenderer(tmp_path / "rendered").render(
        document.document_version_id,
        pdf_path,
        physical_page_number=2,
    )
    repository = PageArtifactRepository(store)

    first = repository.register_page_image(manifest.manifest_id, rendered)
    second = repository.register_page_image(manifest.manifest_id, rendered)

    assert first.created is True
    assert second.created is False
    assert first.page_artifact_id == rendered.artifact_id
    assert first.physical_page_number == 2


def test_page_artifact_rejects_cross_document_or_out_of_manifest_page(tmp_path: Path):
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageArtifact, PageImageRenderer

    store, manifest, document, pdf_path = _manifest(tmp_path)
    rendered = PageImageRenderer(tmp_path / "rendered").render(
        document.document_version_id,
        pdf_path,
        physical_page_number=1,
    )
    repository = PageArtifactRepository(store)
    cross_document = PageImageArtifact(
        artifact_id=rendered.artifact_id,
        document_version_id="other-version",
        physical_page_number=1,
        image_path=rendered.image_path,
        thumbnail_path=rendered.thumbnail_path,
        created=False,
    )
    with pytest.raises(ValueError, match="document_version_id"):
        repository.register_page_image(manifest.manifest_id, cross_document)
    out_of_range = PageImageArtifact(
        artifact_id="out-of-range",
        document_version_id=document.document_version_id,
        physical_page_number=3,
        image_path=rendered.image_path,
        thumbnail_path=rendered.thumbnail_path,
        created=False,
    )
    with pytest.raises(ValueError, match="物理页"):
        repository.register_page_image(manifest.manifest_id, out_of_range)
    zero_page = PageImageArtifact(
        artifact_id="zero-page",
        document_version_id=document.document_version_id,
        physical_page_number=0,
        image_path=rendered.image_path,
        thumbnail_path=rendered.thumbnail_path,
        created=False,
    )
    with pytest.raises(ValueError, match="物理页"):
        repository.register_page_image(manifest.manifest_id, zero_page)
