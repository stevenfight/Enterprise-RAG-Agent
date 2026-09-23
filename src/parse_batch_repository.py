# -*- coding: utf-8 -*-
"""v7 PDF 解析批次的物理页段持久化。"""

from dataclasses import dataclass

from .v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class ParseBatchRecord:
    """单个解析批次及其物理页段。"""

    manifest_id: str
    batch_id: str
    physical_page_start: int
    physical_page_end: int
    batch_status: str
    created: bool


@dataclass(frozen=True)
class ParseBatchCoverage:
    """按 PDF 物理页汇总的解析覆盖状态。"""

    manifest_id: str
    complete: bool
    missing_physical_pages: tuple[int, ...]
    failed_physical_pages: tuple[int, ...]
    unresolved_physical_pages: tuple[int, ...]


class ParseBatchRepository:
    """以 manifest 为边界保存不可重叠的解析物理页段。"""

    _ALLOWED_BATCH_STATUSES = {"pending", "processing", "complete", "failed"}
    _STATUS_TRANSITIONS = {
        "pending": {"processing", "failed"},
        "processing": {"complete", "failed"},
        "failed": {"pending"},
        "complete": set(),
    }

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def record(
        self,
        *,
        manifest_id: str,
        batch_id: str,
        physical_page_start: int,
        physical_page_end: int,
        parser_name: str,
        parser_version: str,
        batch_status: str,
        error_code: str | None = None,
    ) -> ParseBatchRecord:
        """保存单个解析批次，拒绝重叠或超出 manifest 的物理页段。"""
        self._validate_input(
            batch_id,
            physical_page_start,
            physical_page_end,
            parser_name,
            parser_version,
            batch_status,
            error_code,
        )
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                manifest = connection.execute(
                    """
                    SELECT physical_page_count FROM v7_document_asset_manifests
                    WHERE manifest_id = ?
                    """,
                    (manifest_id,),
                ).fetchone()
                if manifest is None:
                    raise ValueError("manifest_id 不存在")
                if physical_page_end > int(manifest[0]):
                    raise ValueError("物理页段超出 manifest 总页数")
                existing = connection.execute(
                    """
                    SELECT physical_page_start, physical_page_end, parser_name,
                           parser_version, batch_status, error_code
                    FROM v7_parse_batches
                    WHERE manifest_id = ? AND batch_id = ?
                    """,
                    (manifest_id, batch_id),
                ).fetchone()
                expected = (
                    physical_page_start,
                    physical_page_end,
                    parser_name,
                    parser_version,
                    batch_status,
                    error_code,
                )
                if existing is not None:
                    if tuple(existing) != expected:
                        raise ValueError("batch_id 与既有批次证据不一致")
                    connection.commit()
                    return ParseBatchRecord(
                        manifest_id,
                        batch_id,
                        physical_page_start,
                        physical_page_end,
                        batch_status,
                        False,
                    )
                overlapping = connection.execute(
                    """
                    SELECT batch_id FROM v7_parse_batches
                    WHERE manifest_id = ?
                      AND NOT (
                        physical_page_end < ? OR physical_page_start > ?
                      )
                    """,
                    (manifest_id, physical_page_start, physical_page_end),
                ).fetchone()
                if overlapping is not None:
                    raise ValueError("物理页段与既有批次重叠")
                connection.execute(
                    """
                    INSERT INTO v7_parse_batches(
                        manifest_id, batch_id, physical_page_start,
                        physical_page_end, parser_name, parser_version,
                        batch_status, error_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest_id,
                        batch_id,
                        physical_page_start,
                        physical_page_end,
                        parser_name,
                        parser_version,
                        batch_status,
                        error_code,
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return ParseBatchRecord(
            manifest_id,
            batch_id,
            physical_page_start,
            physical_page_end,
            batch_status,
            True,
        )

    def transition_status(
        self,
        manifest_id: str,
        batch_id: str,
        next_status: str,
        *,
        error_code: str | None = None,
    ) -> str:
        """按解析批次状态机迁移，并和审计事件在同一事务内提交。"""
        if not isinstance(manifest_id, str) or not manifest_id.strip():
            raise ValueError("manifest_id 不能为空")
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ValueError("batch_id 不能为空")
        self._validate_transition_input(next_status, error_code)
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT batch_status FROM v7_parse_batches
                    WHERE manifest_id = ? AND batch_id = ?""",
                    (manifest_id, batch_id),
                ).fetchone()
                if row is None:
                    raise ValueError("解析批次不存在")
                previous_status = row[0]
                if previous_status == next_status:
                    connection.commit()
                    return next_status
                if next_status not in self._STATUS_TRANSITIONS[previous_status]:
                    raise ValueError("解析批次状态不允许迁移")
                connection.execute(
                    """UPDATE v7_parse_batches
                    SET batch_status = ?, error_code = ?
                    WHERE manifest_id = ? AND batch_id = ?""",
                    (next_status, error_code, manifest_id, batch_id),
                )
                connection.execute(
                    """INSERT INTO v7_visual_artifact_status_events(
                        entity_type, entity_id, previous_status, next_status
                    ) VALUES ('parse_batch', ?, ?, ?)""",
                    (f"{manifest_id}:{batch_id}", previous_status, next_status),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return next_status

    def summarize(self, manifest_id: str) -> ParseBatchCoverage:
        """汇总物理页段，避免把失败或未完成批次误报为完整解析。"""
        self.store.initialize()
        with self.store.connect() as connection:
            manifest = connection.execute(
                """
                SELECT physical_page_count FROM v7_document_asset_manifests
                WHERE manifest_id = ?
                """,
                (manifest_id,),
            ).fetchone()
            if manifest is None:
                raise ValueError("manifest_id 不存在")
            batches = connection.execute(
                """
                SELECT physical_page_start, physical_page_end, batch_status
                FROM v7_parse_batches
                WHERE manifest_id = ?
                """,
                (manifest_id,),
            ).fetchall()
        page_statuses: dict[int, str] = {}
        for physical_page_start, physical_page_end, batch_status in batches:
            for physical_page_number in range(
                int(physical_page_start),
                int(physical_page_end) + 1,
            ):
                page_statuses[physical_page_number] = batch_status
        physical_page_count = int(manifest[0])
        missing_pages = tuple(
            page
            for page in range(1, physical_page_count + 1)
            if page not in page_statuses
        )
        failed_pages = tuple(
            page
            for page in range(1, physical_page_count + 1)
            if page_statuses.get(page) == "failed"
        )
        unresolved_pages = tuple(
            page
            for page in range(1, physical_page_count + 1)
            if page_statuses.get(page) in {"pending", "processing"}
        )
        return ParseBatchCoverage(
            manifest_id=manifest_id,
            complete=not missing_pages and not failed_pages and not unresolved_pages,
            missing_physical_pages=missing_pages,
            failed_physical_pages=failed_pages,
            unresolved_physical_pages=unresolved_pages,
        )

    @classmethod
    def _validate_transition_input(cls, next_status: str, error_code: str | None) -> None:
        """验证状态迁移的目标状态和失败证据。"""
        if next_status not in cls._ALLOWED_BATCH_STATUSES:
            raise ValueError("batch_status 无效")
        if next_status == "failed":
            if not isinstance(error_code, str) or not error_code.strip():
                raise ValueError("failed 批次必须记录 error_code")
        elif error_code is not None:
            raise ValueError("只有 failed 批次可以记录 error_code")

    @classmethod
    def _validate_input(
        cls,
        batch_id: str,
        physical_page_start: int,
        physical_page_end: int,
        parser_name: str,
        parser_version: str,
        batch_status: str,
        error_code: str | None,
    ) -> None:
        """验证批次身份、物理页范围、解析器标识和失败证据。"""
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ValueError("batch_id 不能为空")
        if (
            type(physical_page_start) is not int
            or type(physical_page_end) is not int
            or physical_page_start <= 0
            or physical_page_end < physical_page_start
        ):
            raise ValueError("物理页段必须是递增的正整数范围")
        if not isinstance(parser_name, str) or not parser_name.strip():
            raise ValueError("parser_name 不能为空")
        if not isinstance(parser_version, str) or not parser_version.strip():
            raise ValueError("parser_version 不能为空")
        if batch_status not in cls._ALLOWED_BATCH_STATUSES:
            raise ValueError("batch_status 无效")
        if error_code is not None and (
            not isinstance(error_code, str) or not error_code.strip()
        ):
            raise ValueError("error_code 必须是非空字符串或 None")
        if batch_status != "failed" and error_code is not None:
            raise ValueError("只有 failed 批次可以记录 error_code")
