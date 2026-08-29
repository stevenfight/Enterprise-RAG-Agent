"""VisualRegion 必须绑定物理页制品并使用规范化坐标。"""

import hashlib
from pathlib import Path

import fitz
import pytest


def _registered_page_artifact(tmp_path: Path):
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    pdf_path = tmp_path / "region-source.pdf"
    pdf_document = fitz.open()
    pdf_document.new_page()
    pdf_document.save(pdf_path)
    pdf_document.close()
    pdf_content = pdf_path.read_bytes()
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    document = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="region-source",
        display_name="区域来源",
        original_filename="区域来源.pdf",
        file_content=pdf_content,
        physical_page_count=1,
    )
    manifest = DocumentAssetManifestRepository(store).create_or_get(
        document_version_id=document.document_version_id,
        source_sha256=hashlib.sha256(pdf_content).hexdigest(),
        physical_page_count=1,
        asset_status="incomplete",
    )
    artifact = PageImageRenderer(tmp_path / "rendered").render(
        document.document_version_id,
        pdf_path,
        physical_page_number=1,
    )
    registered = PageArtifactRepository(store).register_page_image(
        manifest.manifest_id,
        artifact,
    )
    return store, manifest, registered


def test_visual_region_is_idempotent_and_keeps_manifest_page_identity(tmp_path: Path):
    from src.visual_region_repository import VisualRegionRepository

    store, manifest, artifact = _registered_page_artifact(tmp_path)
    repository = VisualRegionRepository(store)

    first = repository.register(
        page_artifact_id=artifact.page_artifact_id,
        x0=0.1,
        y0=0.2,
        x1=0.8,
        y1=0.9,
        region_status="complete",
    )
    second = repository.register(
        page_artifact_id=artifact.page_artifact_id,
        x0=0.1,
        y0=0.2,
        x1=0.8,
        y1=0.9,
        region_status="complete",
    )

    assert first.created is True
    assert second.created is False
    assert first.visual_region_id == second.visual_region_id
    assert first.manifest_id == manifest.manifest_id
    assert first.physical_page_number == 1


def test_visual_region_rejects_unordered_out_of_range_or_unknown_page_artifact(
    tmp_path: Path,
):
    from src.visual_region_repository import VisualRegionRepository

    store, _, artifact = _registered_page_artifact(tmp_path)
    repository = VisualRegionRepository(store)
    with pytest.raises(ValueError, match="坐标"):
        repository.register(
            page_artifact_id=artifact.page_artifact_id,
            x0=0.8,
            y0=0.2,
            x1=0.1,
            y1=0.9,
            region_status="complete",
        )
    with pytest.raises(ValueError, match="坐标"):
        repository.register(
            page_artifact_id=artifact.page_artifact_id,
            x0=-0.1,
            y0=0.2,
            x1=0.8,
            y1=0.9,
            region_status="complete",
        )
    with pytest.raises(ValueError, match="page_artifact_id"):
        repository.register(
            page_artifact_id="missing-artifact",
            x0=0.1,
            y0=0.2,
            x1=0.8,
            y1=0.9,
            region_status="complete",
        )
