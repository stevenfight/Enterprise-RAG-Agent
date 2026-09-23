"""M1.3 表格、图表和视觉证据的事务关联测试。"""

from pathlib import Path

import pytest


def _manifest_with_region(tmp_path: Path, suffix: str):
    import fitz
    import hashlib

    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore
    from src.visual_region_repository import VisualRegionRepository

    pdf_path = tmp_path / f"{suffix}.pdf"
    pdf_document = fitz.open()
    pdf_document.new_page()
    pdf_document.save(pdf_path)
    pdf_document.close()
    pdf_bytes = pdf_path.read_bytes()
    store = V7MetadataStore(tmp_path / f"{suffix}.sqlite3")
    document = V7DocumentRepository(store, tmp_path / f"blobs-{suffix}").register_document_version(
        logical_document_key=f"document-{suffix}",
        display_name=f"文档{suffix}",
        original_filename=pdf_path.name,
        file_content=pdf_bytes,
        physical_page_count=1,
    )
    manifest = DocumentAssetManifestRepository(store).create_or_get(
        document_version_id=document.document_version_id,
        source_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        physical_page_count=1,
        asset_status="incomplete",
    )
    page_artifact = PageArtifactRepository(store).register_page_image(
        manifest.manifest_id,
        PageImageRenderer(tmp_path / f"rendered-{suffix}").render(
            document.document_version_id,
            pdf_path,
            physical_page_number=1,
        ),
    )
    region = VisualRegionRepository(store).register(
        page_artifact_id=page_artifact.page_artifact_id,
        x0=0.1,
        y0=0.1,
        x1=0.9,
        y1=0.9,
        region_status="complete",
    )
    return store, manifest, page_artifact, region


def test_table_chart_and_evidence_are_bound_to_one_manifest(tmp_path: Path):
    from src.visual_artifact_repository import VisualArtifactRepository

    store, manifest, page_artifact, region = _manifest_with_region(tmp_path, "one")
    repository = VisualArtifactRepository(store)

    table = repository.register_table(
        manifest_id=manifest.manifest_id,
        visual_region_id=region.visual_region_id,
        source_format="html",
        artifact_status="complete",
    )
    chart = repository.register_chart(
        manifest_id=manifest.manifest_id,
        visual_region_id=region.visual_region_id,
        artifact_status="pending",
    )
    evidence = repository.register_evidence(
        manifest_id=manifest.manifest_id,
        page_artifact_id=page_artifact.page_artifact_id,
        visual_region_id=region.visual_region_id,
        table_artifact_id=table.artifact_id,
        chart_artifact_id=chart.artifact_id,
        evidence_status="incomplete",
    )

    assert table.created is True
    assert chart.created is True
    assert evidence.manifest_id == manifest.manifest_id
    assert evidence.table_artifact_id == table.artifact_id
    assert evidence.chart_artifact_id == chart.artifact_id
    with store.connect() as connection:
        schema_versions = connection.execute(
            """SELECT
                (SELECT schema_version FROM v7_document_asset_manifests WHERE manifest_id = ?),
                (SELECT schema_version FROM v7_page_artifacts WHERE page_artifact_id = ?),
                (SELECT schema_version FROM v7_visual_regions WHERE visual_region_id = ?),
                (SELECT schema_version FROM v7_table_artifacts WHERE table_artifact_id = ?),
                (SELECT schema_version FROM v7_chart_artifacts WHERE chart_artifact_id = ?),
                (SELECT schema_version FROM v7_visual_evidence WHERE visual_evidence_id = ?)""",
            (
                manifest.manifest_id,
                page_artifact.page_artifact_id,
                region.visual_region_id,
                table.artifact_id,
                chart.artifact_id,
                evidence.visual_evidence_id,
            ),
        ).fetchone()
    assert schema_versions == (1, 1, 1, 1, 1, 1)


def test_visual_evidence_rejects_region_or_artifact_from_another_manifest(tmp_path: Path):
    from src.visual_artifact_repository import VisualArtifactRepository

    store, manifest, page_artifact, region = _manifest_with_region(tmp_path, "one")
    _, other_manifest, other_page_artifact, other_region = _manifest_with_region(tmp_path, "two")
    repository = VisualArtifactRepository(store)

    with pytest.raises(ValueError, match="不属于 manifest"):
        repository.register_table(
            manifest_id=manifest.manifest_id,
            visual_region_id=other_region.visual_region_id,
            source_format="html",
            artifact_status="complete",
        )
    with pytest.raises(ValueError, match="不属于 manifest"):
        repository.register_evidence(
            manifest_id=manifest.manifest_id,
            page_artifact_id=other_page_artifact.page_artifact_id,
            visual_region_id=region.visual_region_id,
            table_artifact_id=None,
            chart_artifact_id=None,
            evidence_status="complete",
        )

    assert other_manifest.manifest_id != manifest.manifest_id


def test_visual_artifact_status_transition_is_audited_and_complete_cannot_regress(tmp_path: Path):
    from src.visual_artifact_repository import VisualArtifactRepository

    store, manifest, page_artifact, region = _manifest_with_region(tmp_path, "s")
    repository = VisualArtifactRepository(store)
    table = repository.register_table(
        manifest_id=manifest.manifest_id,
        visual_region_id=region.visual_region_id,
        source_format="html",
        artifact_status="pending",
    )
    chart = repository.register_chart(
        manifest_id=manifest.manifest_id,
        visual_region_id=region.visual_region_id,
        artifact_status="pending",
    )
    evidence = repository.register_evidence(
        manifest_id=manifest.manifest_id,
        page_artifact_id=page_artifact.page_artifact_id,
        visual_region_id=region.visual_region_id,
        table_artifact_id=table.artifact_id,
        chart_artifact_id=None,
        evidence_status="pending",
    )

    assert repository.transition_table_status(table.artifact_id, "complete") == "complete"
    assert repository.transition_chart_status(chart.artifact_id, "incomplete") == "incomplete"
    assert repository.transition_evidence_status(evidence.visual_evidence_id, "incomplete") == "incomplete"
    assert repository.transition_evidence_status(evidence.visual_evidence_id, "complete") == "complete"
    assert repository.list_status_events(table.artifact_id) == [("pending", "complete")]
    assert repository.list_status_events(chart.artifact_id) == [("pending", "incomplete")]
    assert repository.list_status_events(evidence.visual_evidence_id) == [
        ("pending", "incomplete"),
        ("incomplete", "complete"),
    ]
    with pytest.raises(ValueError, match="不允许"):
        repository.transition_table_status(table.artifact_id, "incomplete")
