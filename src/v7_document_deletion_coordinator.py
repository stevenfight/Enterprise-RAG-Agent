# -*- coding: utf-8 -*-
"""已发布 V7 文档删除请求的异步状态协调器。"""

from dataclasses import dataclass

from .provenance_repository import ProvenanceRepository
from .v7_document_deletion_lifecycle import V7DocumentDeletionLifecycle
from .v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class V7DocumentDeletionRequest:
    """删除请求当前状态；物理清理只能由后续重建和发布流程推进。"""

    document_version_id: str
    status: str
    active_request_lease_count: int


class V7DocumentDeletionCoordinator:
    """将 deleting 线性化结果持久化为可轮询的删除请求状态。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store
        self.lifecycle = V7DocumentDeletionLifecycle(store)
        self.provenance = ProvenanceRepository(store)

    def request_deletion(self, document_version_id: str) -> V7DocumentDeletionRequest:
        """开始删除并返回等待 lease 或重建 generation 的异步状态。"""
        result = self.lifecycle.begin_deletion(document_version_id)
        return self._save_status(document_version_id, result.active_request_lease_count)

    def request_deletion_by_original_filename(
        self, original_filename: str
    ) -> list[V7DocumentDeletionRequest]:
        """按原始文件名为全部未删除版本创建删除请求；已 deleting 的版本幂等跳过。"""
        if not isinstance(original_filename, str) or not original_filename.strip():
            raise ValueError("original_filename 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            rows = connection.execute(
                """SELECT document_version_id FROM v7_document_versions
                WHERE original_filename = ? AND index_status != 'deleting'
                ORDER BY document_version_id""",
                (original_filename,),
            ).fetchall()
        return [self.request_deletion(str(row[0])) for row in rows]

    def refresh_request(self, document_version_id: str) -> V7DocumentDeletionRequest:
        """重新评估已有删除请求；不执行物理删除。"""
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise ValueError("document_version_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM v7_document_deletion_requests WHERE document_version_id = ?",
                (document_version_id,),
            ).fetchone()
        if existing is None:
            raise ValueError("document_version_id 尚未创建删除请求")
        return self._save_status(
            document_version_id, self.lifecycle.active_request_lease_count(document_version_id)
        )

    def advance_request(self, document_version_id: str) -> V7DocumentDeletionRequest:
        """异步推进删除请求：租约归零且替代 publication 生效后进入 cleanup_ready。"""
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise ValueError("document_version_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM v7_document_deletion_requests WHERE document_version_id = ?",
                (document_version_id,),
            ).fetchone()
        if existing is None:
            raise ValueError("document_version_id 尚未创建删除请求")
        # 1. 存在未过期租约时只回报等待状态，不做任何清理动作
        lease_count = self.lifecycle.active_request_lease_count(document_version_id)
        if lease_count:
            return self._save_status(document_version_id, lease_count)
        # 2. 无租约时检查 active publication 是否仍包含被删版本
        with self.store.connect() as connection:
            active_row = connection.execute(
                "SELECT publication_id FROM v7_active_publication WHERE singleton_id = 1"
            ).fetchone()
            blocked = False
            if active_row is not None:
                contained = connection.execute(
                    """SELECT 1 FROM v7_publication_document_versions
                    WHERE publication_id = ? AND document_version_id = ?""",
                    (active_row[0], document_version_id),
                ).fetchone()
                blocked = contained is not None
        if blocked:
            return self._save_status(document_version_id, 0)
        # 3. 替代 publication 已生效：进入 cleanup_ready 稳定终态
        return self._save_cleanup_ready(document_version_id)

    def cleanup_request(
        self,
        document_version_id: str,
        document_repository,
        *,
        retention_seconds: float = 0.0,
    ) -> dict:
        """M3.11 物理清理：失效事实可见性、传播 stale 并按资格回收共享 blob。"""
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise ValueError("document_version_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            request_row = connection.execute(
                "SELECT status FROM v7_document_deletion_requests WHERE document_version_id = ?",
                (document_version_id,),
            ).fetchone()
            version_row = connection.execute(
                "SELECT blob_sha256 FROM v7_document_versions WHERE document_version_id = ?",
                (document_version_id,),
            ).fetchone()
        if request_row is None:
            raise ValueError("document_version_id 尚未创建删除请求")
        if request_row[0] != "cleanup_ready":
            raise ValueError("删除请求尚未达到 cleanup_ready，拒绝物理清理")
        if version_row is None:
            raise ValueError("document_version_id 不存在")

        # 1. 事实与溯源失效：直接/间接依赖的计算、声明、报告进入 stale（含审计记录）
        invalidated = self.provenance.invalidate_document_version(
            document_version_id, "document_cleanup"
        )
        # 2. 事实可见性失效：该版本的事实关联行删除，软失效审计保留
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM v7_fact_document_versions WHERE document_version_id = ?",
                    (document_version_id,),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        # 3. 共享 blob 仅在零引用且超过保留期后物理回收（deleting 版本不计引用）
        blob_sha256 = version_row[0]
        reclaimed = document_repository.reclaim_blob_if_eligible(
            blob_sha256, retention_seconds=retention_seconds
        )
        result = dict(invalidated)
        result["reclaimed"] = reclaimed
        return result

    def _save_cleanup_ready(self, document_version_id: str) -> V7DocumentDeletionRequest:
        """将删除请求持久化为 cleanup_ready；该状态一旦写入即为终态。"""
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """INSERT INTO v7_document_deletion_requests(
                        document_version_id, status, active_request_lease_count
                    ) VALUES (?, 'cleanup_ready', 0)
                    ON CONFLICT(document_version_id) DO UPDATE SET
                        status = 'cleanup_ready',
                        active_request_lease_count = 0,
                        updated_at = CURRENT_TIMESTAMP""",
                    (document_version_id,),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return V7DocumentDeletionRequest(document_version_id, "cleanup_ready", 0)

    def _save_status(
        self, document_version_id: str, active_request_lease_count: int
    ) -> V7DocumentDeletionRequest:
        status = "waiting_for_active_requests" if active_request_lease_count else "rebuild_required"
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing_status = connection.execute(
                    "SELECT status FROM v7_document_deletion_requests WHERE document_version_id = ?",
                    (document_version_id,),
                ).fetchone()
                if existing_status is not None and existing_status[0] == "cleanup_ready":
                    # cleanup_ready 是稳定终态：refresh/advance 不得降级
                    connection.commit()
                    return V7DocumentDeletionRequest(document_version_id, "cleanup_ready", 0)
                connection.execute(
                    """INSERT INTO v7_document_deletion_requests(
                        document_version_id, status, active_request_lease_count
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(document_version_id) DO UPDATE SET
                        status = excluded.status,
                        active_request_lease_count = excluded.active_request_lease_count,
                        updated_at = CURRENT_TIMESTAMP""",
                    (document_version_id, status, active_request_lease_count),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return V7DocumentDeletionRequest(document_version_id, status, active_request_lease_count)
