# -*- coding: utf-8 -*-
"""M1.7 页图制品受控读取测试。"""

import hashlib
import asyncio
from pathlib import Path

import fitz
import pytest


def _registered_page_artifact(tmp_path: Path):
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    pdf_path = tmp_path / "access.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf_path)
    document.close()
    pdf_content = pdf_path.read_bytes()
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    version = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="artifact-access",
        display_name="受控页图",
        original_filename="access.pdf",
        file_content=pdf_content,
        physical_page_count=1,
    )
    manifest = DocumentAssetManifestRepository(store).create_or_get(
        document_version_id=version.document_version_id,
        source_sha256=hashlib.sha256(pdf_content).hexdigest(),
        physical_page_count=1,
        asset_status="incomplete",
    )
    rendered = PageImageRenderer(tmp_path / "rendered").render(
        version.document_version_id,
        pdf_path,
        physical_page_number=1,
    )
    registered = PageArtifactRepository(store).register_page_image(
        manifest.manifest_id,
        rendered,
    )
    return store, manifest, registered, rendered


def test_page_artifact_access_resolves_only_matching_complete_registered_image(tmp_path: Path):
    from src.page_artifact_access import PageArtifactAccessService

    store, manifest, artifact, rendered = _registered_page_artifact(tmp_path)

    resolved = PageArtifactAccessService(store).resolve_image(
        manifest_id=manifest.manifest_id,
        page_artifact_id=artifact.page_artifact_id,
    )

    assert resolved == rendered.image_path.resolve()


def test_page_artifact_access_rejects_path_unknown_or_cross_manifest_id(tmp_path: Path):
    from src.page_artifact_access import PageArtifactAccessService

    store, manifest, artifact, _ = _registered_page_artifact(tmp_path)
    service = PageArtifactAccessService(store)

    with pytest.raises(ValueError, match="page_artifact_id"):
        service.resolve_image(manifest_id=manifest.manifest_id, page_artifact_id="../access.png")
    with pytest.raises(ValueError, match="不存在"):
        service.resolve_image(manifest_id=manifest.manifest_id, page_artifact_id="a" * 64)
    with pytest.raises(ValueError, match="不属于 manifest"):
        service.resolve_image(manifest_id="other-manifest", page_artifact_id=artifact.page_artifact_id)


def test_page_artifact_endpoint_is_feature_gated_and_returns_only_resolved_image(monkeypatch, tmp_path: Path):
    from fastapi import HTTPException

    from src import api_service
    from src.v7_feature_flags import V7FeatureFlags

    class AccessService:
        def resolve_image(self, *, manifest_id: str, page_artifact_id: str) -> Path:
            assert manifest_id == "manifest-1"
            assert page_artifact_id == "a" * 64
            return tmp_path / "image.png"

    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"png")
    monkeypatch.setattr(api_service, "_get_page_artifact_access_service", lambda: AccessService())
    monkeypatch.setattr(
        api_service,
        "_load_agent_config",
        lambda: {"v7_feature_flags": V7FeatureFlags()},
    )
    with pytest.raises(HTTPException, match="未启用"):
        asyncio.run(api_service.api_page_artifact_image("manifest-1", "a" * 64))

    enabled = V7FeatureFlags(
        financial_trust_enabled=True,
        durable_execution_enabled=True,
        multimodal_enabled=True,
    )
    monkeypatch.setattr(api_service, "_load_agent_config", lambda: {"v7_feature_flags": enabled})
    response = asyncio.run(api_service.api_page_artifact_image("manifest-1", "a" * 64))

    assert Path(response.path) == image_path
    assert response.media_type == "image/png"
