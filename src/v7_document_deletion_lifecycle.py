# -*- coding: utf-8 -*-
"""V7 文档版本删除的线性化点与请求级可见性边界。"""

from contextvars import ContextVar
from dataclasses import dataclass

from .v7_metadata_store import V7MetadataStore


class V7PublicationDeletingDocumentError(RuntimeError):
    """新请求的 publication 快照包含 deleting 文档，必须失败关闭。"""


@dataclass(frozen=True)
class DocumentDeletionStartResult:
    """删除线性化事务的结果；物理清理由后续受控步骤完成。"""

    document_version_id: str
    previous_status: str
    changed: bool
    active_request_lease_count: int


class V7DocumentDeletionLifecycle:
    """通过短事务把文档版本切到 deleting，作为新查询不可见的线性化点。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def begin_deletion(self, document_version_id: str) -> DocumentDeletionStartResult:
        """标记删除中并登记失效原因；重复调用保持幂等。"""
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise ValueError("document_version_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT index_status FROM v7_document_versions WHERE document_version_id = ?",
                    (document_version_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("document_version_id 不存在")
                previous_status = str(row[0])
                changed = previous_status != "deleting"
                if changed:
                    connection.execute(
                        "UPDATE v7_document_versions SET index_status = 'deleting' WHERE document_version_id = ?",
                        (document_version_id,),
                    )
                connection.execute(
                    """INSERT OR IGNORE INTO v7_document_version_invalidations(
                        document_version_id, reason
                    ) VALUES (?, 'deletion_requested')""",
                    (document_version_id,),
                )
                active_request_lease_count = self._active_request_lease_count(connection, document_version_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return DocumentDeletionStartResult(
            document_version_id, previous_status, changed, active_request_lease_count
        )

    def active_request_lease_count(self, document_version_id: str) -> int:
        """读取仍未过期且引用该版本的 publication 请求租约数量。"""
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise ValueError("document_version_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            return self._active_request_lease_count(connection, document_version_id)

    @staticmethod
    def _active_request_lease_count(connection, document_version_id: str) -> int:
        return int(connection.execute(
            """SELECT COUNT(*)
            FROM v7_publication_request_leases AS lease
            JOIN v7_publication_document_versions AS publication_document
                ON publication_document.publication_id = lease.publication_id
            WHERE publication_document.document_version_id = ?
                AND lease.expires_at > CAST(strftime('%s', 'now') AS REAL)""",
            (document_version_id,),
        ).fetchone()[0])


class V7DocumentVersionVisibilityResolver:
    """在查询开始时固定 active 文档版本；删除后的新查询不再取得该版本。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store
        self._current_document_version_id: ContextVar[str | None] = ContextVar(
            "v7_document_version_query_snapshot", default=None
        )

    def begin_query(self, logical_document_id: str) -> str | None:
        """固定本次查询可见的 active 文档版本；deleting 状态不满足查询条件。"""
        if not isinstance(logical_document_id, str) or not logical_document_id.strip():
            raise ValueError("logical_document_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                """SELECT document_version_id FROM v7_document_versions
                WHERE logical_document_id = ? AND index_status = 'active'""",
                (logical_document_id,),
            ).fetchone()
        document_version_id = str(row[0]) if row is not None else None
        self._current_document_version_id.set(document_version_id)
        return document_version_id

    def current_document_version_id(self) -> str | None:
        """返回当前查询已固定的文档版本 ID。"""
        return self._current_document_version_id.get()

    def end_query(self) -> None:
        """结束查询并释放本次固定的可见性快照。"""
        self._current_document_version_id.set(None)
