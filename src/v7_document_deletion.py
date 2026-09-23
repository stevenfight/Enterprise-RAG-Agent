# -*- coding: utf-8 -*-
"""未发布 V7 文档的受约束制品删除服务。"""

import os
from dataclasses import dataclass
from pathlib import Path

from .v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class V7DocumentDeletionResult:
    """一次删除操作移除的 V7 制品标识。"""

    document_version_id: str
    manifest_id: str
    removed_page_artifact_ids: tuple[str, ...]
    removed_visual_region_ids: tuple[str, ...]
    removed_table_artifact_ids: tuple[str, ...]
    removed_chart_artifact_ids: tuple[str, ...]
    removed_visual_evidence_ids: tuple[str, ...]


class V7DocumentDeletionService:
    """仅清理尚未进入索引代际或发布集的文档及视觉派生制品。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def delete_unpublished_document_version(
        self, document_version_id: str
    ) -> V7DocumentDeletionResult:
        """删除未发布文档的 manifest、页图、视觉区域、表图制品和解析批次。"""
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise ValueError("document_version_id 不能为空")
        self.store.initialize()
        staged_files: list[tuple[Path, Path]] = []
        try:
            with self.store.connect() as connection:
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    document = connection.execute(
                        "SELECT logical_document_id FROM v7_document_versions WHERE document_version_id = ?",
                        (document_version_id,),
                    ).fetchone()
                    if document is None:
                        raise ValueError("document_version_id 不存在")
                    self._reject_referenced_document(connection, document_version_id)
                    manifest = connection.execute(
                        "SELECT manifest_id FROM v7_document_asset_manifests WHERE document_version_id = ?",
                        (document_version_id,),
                    ).fetchone()
                    if manifest is None:
                        raise ValueError("document_version_id 缺少资产清单，拒绝不完整删除")
                    manifest_id = str(manifest[0])
                    page_rows = connection.execute(
                        """SELECT page_artifact_id, image_path, thumbnail_path
                        FROM v7_page_artifacts WHERE manifest_id = ?""",
                        (manifest_id,),
                    ).fetchall()
                    page_ids = tuple(str(row[0]) for row in page_rows)
                    self._reject_published_artifacts(connection, page_ids)
                    staged_files = self._stage_page_files(page_rows)
                    region_ids = self._ids(
                        connection,
                        "SELECT visual_region_id FROM v7_visual_regions WHERE page_artifact_id IN ({})",
                        page_ids,
                    )
                    table_ids = self._ids(
                        connection,
                        "SELECT table_artifact_id FROM v7_table_artifacts WHERE manifest_id = ?",
                        (manifest_id,),
                    )
                    chart_ids = self._ids(
                        connection,
                        "SELECT chart_artifact_id FROM v7_chart_artifacts WHERE manifest_id = ?",
                        (manifest_id,),
                    )
                    evidence_ids = self._ids(
                        connection,
                        "SELECT visual_evidence_id FROM v7_visual_evidence WHERE manifest_id = ?",
                        (manifest_id,),
                    )
                    self._delete_by_manifest(connection, manifest_id)
                    connection.execute(
                        "DELETE FROM v7_document_versions WHERE document_version_id = ?",
                        (document_version_id,),
                    )
                    connection.execute(
                        """DELETE FROM v7_logical_documents WHERE logical_document_id = ?
                        AND NOT EXISTS (
                            SELECT 1 FROM v7_document_versions WHERE logical_document_id = ?
                        )""",
                        (document[0], document[0]),
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        except Exception:
            self._restore_staged_files(staged_files)
            raise

        for _, deleting_path in staged_files:
            deleting_path.unlink()
        return V7DocumentDeletionResult(
            document_version_id=document_version_id,
            manifest_id=manifest_id,
            removed_page_artifact_ids=page_ids,
            removed_visual_region_ids=region_ids,
            removed_table_artifact_ids=table_ids,
            removed_chart_artifact_ids=chart_ids,
            removed_visual_evidence_ids=evidence_ids,
        )

    @staticmethod
    def resume_pending_page_file_cleanup(artifact_root: Path) -> tuple[Path, ...]:
        """仅在明确的页图根目录内幂等清理中断后遗留的 `.deleting` 文件。"""
        artifact_root = Path(artifact_root).resolve()
        if not artifact_root.is_dir():
            raise ValueError("页图制品根目录不存在")
        removed: list[Path] = []
        for pending_path in sorted(artifact_root.rglob("*.png.deleting")):
            if not pending_path.is_file():
                continue
            pending_path.unlink()
            removed.append(pending_path)
        return tuple(removed)

    @staticmethod
    def _reject_referenced_document(connection, document_version_id: str) -> None:
        if connection.execute(
            "SELECT 1 FROM v7_generation_documents WHERE document_version_id = ?",
            (document_version_id,),
        ).fetchone() is not None:
            raise ValueError("文档已进入索引代际，必须通过代际迁移移除")
        if connection.execute(
            "SELECT 1 FROM v7_publication_document_versions WHERE document_version_id = ?",
            (document_version_id,),
        ).fetchone() is not None:
            raise ValueError("文档已进入发布集，必须先执行发布回滚或代际迁移")
        if connection.execute(
            "SELECT 1 FROM v7_fact_document_versions WHERE document_version_id = ?",
            (document_version_id,),
        ).fetchone() is not None:
            raise ValueError("文档仍关联金融事实，必须先完成事实失效治理")
        if connection.execute(
            "SELECT 1 FROM v7_financial_fact_sources WHERE document_version_id = ?",
            (document_version_id,),
        ).fetchone() is not None:
            raise ValueError("文档仍关联金融事实来源，必须先完成事实失效治理")

    @staticmethod
    def _reject_published_artifacts(connection, page_ids: tuple[str, ...]) -> None:
        if not page_ids:
            return
        placeholders = ", ".join("?" for _ in page_ids)
        if connection.execute(
            f"SELECT 1 FROM v7_publication_page_artifacts WHERE page_artifact_id IN ({placeholders})",
            page_ids,
        ).fetchone() is not None:
            raise ValueError("页图已进入发布集，必须先执行发布回滚或代际迁移")
        if connection.execute(
            f"SELECT 1 FROM v7_artifact_fact_links WHERE page_artifact_id IN ({placeholders})",
            page_ids,
        ).fetchone() is not None:
            raise ValueError("页图仍关联金融事实，必须先完成事实失效治理")

    @classmethod
    def _ids(cls, connection, statement: str, values: tuple[str, ...]) -> tuple[str, ...]:
        if "{}" in statement:
            if not values:
                return ()
            statement = statement.format(", ".join("?" for _ in values))
        return tuple(str(row[0]) for row in connection.execute(statement, values).fetchall())

    @staticmethod
    def _stage_page_files(page_rows) -> list[tuple[Path, Path]]:
        staged: list[tuple[Path, Path]] = []
        for _, image_path, thumbnail_path in page_rows:
            for raw_path in (image_path, thumbnail_path):
                path = Path(raw_path)
                if not path.is_file():
                    raise ValueError("页图文件不存在，拒绝不完整删除")
                deleting_path = path.with_name(f"{path.name}.deleting")
                os.replace(path, deleting_path)
                staged.append((path, deleting_path))
        return staged

    @staticmethod
    def _restore_staged_files(staged_files: list[tuple[Path, Path]]) -> None:
        for original_path, deleting_path in reversed(staged_files):
            if deleting_path.exists():
                os.replace(deleting_path, original_path)

    @staticmethod
    def _delete_by_manifest(connection, manifest_id: str) -> None:
        connection.execute("DELETE FROM v7_visual_evidence WHERE manifest_id = ?", (manifest_id,))
        connection.execute("DELETE FROM v7_table_artifacts WHERE manifest_id = ?", (manifest_id,))
        connection.execute("DELETE FROM v7_chart_artifacts WHERE manifest_id = ?", (manifest_id,))
        connection.execute(
            """DELETE FROM v7_visual_regions WHERE page_artifact_id IN (
                SELECT page_artifact_id FROM v7_page_artifacts WHERE manifest_id = ?
            )""",
            (manifest_id,),
        )
        connection.execute("DELETE FROM v7_parse_batches WHERE manifest_id = ?", (manifest_id,))
        connection.execute("DELETE FROM v7_manifest_validation_issues WHERE manifest_id = ?", (manifest_id,))
        connection.execute("DELETE FROM v7_page_artifacts WHERE manifest_id = ?", (manifest_id,))
        connection.execute("DELETE FROM v7_document_asset_manifests WHERE manifest_id = ?", (manifest_id,))
