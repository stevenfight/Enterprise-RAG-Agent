# -*- coding: utf-8 -*-
"""按已登记制品 ID 受控解析页图，不接受调用方提供的文件路径。"""

import re
from pathlib import Path

from .v7_metadata_store import V7MetadataStore


class PageArtifactAccessService:
    """读取完整页图前验证 manifest、制品身份与磁盘文件。"""

    _SAFE_MANIFEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
    _SAFE_PAGE_ARTIFACT_ID = re.compile(r"^[0-9a-f]{64}$")

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def resolve_image(self, *, manifest_id: str, page_artifact_id: str) -> Path:
        """返回同一 manifest 下完整页图的已登记绝对路径。"""
        if not isinstance(manifest_id, str) or not self._SAFE_MANIFEST_ID.fullmatch(manifest_id):
            raise ValueError("manifest_id 不合法")
        if (
            not isinstance(page_artifact_id, str)
            or not self._SAFE_PAGE_ARTIFACT_ID.fullmatch(page_artifact_id)
        ):
            raise ValueError("page_artifact_id 不合法")
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                """SELECT p.manifest_id, p.artifact_status, p.image_path, d.index_status
                FROM v7_page_artifacts p
                JOIN v7_document_asset_manifests m ON m.manifest_id = p.manifest_id
                LEFT JOIN v7_document_versions d
                    ON d.document_version_id = m.document_version_id
                WHERE p.page_artifact_id = ? AND p.artifact_kind = 'page_image'""",
                (page_artifact_id,),
            ).fetchone()
        if row is None:
            raise ValueError("页图制品不存在")
        if row[0] != manifest_id:
            raise ValueError("页图制品不属于 manifest")
        if row[1] != "complete" or not isinstance(row[2], str):
            raise ValueError("页图制品未完成")
        # M3.9：关联 document version 当前可见才允许读取；
        # deleting 版本或版本行缺失（fail-closed）一律拒绝
        if row[3] is None or row[3] == "deleting":
            raise ValueError("文档版本不可见")
        image_path = Path(row[2]).resolve()
        if not image_path.is_file() or image_path.suffix.lower() != ".png":
            raise ValueError("页图文件不可用")
        return image_path
