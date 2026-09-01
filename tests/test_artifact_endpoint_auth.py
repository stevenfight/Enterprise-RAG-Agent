# -*- coding: utf-8 -*-
"""M3.9 受认证 artifact 图像端点测试：端点级 API key、制品目录不公开挂载、版本可见性校验。

边界说明（M3.9.1）：本组测试仅证明单用户/单租户端点级 API key 保护，
不构成、也不宣称文档级多租户 ACL。
"""

import asyncio
import hashlib
from pathlib import Path

import fitz
import pytest


def _registered_page_artifact(tmp_path: Path):
    """登记一份完整页图制品（与既有页图访问测试相同的 seed 链路）。"""
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    pdf_path = tmp_path / "auth.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf_path)
    document.close()
    pdf_content = pdf_path.read_bytes()
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    version = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="artifact-auth",
        display_name="受认证页图",
        original_filename="auth.pdf",
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
    return store, manifest, registered, version


def test_artifact_endpoint_requires_api_key(monkeypatch):
    """页图端点不在认证白名单内：缺少或错误 API key 一律 401。"""
    from src import api_service

    endpoint_path = "/api/artifacts/manifests/m1/pages/" + "a" * 64 + "/image"
    # 显式钉住：端点路径不得进入免认证白名单
    assert endpoint_path not in api_service.APIAuthMiddleware.SKIP_PATHS
    assert not endpoint_path.startswith(api_service.APIAuthMiddleware.SKIP_PREFIXES)

    monkeypatch.setattr(api_service, "_api_key", "secret-key")
    called = []

    async def fake_app(scope, receive, send):
        called.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def _request(headers):
        middleware = api_service.APIAuthMiddleware(fake_app)
        status_holder = {}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]

        scope = {
            "type": "http",
            "method": "GET",
            "path": endpoint_path,
            "headers": headers,
            "query_string": b"",
        }
        await middleware(scope, receive, send)
        return status_holder.get("status")

    # 缺少 Authorization 头：401，下游不被调用
    status = asyncio.run(_request([]))
    assert status == 401
    assert called == []

    # 错误 API key：401，下游不被调用
    status = asyncio.run(_request([(b"authorization", b"Bearer wrong-key")]))
    assert status == 401
    assert called == []

    # 正确 API key：请求透传下游
    status = asyncio.run(_request([(b"authorization", b"Bearer secret-key")]))
    assert status == 200
    assert called == [True]


def test_artifact_access_rejects_version_not_visible(tmp_path: Path):
    """删除线性化后的版本不可见：deleting 版本的页图读取被拒绝。"""
    from src.page_artifact_access import PageArtifactAccessService

    store, manifest, artifact, version = _registered_page_artifact(tmp_path)
    service = PageArtifactAccessService(store)
    resolved = service.resolve_image(
        manifest_id=manifest.manifest_id,
        page_artifact_id=artifact.page_artifact_id,
    )
    assert resolved.is_file()

    with store.connect() as connection:
        cursor = connection.execute(
            "UPDATE v7_document_versions SET index_status = 'deleting' "
            "WHERE document_version_id = ?",
            (version.document_version_id,),
        )
        connection.commit()
        assert cursor.rowcount == 1

    with pytest.raises(ValueError, match="不可见"):
        service.resolve_image(
            manifest_id=manifest.manifest_id,
            page_artifact_id=artifact.page_artifact_id,
        )


def test_page_image_root_is_not_publicly_mounted():
    """页图制品目录不作为公开静态目录挂载，页图端点是受控 API 路由。"""
    from fastapi.routing import APIRoute
    from starlette.routing import Mount

    from src import api_service

    mounts = [r for r in api_service.app.routes if isinstance(r, Mount)]
    # M3.9：不挂载公开制品目录，静态挂载路径不得涉及 artifacts
    for mount in mounts:
        assert "artifacts" not in mount.path

    page_route_paths = {
        r.path for r in api_service.app.routes if isinstance(r, APIRoute)
    }
    expected = "/api/artifacts/manifests/{manifest_id}/pages/{page_artifact_id}/image"
    assert expected in page_route_paths
