# -*- coding: utf-8 -*-
"""M-T21 未发布 V7 文档制品删除测试。"""

import hashlib
from pathlib import Path

import fitz
import pytest


def _registered_visual_document(tmp_path: Path):
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer
    from src.parse_batch_repository import ParseBatchRepository
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore
    from src.visual_artifact_repository import VisualArtifactRepository
    from src.visual_region_repository import VisualRegionRepository

    pdf_path = tmp_path / "delete.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf_path)
    document.close()
    content = pdf_path.read_bytes()
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    version = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="delete-target",
        display_name="删除目标",
        original_filename="delete.pdf",
        file_content=content,
        physical_page_count=1,
    )
    manifest = DocumentAssetManifestRepository(store).create_or_get(
        document_version_id=version.document_version_id,
        source_sha256=hashlib.sha256(content).hexdigest(),
        physical_page_count=1,
        asset_status="incomplete",
    )
    page = PageArtifactRepository(store).register_page_image(
        manifest.manifest_id,
        PageImageRenderer(tmp_path / "rendered").render(
            version.document_version_id, pdf_path, physical_page_number=1,
        ),
    )
    ParseBatchRepository(store).record(
        manifest_id=manifest.manifest_id,
        batch_id="page-1",
        physical_page_start=1,
        physical_page_end=1,
        parser_name="fixture",
        parser_version="1",
        batch_status="complete",
    )
    region = VisualRegionRepository(store).register(
        page_artifact_id=page.page_artifact_id,
        x0=0.1, y0=0.2, x1=0.8, y1=0.9,
        region_status="complete",
    )
    artifacts = VisualArtifactRepository(store)
    table = artifacts.register_table(
        manifest_id=manifest.manifest_id,
        visual_region_id=region.visual_region_id,
        source_format="fixture",
        artifact_status="complete",
    )
    evidence = artifacts.register_evidence(
        manifest_id=manifest.manifest_id,
        page_artifact_id=page.page_artifact_id,
        visual_region_id=region.visual_region_id,
        table_artifact_id=table.artifact_id,
        chart_artifact_id=None,
        evidence_status="complete",
    )
    return store, version, manifest, page, region, table, evidence


def test_delete_unpublished_document_cleans_v7_visual_artifacts_and_files(tmp_path: Path):
    from src.v7_document_deletion import V7DocumentDeletionService

    store, version, manifest, page, region, table, evidence = _registered_visual_document(tmp_path)
    with store.connect() as connection:
        image_path, thumbnail_path = connection.execute(
            "SELECT image_path, thumbnail_path FROM v7_page_artifacts WHERE page_artifact_id = ?",
            (page.page_artifact_id,),
        ).fetchone()

    result = V7DocumentDeletionService(store).delete_unpublished_document_version(
        version.document_version_id
    )

    assert result.document_version_id == version.document_version_id
    assert result.manifest_id == manifest.manifest_id
    assert result.removed_page_artifact_ids == (page.page_artifact_id,)
    assert result.removed_visual_region_ids == (region.visual_region_id,)
    assert result.removed_table_artifact_ids == (table.artifact_id,)
    assert result.removed_visual_evidence_ids == (evidence.visual_evidence_id,)
    assert not Path(image_path).exists()
    assert not Path(thumbnail_path).exists()
    assert not Path(f"{image_path}.deleting").exists()
    assert not Path(f"{thumbnail_path}.deleting").exists()
    with store.connect() as connection:
        assert connection.execute("SELECT 1 FROM v7_document_versions WHERE document_version_id = ?", (version.document_version_id,)).fetchone() is None
        assert connection.execute("SELECT 1 FROM v7_document_asset_manifests WHERE manifest_id = ?", (manifest.manifest_id,)).fetchone() is None
        assert connection.execute("SELECT 1 FROM v7_page_artifacts WHERE page_artifact_id = ?", (page.page_artifact_id,)).fetchone() is None


def test_delete_unpublished_document_rejects_published_or_indexed_document(tmp_path: Path):
    from src.v7_document_deletion import V7DocumentDeletionService

    store, version, *_ = _registered_visual_document(tmp_path)
    with store.connect() as connection:
        connection.execute("INSERT INTO v7_generation_candidates(generation_id, corpus_revision, status, payload_json) VALUES ('g1', 'r1', 'ready', '{}')")
        connection.execute("INSERT INTO v7_generation_documents(generation_id, document_version_id, source_sha256) VALUES ('g1', ?, ?)", (version.document_version_id, version.blob_sha256))
        connection.commit()

    with pytest.raises(ValueError, match="索引代际"):
        V7DocumentDeletionService(store).delete_unpublished_document_version(version.document_version_id)


def test_resume_pending_page_file_cleanup_is_idempotent_and_scoped_to_root(tmp_path: Path):
    from src.v7_document_deletion import V7DocumentDeletionService

    artifact_root = tmp_path / "rendered"
    artifact_root.mkdir()
    pending = artifact_root / "page.png.deleting"
    pending.write_bytes(b"page")
    unrelated = tmp_path / "unrelated.png.deleting"
    unrelated.write_bytes(b"keep")

    assert V7DocumentDeletionService.resume_pending_page_file_cleanup(artifact_root) == (pending,)
    assert V7DocumentDeletionService.resume_pending_page_file_cleanup(artifact_root) == ()
    assert not pending.exists()
    assert unrelated.exists()
