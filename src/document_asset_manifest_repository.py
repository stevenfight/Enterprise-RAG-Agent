# -*- coding: utf-8 -*-
"""v7 DocumentAssetManifest 仓储。"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from .v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class DocumentAssetManifest:
    """已持久化的文档制品清单。"""

    manifest_id: str
    document_version_id: str
    source_sha256: str
    physical_page_count: int
    asset_status: str
    created: bool


@dataclass(frozen=True)
class ManifestPageImageCompleteness:
    """按 PDF 物理页核验页图和缩略图后的清单状态。"""

    manifest_id: str
    complete: bool
    missing_physical_pages: tuple[int, ...]
    invalid_physical_pages: tuple[int, ...]
    missing_parse_physical_pages: tuple[int, ...]
    failed_parse_physical_pages: tuple[int, ...]
    unresolved_parse_physical_pages: tuple[int, ...]


class DocumentAssetManifestRepository:
    """使用 v7 SQLite 事务维护文档制品清单。"""

    _ALLOWED_ASSET_STATUSES = {"pending", "incomplete", "complete"}

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def create_or_get(
        self,
        *,
        document_version_id: str,
        source_sha256: str,
        physical_page_count: int,
        asset_status: str,
    ) -> DocumentAssetManifest:
        """为一个文档版本创建唯一制品清单，并校验物理页数一致。"""
        self._validate_input(source_sha256, physical_page_count, asset_status)
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                version_row = connection.execute(
                    """
                    SELECT physical_page_count FROM v7_document_versions
                    WHERE document_version_id = ?
                    """,
                    (document_version_id,),
                ).fetchone()
                if version_row is None:
                    raise ValueError("document_version_id 不存在")
                if int(version_row[0]) != physical_page_count:
                    raise ValueError("physical_page_count 必须与 document version 一致")
                existing = connection.execute(
                    """
                    SELECT manifest_id, source_sha256, physical_page_count, asset_status
                    FROM v7_document_asset_manifests
                    WHERE document_version_id = ?
                    """,
                    (document_version_id,),
                ).fetchone()
                if existing:
                    if existing[1] != source_sha256:
                        raise ValueError("source_sha256 与既有 manifest 不一致")
                    if int(existing[2]) != physical_page_count:
                        raise ValueError("physical_page_count 与既有 manifest 不一致")
                    if existing[3] != asset_status:
                        raise ValueError("asset_status 与既有 manifest 不一致")
                    connection.commit()
                    return DocumentAssetManifest(
                        manifest_id=existing[0],
                        document_version_id=document_version_id,
                        source_sha256=existing[1],
                        physical_page_count=int(existing[2]),
                        asset_status=existing[3],
                        created=False,
                    )
                manifest_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO v7_document_asset_manifests(
                        manifest_id, document_version_id, source_sha256,
                        physical_page_count, asset_status, schema_version
                    ) VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (
                        manifest_id,
                        document_version_id,
                        source_sha256,
                        physical_page_count,
                        asset_status,
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return DocumentAssetManifest(
            manifest_id=manifest_id,
            document_version_id=document_version_id,
            source_sha256=source_sha256,
            physical_page_count=physical_page_count,
            asset_status=asset_status,
            created=True,
        )

    def get(self, manifest_id: str) -> DocumentAssetManifest | None:
        """按 ID 读取清单；不存在时返回 None。"""
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT manifest_id, document_version_id, source_sha256,
                       physical_page_count, asset_status
                FROM v7_document_asset_manifests
                WHERE manifest_id = ?
                """,
                (manifest_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentAssetManifest(
            manifest_id=row[0],
            document_version_id=row[1],
            source_sha256=row[2],
            physical_page_count=int(row[3]),
            asset_status=row[4],
            created=False,
        )

    def verify_page_image_completeness(
        self,
        manifest_id: str,
    ) -> ManifestPageImageCompleteness:
        """核验页图和解析物理页覆盖，只有两类证据完整时才标记 complete。"""
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                manifest = connection.execute(
                    """
                    SELECT physical_page_count, asset_status
                    FROM v7_document_asset_manifests
                    WHERE manifest_id = ?
                    """,
                    (manifest_id,),
                ).fetchone()
                if manifest is None:
                    raise ValueError("manifest_id 不存在")
                physical_page_count = int(manifest[0])
                artifacts = connection.execute(
                    """
                    SELECT physical_page_number, image_path, thumbnail_path
                    FROM v7_page_artifacts
                    WHERE manifest_id = ?
                      AND artifact_kind = 'page_image'
                      AND artifact_status = 'complete'
                    """,
                    (manifest_id,),
                ).fetchall()
                artifacts_by_page: dict[int, list[tuple[str | None, str | None]]] = {}
                for physical_page_number, image_path, thumbnail_path in artifacts:
                    artifacts_by_page.setdefault(int(physical_page_number), []).append(
                        (image_path, thumbnail_path)
                    )

                missing_pages: list[int] = []
                invalid_pages: list[int] = []
                for physical_page_number in range(1, physical_page_count + 1):
                    page_artifacts = artifacts_by_page.get(physical_page_number, [])
                    if not page_artifacts:
                        missing_pages.append(physical_page_number)
                        continue
                    if not any(
                        image_path
                        and thumbnail_path
                        and Path(image_path).is_file()
                        and Path(thumbnail_path).is_file()
                        for image_path, thumbnail_path in page_artifacts
                    ):
                        invalid_pages.append(physical_page_number)

                parse_batches = connection.execute(
                    """
                    SELECT physical_page_start, physical_page_end, batch_status
                    FROM v7_parse_batches
                    WHERE manifest_id = ?
                    """,
                    (manifest_id,),
                ).fetchall()
                parse_page_statuses: dict[int, str] = {}
                for physical_page_start, physical_page_end, batch_status in parse_batches:
                    for physical_page_number in range(
                        int(physical_page_start),
                        int(physical_page_end) + 1,
                    ):
                        parse_page_statuses[physical_page_number] = batch_status
                missing_parse_pages = [
                    physical_page_number
                    for physical_page_number in range(1, physical_page_count + 1)
                    if physical_page_number not in parse_page_statuses
                ]
                failed_parse_pages = [
                    physical_page_number
                    for physical_page_number in range(1, physical_page_count + 1)
                    if parse_page_statuses.get(physical_page_number) == "failed"
                ]
                unresolved_parse_pages = [
                    physical_page_number
                    for physical_page_number in range(1, physical_page_count + 1)
                    if parse_page_statuses.get(physical_page_number)
                    in {"pending", "processing"}
                ]

                connection.execute(
                    "DELETE FROM v7_manifest_validation_issues WHERE manifest_id = ?",
                    (manifest_id,),
                )
                for physical_page_number in missing_pages:
                    connection.execute(
                        """
                        INSERT INTO v7_manifest_validation_issues(
                            manifest_id, physical_page_number, issue_code
                        ) VALUES (?, ?, 'missing_page_image')
                        """,
                        (manifest_id, physical_page_number),
                    )
                for physical_page_number in invalid_pages:
                    connection.execute(
                        """
                        INSERT INTO v7_manifest_validation_issues(
                            manifest_id, physical_page_number, issue_code
                        ) VALUES (?, ?, 'missing_page_files')
                        """,
                        (manifest_id, physical_page_number),
                    )
                for physical_page_number in missing_parse_pages:
                    connection.execute(
                        """
                        INSERT INTO v7_manifest_validation_issues(
                            manifest_id, physical_page_number, issue_code
                        ) VALUES (?, ?, 'missing_parse_batch')
                        """,
                        (manifest_id, physical_page_number),
                    )
                for physical_page_number in failed_parse_pages:
                    connection.execute(
                        """
                        INSERT INTO v7_manifest_validation_issues(
                            manifest_id, physical_page_number, issue_code
                        ) VALUES (?, ?, 'failed_parse_batch')
                        """,
                        (manifest_id, physical_page_number),
                    )
                for physical_page_number in unresolved_parse_pages:
                    connection.execute(
                        """
                        INSERT INTO v7_manifest_validation_issues(
                            manifest_id, physical_page_number, issue_code
                        ) VALUES (?, ?, 'unresolved_parse_batch')
                        """,
                        (manifest_id, physical_page_number),
                    )
                complete = not (
                    missing_pages
                    or invalid_pages
                    or missing_parse_pages
                    or failed_parse_pages
                    or unresolved_parse_pages
                )
                next_status = "complete" if complete else "incomplete"
                previous_status = manifest[1]
                if previous_status != next_status:
                    connection.execute(
                        """
                        UPDATE v7_document_asset_manifests
                        SET asset_status = ?
                        WHERE manifest_id = ?
                        """,
                        (next_status, manifest_id),
                    )
                    connection.execute(
                        """INSERT INTO v7_visual_artifact_status_events(
                            entity_type, entity_id, previous_status, next_status
                        ) VALUES ('document_asset_manifest', ?, ?, ?)""",
                        (manifest_id, previous_status, next_status),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return ManifestPageImageCompleteness(
            manifest_id=manifest_id,
            complete=complete,
            missing_physical_pages=tuple(missing_pages),
            invalid_physical_pages=tuple(invalid_pages),
            missing_parse_physical_pages=tuple(missing_parse_pages),
            failed_parse_physical_pages=tuple(failed_parse_pages),
            unresolved_parse_physical_pages=tuple(unresolved_parse_pages),
        )

    @classmethod
    def _validate_input(
        cls,
        source_sha256: str,
        physical_page_count: int,
        asset_status: str,
    ) -> None:
        """验证清单不会记录不可信的页数或状态。"""
        if (
            not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)
        ):
            raise ValueError("source_sha256 必须是小写 SHA-256")
        if type(physical_page_count) is not int or physical_page_count <= 0:
            raise ValueError("physical_page_count 必须为正整数")
        if asset_status not in cls._ALLOWED_ASSET_STATUSES:
            raise ValueError("asset_status 无效")
