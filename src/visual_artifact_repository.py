# -*- coding: utf-8 -*-
"""v7 表格、图表和视觉证据的受约束 SQLite 仓储。"""

import uuid
from dataclasses import dataclass

from .v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class VisualArtifactRegistration:
    """已登记的表格或图表制品。"""

    artifact_id: str
    manifest_id: str
    visual_region_id: str | None
    artifact_status: str
    created: bool


@dataclass(frozen=True)
class VisualEvidenceRegistration:
    """同一文档清单内的视觉证据关联。"""

    visual_evidence_id: str
    manifest_id: str
    page_artifact_id: str | None
    visual_region_id: str | None
    table_artifact_id: str | None
    chart_artifact_id: str | None
    evidence_status: str


class VisualArtifactRepository:
    """防止表格、图表和证据跨 DocumentAssetManifest 错绑。"""

    _ALLOWED_STATUSES = {"pending", "incomplete", "complete"}
    _STATUS_TRANSITIONS = {
        "pending": {"incomplete", "complete"},
        "incomplete": {"pending", "complete"},
        "complete": set(),
    }

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def register_table(
        self,
        *,
        manifest_id: str,
        visual_region_id: str | None,
        source_format: str,
        artifact_status: str,
    ) -> VisualArtifactRegistration:
        """登记表格制品，区域存在时必须属于同一 manifest。"""
        if not isinstance(source_format, str) or not source_format.strip():
            raise ValueError("source_format 不能为空")
        self._validate_status(artifact_status, "artifact_status")
        return self._register_artifact(
            table=True,
            manifest_id=manifest_id,
            visual_region_id=visual_region_id,
            source_format=source_format,
            artifact_status=artifact_status,
        )

    def register_chart(
        self,
        *,
        manifest_id: str,
        visual_region_id: str | None,
        artifact_status: str,
    ) -> VisualArtifactRegistration:
        """登记图表制品，区域存在时必须属于同一 manifest。"""
        self._validate_status(artifact_status, "artifact_status")
        return self._register_artifact(
            table=False,
            manifest_id=manifest_id,
            visual_region_id=visual_region_id,
            source_format=None,
            artifact_status=artifact_status,
        )

    def register_evidence(
        self,
        *,
        manifest_id: str,
        page_artifact_id: str | None,
        visual_region_id: str | None,
        table_artifact_id: str | None,
        chart_artifact_id: str | None,
        evidence_status: str,
    ) -> VisualEvidenceRegistration:
        """登记视觉证据；所有非空关联必须可追溯到同一 manifest。"""
        self._validate_status(evidence_status, "evidence_status")
        if not any((page_artifact_id, visual_region_id, table_artifact_id, chart_artifact_id)):
            raise ValueError("视觉证据至少需要一个关联制品")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._require_manifest(connection, manifest_id)
                self._require_page_artifact(connection, manifest_id, page_artifact_id)
                self._require_region(connection, manifest_id, visual_region_id)
                self._require_related_artifact(connection, manifest_id, table_artifact_id, "v7_table_artifacts", "table_artifact_id")
                self._require_related_artifact(connection, manifest_id, chart_artifact_id, "v7_chart_artifacts", "chart_artifact_id")
                evidence_id = str(uuid.uuid4())
                connection.execute(
                    """INSERT INTO v7_visual_evidence(
                        visual_evidence_id, manifest_id, page_artifact_id,
                        visual_region_id, table_artifact_id, chart_artifact_id,
                        evidence_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (evidence_id, manifest_id, page_artifact_id, visual_region_id, table_artifact_id, chart_artifact_id, evidence_status),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return VisualEvidenceRegistration(
            evidence_id,
            manifest_id,
            page_artifact_id,
            visual_region_id,
            table_artifact_id,
            chart_artifact_id,
            evidence_status,
        )

    def transition_table_status(self, table_artifact_id: str, next_status: str) -> str:
        """按受限状态机迁移表格制品状态，并保留审计事件。"""
        return self._transition_status(
            entity_type="table_artifact",
            table_name="v7_table_artifacts",
            id_column="table_artifact_id",
            status_column="artifact_status",
            entity_id=table_artifact_id,
            next_status=next_status,
        )

    def transition_chart_status(self, chart_artifact_id: str, next_status: str) -> str:
        """按受限状态机迁移图表制品状态，并保留审计事件。"""
        return self._transition_status(
            entity_type="chart_artifact",
            table_name="v7_chart_artifacts",
            id_column="chart_artifact_id",
            status_column="artifact_status",
            entity_id=chart_artifact_id,
            next_status=next_status,
        )

    def transition_evidence_status(self, visual_evidence_id: str, next_status: str) -> str:
        """按受限状态机迁移视觉证据状态，并保留审计事件。"""
        return self._transition_status(
            entity_type="visual_evidence",
            table_name="v7_visual_evidence",
            id_column="visual_evidence_id",
            status_column="evidence_status",
            entity_id=visual_evidence_id,
            next_status=next_status,
        )

    def list_status_events(self, entity_id: str) -> list[tuple[str, str]]:
        """按写入顺序返回指定制品的状态迁移审计记录。"""
        if not isinstance(entity_id, str) or not entity_id.strip():
            raise ValueError("entity_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            rows = connection.execute(
                """SELECT previous_status, next_status
                FROM v7_visual_artifact_status_events
                WHERE entity_id = ?
                ORDER BY event_id""",
                (entity_id,),
            ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def _register_artifact(
        self,
        *,
        table: bool,
        manifest_id: str,
        visual_region_id: str | None,
        source_format: str | None,
        artifact_status: str,
    ) -> VisualArtifactRegistration:
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._require_manifest(connection, manifest_id)
                self._require_region(connection, manifest_id, visual_region_id)
                artifact_id = str(uuid.uuid4())
                if table:
                    connection.execute(
                        """INSERT INTO v7_table_artifacts(
                            table_artifact_id, manifest_id, visual_region_id, source_format, artifact_status
                        ) VALUES (?, ?, ?, ?, ?)""",
                        (artifact_id, manifest_id, visual_region_id, source_format, artifact_status),
                    )
                else:
                    connection.execute(
                        """INSERT INTO v7_chart_artifacts(
                            chart_artifact_id, manifest_id, visual_region_id, artifact_status
                        ) VALUES (?, ?, ?, ?)""",
                        (artifact_id, manifest_id, visual_region_id, artifact_status),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return VisualArtifactRegistration(artifact_id, manifest_id, visual_region_id, artifact_status, True)

    def _transition_status(
        self,
        *,
        entity_type: str,
        table_name: str,
        id_column: str,
        status_column: str,
        entity_id: str,
        next_status: str,
    ) -> str:
        if not isinstance(entity_id, str) or not entity_id.strip():
            raise ValueError("制品 ID 不能为空")
        self._validate_status(next_status, "next_status")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    f"SELECT {status_column} FROM {table_name} WHERE {id_column} = ?",
                    (entity_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("制品不存在")
                previous_status = row[0]
                if previous_status == next_status:
                    connection.commit()
                    return next_status
                if next_status not in self._STATUS_TRANSITIONS[previous_status]:
                    raise ValueError("制品状态不允许迁移")
                connection.execute(
                    f"UPDATE {table_name} SET {status_column} = ? WHERE {id_column} = ?",
                    (next_status, entity_id),
                )
                connection.execute(
                    """INSERT INTO v7_visual_artifact_status_events(
                        entity_type, entity_id, previous_status, next_status
                    ) VALUES (?, ?, ?, ?)""",
                    (entity_type, entity_id, previous_status, next_status),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return next_status

    @staticmethod
    def _require_manifest(connection, manifest_id: str) -> None:
        if not isinstance(manifest_id, str) or not manifest_id.strip():
            raise ValueError("manifest_id 不能为空")
        if connection.execute(
            "SELECT 1 FROM v7_document_asset_manifests WHERE manifest_id = ?", (manifest_id,)
        ).fetchone() is None:
            raise ValueError("manifest_id 不存在")

    @staticmethod
    def _require_page_artifact(connection, manifest_id: str, page_artifact_id: str | None) -> None:
        if page_artifact_id is None:
            return
        row = connection.execute(
            "SELECT manifest_id FROM v7_page_artifacts WHERE page_artifact_id = ?", (page_artifact_id,)
        ).fetchone()
        if row is None or row[0] != manifest_id:
            raise ValueError("页制品不存在或不属于 manifest")

    @staticmethod
    def _require_region(connection, manifest_id: str, visual_region_id: str | None) -> None:
        if visual_region_id is None:
            return
        row = connection.execute(
            """SELECT page.manifest_id FROM v7_visual_regions AS region
            JOIN v7_page_artifacts AS page ON page.page_artifact_id = region.page_artifact_id
            WHERE region.visual_region_id = ?""",
            (visual_region_id,),
        ).fetchone()
        if row is None or row[0] != manifest_id:
            raise ValueError("视觉区域不存在或不属于 manifest")

    @staticmethod
    def _require_related_artifact(connection, manifest_id: str, artifact_id: str | None, table: str, id_column: str) -> None:
        if artifact_id is None:
            return
        row = connection.execute(
            f"SELECT manifest_id FROM {table} WHERE {id_column} = ?", (artifact_id,)
        ).fetchone()
        if row is None or row[0] != manifest_id:
            raise ValueError("视觉制品不存在或不属于 manifest")

    @classmethod
    def _validate_status(cls, status: str, field_name: str) -> None:
        if status not in cls._ALLOWED_STATUSES:
            raise ValueError(f"{field_name} 无效")
