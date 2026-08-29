# -*- coding: utf-8 -*-
"""v7 页图制品登记仓储。"""

import hashlib
from dataclasses import dataclass

from .page_image_renderer import PageImageArtifact
from .v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class RegisteredPageArtifact:
    """已与 manifest 绑定的页图制品。"""

    page_artifact_id: str
    manifest_id: str
    physical_page_number: int
    content_sha256: str
    created: bool


class PageArtifactRepository:
    """把页图缓存登记到唯一的 v7 DocumentAssetManifest。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def register_page_image(
        self,
        manifest_id: str,
        artifact: PageImageArtifact,
    ) -> RegisteredPageArtifact:
        """登记一张完整页图，并校验版本与物理页归属。"""
        if (
            type(artifact.physical_page_number) is not int
            or artifact.physical_page_number <= 0
        ):
            raise ValueError("物理页必须为正整数")
        if not artifact.image_path.is_file() or not artifact.thumbnail_path.is_file():
            raise ValueError("页图与缩略图必须完整存在")
        content_sha256 = hashlib.sha256(artifact.image_path.read_bytes()).hexdigest()
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                manifest = connection.execute(
                    """
                    SELECT document_version_id, physical_page_count
                    FROM v7_document_asset_manifests
                    WHERE manifest_id = ?
                    """,
                    (manifest_id,),
                ).fetchone()
                if manifest is None:
                    raise ValueError("manifest_id 不存在")
                if manifest[0] != artifact.document_version_id:
                    raise ValueError("document_version_id 与 manifest 不一致")
                if artifact.physical_page_number > int(manifest[1]):
                    raise ValueError("物理页超出 manifest 总页数")
                existing = connection.execute(
                    """
                    SELECT manifest_id, physical_page_number, content_sha256,
                           image_path, thumbnail_path
                    FROM v7_page_artifacts
                    WHERE page_artifact_id = ?
                    """,
                    (artifact.artifact_id,),
                ).fetchone()
                if existing:
                    if (
                        existing[0] != manifest_id
                        or int(existing[1]) != artifact.physical_page_number
                        or existing[2] != content_sha256
                        or existing[3] != str(artifact.image_path.resolve())
                        or existing[4] != str(artifact.thumbnail_path.resolve())
                    ):
                        raise ValueError("page_artifact_id 与既有页图证据不一致")
                    connection.commit()
                    return RegisteredPageArtifact(
                        artifact.artifact_id,
                        manifest_id,
                        artifact.physical_page_number,
                        content_sha256,
                        False,
                    )
                connection.execute(
                    """
                    INSERT INTO v7_page_artifacts(
                        page_artifact_id, manifest_id, physical_page_number,
                        artifact_kind, content_sha256, artifact_status,
                        image_path, thumbnail_path
                    ) VALUES (?, ?, ?, 'page_image', ?, 'complete', ?, ?)
                    """,
                    (
                        artifact.artifact_id,
                        manifest_id,
                        artifact.physical_page_number,
                        content_sha256,
                        str(artifact.image_path.resolve()),
                        str(artifact.thumbnail_path.resolve()),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return RegisteredPageArtifact(
            artifact.artifact_id,
            manifest_id,
            artifact.physical_page_number,
            content_sha256,
            True,
        )
