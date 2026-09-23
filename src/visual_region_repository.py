# -*- coding: utf-8 -*-
"""v7 VisualRegion 仓储，绑定页图制品与规范化坐标。"""

import math
import uuid
from dataclasses import dataclass

from .v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class VisualRegionRegistration:
    """已登记的视觉区域及其不可变物理页归属。"""

    visual_region_id: str
    manifest_id: str
    page_artifact_id: str
    physical_page_number: int
    created: bool


class VisualRegionRepository:
    """将规范化视觉区域登记到既有 PageArtifact。"""

    _ALLOWED_REGION_STATUSES = {"pending", "complete", "incomplete"}
    _STATUS_TRANSITIONS = {
        "pending": {"incomplete", "complete"},
        "incomplete": {"pending", "complete"},
        "complete": set(),
    }

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def register(
        self,
        *,
        page_artifact_id: str,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        region_status: str,
    ) -> VisualRegionRegistration:
        """登记一个页内区域；坐标使用 0 到 1 的左上—右下规范化空间。"""
        coordinates = self._validate_coordinates(x0, y0, x1, y1)
        if region_status not in self._ALLOWED_REGION_STATUSES:
            raise ValueError("region_status 无效")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                artifact = connection.execute(
                    """
                    SELECT manifest_id, physical_page_number
                    FROM v7_page_artifacts
                    WHERE page_artifact_id = ?
                      AND artifact_kind = 'page_image'
                      AND artifact_status = 'complete'
                    """,
                    (page_artifact_id,),
                ).fetchone()
                if artifact is None:
                    raise ValueError("page_artifact_id 不存在或页图未完成")
                existing = connection.execute(
                    """
                    SELECT visual_region_id
                    FROM v7_visual_regions
                    WHERE page_artifact_id = ?
                      AND x0 = ? AND y0 = ? AND x1 = ? AND y1 = ?
                      AND region_status = ?
                    """,
                    (page_artifact_id, *coordinates, region_status),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    return VisualRegionRegistration(
                        visual_region_id=existing[0],
                        manifest_id=artifact[0],
                        page_artifact_id=page_artifact_id,
                        physical_page_number=int(artifact[1]),
                        created=False,
                    )
                visual_region_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO v7_visual_regions(
                        visual_region_id, page_artifact_id,
                        x0, y0, x1, y1, region_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (visual_region_id, page_artifact_id, *coordinates, region_status),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return VisualRegionRegistration(
            visual_region_id=visual_region_id,
            manifest_id=artifact[0],
            page_artifact_id=page_artifact_id,
            physical_page_number=int(artifact[1]),
            created=True,
        )

    def transition_status(self, visual_region_id: str, next_status: str) -> str:
        """按受限状态机迁移区域状态，并与审计事件同事务提交。"""
        if not isinstance(visual_region_id, str) or not visual_region_id.strip():
            raise ValueError("visual_region_id 不能为空")
        if next_status not in self._ALLOWED_REGION_STATUSES:
            raise ValueError("region_status 无效")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT region_status FROM v7_visual_regions
                    WHERE visual_region_id = ?""",
                    (visual_region_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("visual_region_id 不存在")
                previous_status = row[0]
                if previous_status == next_status:
                    connection.commit()
                    return next_status
                if next_status not in self._STATUS_TRANSITIONS[previous_status]:
                    raise ValueError("视觉区域状态不允许迁移")
                connection.execute(
                    """UPDATE v7_visual_regions SET region_status = ?
                    WHERE visual_region_id = ?""",
                    (next_status, visual_region_id),
                )
                connection.execute(
                    """INSERT INTO v7_visual_artifact_status_events(
                        entity_type, entity_id, previous_status, next_status
                    ) VALUES ('visual_region', ?, ?, ?)""",
                    (visual_region_id, previous_status, next_status),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return next_status

    @staticmethod
    def _validate_coordinates(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> tuple[float, float, float, float]:
        """拒绝非数值、无穷值、越界及零面积/反向区域。"""
        raw_coordinates = (x0, y0, x1, y1)
        if any(type(value) not in (int, float) for value in raw_coordinates):
            raise ValueError("坐标必须是有限数值")
        coordinates = tuple(float(value) for value in raw_coordinates)
        if any(not math.isfinite(value) or value < 0 or value > 1 for value in coordinates):
            raise ValueError("坐标必须位于 0 到 1 之间")
        if coordinates[0] >= coordinates[2] or coordinates[1] >= coordinates[3]:
            raise ValueError("坐标必须构成有序的非零面积区域")
        return coordinates
