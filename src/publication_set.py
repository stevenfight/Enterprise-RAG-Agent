# -*- coding: utf-8 -*-
"""V7 PublicationSet：以 SQLite 固定请求可见的 generation 与溯源边界。"""

import json
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterable, Optional

from .v7_document_deletion_lifecycle import V7PublicationDeletingDocumentError
from .v7_metadata_store import V7MetadataStore


class PublicationSetError(RuntimeError):
    """发布集合不满足完整性或可见性边界。"""


@dataclass(frozen=True)
class PublicationSnapshot:
    """一次请求固定使用的不可变发布快照。"""

    publication_id: str
    generation_id: str
    corpus_revision: str
    document_version_ids: tuple[str, ...]
    page_artifact_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]


class PublicationSetRepository:
    """创建不可变发布集合，并只通过 SQLite 切换 active publication。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self.store = store

    def create_publication(
        self,
        publication_id: str,
        generation_id: str,
        document_version_ids: Iterable[str],
        page_artifact_ids: Iterable[str] = (),
        fact_ids: Iterable[str] = (),
    ) -> PublicationSnapshot:
        """登记已验证 generation 的完整可见性边界，不自动激活。"""
        publication_id = self._required_id(publication_id, "publication_id")
        generation_id = self._required_id(generation_id, "generation_id")
        document_ids = self._normalized_ids(document_version_ids, "document_version_ids")
        artifact_ids = self._normalized_ids(page_artifact_ids, "page_artifact_ids")
        fact_ids = self._normalized_ids(fact_ids, "fact_ids")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                candidate = connection.execute(
                    "SELECT corpus_revision, status, validation_json FROM v7_generation_candidates WHERE generation_id = ?",
                    (generation_id,),
                ).fetchone()
                if candidate is None:
                    raise PublicationSetError("generation 不存在")
                if candidate[1] != "validated":
                    raise PublicationSetError("generation 必须处于 validated 状态")
                try:
                    validation = json.loads(candidate[2])
                except json.JSONDecodeError as error:
                    raise PublicationSetError("generation 验证记录格式无效") from error
                if (
                    not isinstance(validation, dict)
                    or validation.get("status") != "validated"
                    or not isinstance(validation.get("artifact_manifest"), list)
                    or not validation["artifact_manifest"]
                ):
                    raise PublicationSetError("generation 缺少已验证索引制品清单")
                expected_documents = self._generation_document_ids(connection, generation_id)
                if document_ids != expected_documents:
                    raise PublicationSetError("发布文档边界必须与 generation 完全一致")
                existing = connection.execute(
                    "SELECT 1 FROM v7_publication_sets WHERE publication_id = ?",
                    (publication_id,),
                ).fetchone()
                if existing is not None:
                    snapshot = self._snapshot(connection, publication_id)
                    if snapshot.generation_id != generation_id or snapshot != PublicationSnapshot(
                        publication_id, generation_id, candidate[0], document_ids, artifact_ids, fact_ids
                    ):
                        raise PublicationSetError("publication_id 与既有不可变发布集合不一致")
                    connection.commit()
                    return snapshot
                self._validate_page_artifacts(connection, artifact_ids, set(document_ids))
                self._validate_facts(connection, fact_ids, set(document_ids))
                connection.execute(
                    "INSERT INTO v7_publication_sets(publication_id, generation_id, corpus_revision) VALUES (?, ?, ?)",
                    (publication_id, generation_id, candidate[0]),
                )
                connection.executemany(
                    "INSERT INTO v7_publication_document_versions VALUES (?, ?)",
                    ((publication_id, item) for item in document_ids),
                )
                connection.executemany(
                    "INSERT INTO v7_publication_page_artifacts VALUES (?, ?)",
                    ((publication_id, item) for item in artifact_ids),
                )
                connection.executemany(
                    "INSERT INTO v7_publication_financial_facts VALUES (?, ?)",
                    ((publication_id, item) for item in fact_ids),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return PublicationSnapshot(publication_id, generation_id, candidate[0], document_ids, artifact_ids, fact_ids)

    def prepare_publication_build(
        self,
        publication_id: str,
        expected_active_publication_id: str | None,
        expected_corpus_revision: str | None,
    ) -> dict[str, str | None]:
        """记录构建开始时观察到的 publication/revision，供发布 CAS 使用。"""
        publication_id = self._required_id(publication_id, "publication_id")
        if expected_active_publication_id is not None:
            expected_active_publication_id = self._required_id(
                expected_active_publication_id, "expected_active_publication_id"
            )
        if expected_corpus_revision is not None:
            expected_corpus_revision = self._required_id(
                expected_corpus_revision, "expected_corpus_revision"
            )
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._snapshot(connection, publication_id)
                existing = connection.execute(
                    """SELECT expected_active_publication_id, expected_corpus_revision, status
                    FROM v7_publication_builds WHERE publication_id = ?""",
                    (publication_id,),
                ).fetchone()
                if existing is not None:
                    if tuple(existing[:2]) != (expected_active_publication_id, expected_corpus_revision):
                        raise PublicationSetError("publication build 的期望 revision 不一致")
                    connection.commit()
                    return {
                        "publication_id": publication_id,
                        "expected_active_publication_id": existing[0],
                        "expected_corpus_revision": existing[1],
                        "status": existing[2],
                    }
                connection.execute(
                    """INSERT INTO v7_publication_builds(
                        publication_id, expected_active_publication_id,
                        expected_corpus_revision, status
                    ) VALUES (?, ?, ?, 'prepared')""",
                    (publication_id, expected_active_publication_id, expected_corpus_revision),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {
            "publication_id": publication_id,
            "expected_active_publication_id": expected_active_publication_id,
            "expected_corpus_revision": expected_corpus_revision,
            "status": "prepared",
        }

    def activate_publication(self, publication_id: str) -> PublicationSnapshot:
        """以已登记 expected publication/revision 做 CAS 后切换唯一 active publication。"""
        publication_id = self._required_id(publication_id, "publication_id")
        self.store.initialize()
        superseded_reason = None
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                snapshot = self._snapshot(connection, publication_id)
                build = connection.execute(
                    """SELECT expected_active_publication_id, expected_corpus_revision, status
                    FROM v7_publication_builds WHERE publication_id = ?""",
                    (publication_id,),
                ).fetchone()
                if build is None:
                    raise PublicationSetError("publication 尚未登记 expected revision")
                if build[2] != "prepared":
                    raise PublicationSetError(f"publication build 状态不可发布: {build[2]}")
                active = connection.execute(
                    """SELECT active.publication_id, publication.corpus_revision
                    FROM v7_active_publication AS active
                    JOIN v7_publication_sets AS publication ON publication.publication_id = active.publication_id
                    WHERE active.singleton_id = 1"""
                ).fetchone()
                actual_active_id = active[0] if active else None
                actual_revision = active[1] if active else None
                if (actual_active_id, actual_revision) != (build[0], build[1]):
                    reason = (
                        "expected active publication/revision 与当前状态不一致: "
                        f"expected=({build[0]}, {build[1]}), actual=({actual_active_id}, {actual_revision})"
                    )
                    connection.execute(
                        """UPDATE v7_publication_builds
                        SET status = 'superseded', superseded_reason = ?
                        WHERE publication_id = ?""",
                        (reason, publication_id),
                    )
                    connection.commit()
                    superseded_reason = reason
                else:
                    connection.execute(
                        """INSERT INTO v7_active_publication(singleton_id, publication_id)
                        VALUES (1, ?)
                        ON CONFLICT(singleton_id) DO UPDATE SET
                            publication_id = excluded.publication_id,
                            activated_at = CURRENT_TIMESTAMP""",
                        (publication_id,),
                    )
                    connection.execute(
                        """UPDATE v7_publication_builds
                        SET status = 'published', published_at = CURRENT_TIMESTAMP
                        WHERE publication_id = ?""",
                        (publication_id,),
                    )
                    connection.commit()
            except Exception:
                connection.rollback()
                raise
        if superseded_reason is not None:
            raise PublicationSetError(f"publication build 已 superseded: {superseded_reason}")
        return snapshot

    def get_publication_build(self, publication_id: str) -> dict[str, str | None] | None:
        """读取构建的 expected revision 与最终状态，供 superseded 审计使用。"""
        publication_id = self._required_id(publication_id, "publication_id")
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                """SELECT expected_active_publication_id, expected_corpus_revision,
                status, superseded_reason FROM v7_publication_builds WHERE publication_id = ?""",
                (publication_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "publication_id": publication_id,
            "expected_active_publication_id": row[0],
            "expected_corpus_revision": row[1],
            "status": row[2],
            "superseded_reason": row[3],
        }

    def rollback_to_publication(
        self,
        rollback_publication_id: str,
        restored_publication_id: str,
    ) -> PublicationSnapshot:
        """以新 publication 重指向完整历史快照，禁止只回滚 generation 指针。"""
        rollback_publication_id = self._required_id(
            rollback_publication_id, "rollback_publication_id"
        )
        restored_publication_id = self._required_id(
            restored_publication_id, "restored_publication_id"
        )
        self.store.initialize()
        with self.store.connect() as connection:
            restored = self._snapshot(connection, restored_publication_id)
            active = connection.execute(
                """SELECT active.publication_id, publication.corpus_revision
                FROM v7_active_publication AS active
                JOIN v7_publication_sets AS publication ON publication.publication_id = active.publication_id
                WHERE active.singleton_id = 1"""
            ).fetchone()
        expected_active_id = active[0] if active else None
        expected_revision = active[1] if active else None
        snapshot = self.create_publication(
            rollback_publication_id,
            restored.generation_id,
            restored.document_version_ids,
            restored.page_artifact_ids,
            restored.fact_ids,
        )
        self.prepare_publication_build(
            rollback_publication_id,
            expected_active_id,
            expected_revision,
        )
        self.activate_publication(rollback_publication_id)
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """INSERT INTO v7_publication_rollbacks(
                        rollback_publication_id, restored_publication_id, replaced_publication_id
                    ) VALUES (?, ?, ?)""",
                    (rollback_publication_id, restored_publication_id, expected_active_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return snapshot

    def get_active_publication(self) -> PublicationSnapshot | None:
        """从 SQLite 真值读取当前 active publication，不读取文件指针。"""
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute("SELECT publication_id FROM v7_active_publication WHERE singleton_id = 1").fetchone()
            return None if row is None else self._snapshot(connection, row[0])

    def acquire_request_lease(
        self, publication_id: str, owner_token: str, *, ttl_seconds: float, now: float | None = None
    ) -> str:
        """为已固定的 publication 记录短期活动请求租约。"""
        publication_id = self._required_id(publication_id, "publication_id")
        owner_token = self._required_id(owner_token, "owner_token")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds 必须大于 0")
        expires_at = (time.time() if now is None else float(now)) + ttl_seconds
        lease_id = str(uuid.uuid4())
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._snapshot(connection, publication_id)
                connection.execute(
                    """INSERT INTO v7_publication_request_leases(
                        lease_id, publication_id, owner_token, expires_at
                    ) VALUES (?, ?, ?, ?)""",
                    (lease_id, publication_id, owner_token, expires_at),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return lease_id

    def release_request_lease(self, lease_id: str) -> None:
        """释放已结束请求的 publication 租约；未知租约按幂等完成处理。"""
        lease_id = self._required_id(lease_id, "lease_id")
        self.store.initialize()
        with self.store.connect() as connection:
            connection.execute("DELETE FROM v7_publication_request_leases WHERE lease_id = ?", (lease_id,))
            connection.commit()

    @staticmethod
    def _required_id(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} 不能为空")
        return value

    @classmethod
    def _normalized_ids(cls, values: Iterable[str], name: str) -> tuple[str, ...]:
        normalized = tuple(sorted(cls._required_id(value, name) for value in values))
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"{name} 不能包含重复 ID")
        return normalized

    @staticmethod
    def _generation_document_ids(connection, generation_id: str) -> tuple[str, ...]:
        return tuple(
            row[0] for row in connection.execute(
                "SELECT document_version_id FROM v7_generation_documents WHERE generation_id = ? ORDER BY document_version_id",
                (generation_id,),
            ).fetchall()
        )

    @staticmethod
    def _validate_page_artifacts(connection, artifact_ids: tuple[str, ...], document_ids: set[str]) -> None:
        for artifact_id in artifact_ids:
            row = connection.execute(
                """SELECT manifest.document_version_id
                FROM v7_page_artifacts AS artifact
                JOIN v7_document_asset_manifests AS manifest ON manifest.manifest_id = artifact.manifest_id
                WHERE artifact.page_artifact_id = ?""",
                (artifact_id,),
            ).fetchone()
            if row is None or row[0] not in document_ids:
                raise PublicationSetError("制品不存在或不属于发布文档边界")

    @staticmethod
    def _validate_facts(connection, fact_ids: tuple[str, ...], document_ids: set[str]) -> None:
        for fact_id in fact_ids:
            fact_exists = connection.execute(
                "SELECT 1 FROM v7_financial_facts WHERE fact_id = ?", (fact_id,)
            ).fetchone()
            source_rows = connection.execute(
                "SELECT document_version_id FROM v7_fact_document_versions WHERE fact_id = ?", (fact_id,)
            ).fetchall()
            if fact_exists is None or not source_rows or any(row[0] not in document_ids for row in source_rows):
                raise PublicationSetError("事实不存在或不属于发布文档边界")

    @staticmethod
    def _snapshot(connection, publication_id: str) -> PublicationSnapshot:
        row = connection.execute(
            "SELECT generation_id, corpus_revision FROM v7_publication_sets WHERE publication_id = ?",
            (publication_id,),
        ).fetchone()
        if row is None:
            raise PublicationSetError("publication 不存在")
        documents = tuple(item[0] for item in connection.execute(
            "SELECT document_version_id FROM v7_publication_document_versions WHERE publication_id = ? ORDER BY document_version_id",
            (publication_id,),
        ).fetchall())
        artifacts = tuple(item[0] for item in connection.execute(
            "SELECT page_artifact_id FROM v7_publication_page_artifacts WHERE publication_id = ? ORDER BY page_artifact_id",
            (publication_id,),
        ).fetchall())
        facts = tuple(item[0] for item in connection.execute(
            "SELECT fact_id FROM v7_publication_financial_facts WHERE publication_id = ? ORDER BY fact_id",
            (publication_id,),
        ).fetchall())
        return PublicationSnapshot(publication_id, row[0], row[1], documents, artifacts, facts)


class PublicationResolver:
    """在请求开始时捕获 publication 快照，调用方持有该快照直至请求结束。"""

    def __init__(self, repository: PublicationSetRepository) -> None:
        self.repository = repository
        # 请求级固定快照：ContextVar 保证线程/协程间相互隔离
        self._request_snapshot: ContextVar[Optional[PublicationSnapshot]] = ContextVar(
            "v7_publication_request_snapshot", default=None
        )
        self._request_lease_id: ContextVar[str | None] = ContextVar(
            "v7_publication_request_lease_id", default=None
        )
        self._request_owner_token: ContextVar[str | None] = ContextVar(
            "v7_publication_request_owner_token", default=None
        )
        self.request_lease_ttl_seconds = 120.0

    def resolve_active(self) -> PublicationSnapshot | None:
        """返回当前请求应固定使用的 active publication 快照。

        若 active publication 含有已进入 deleting 的文档版本，新的检索请求
        不得降级读取 legacy generation，必须明确失败关闭；已在此前固定的
        请求快照仍由 ContextVar 保持不变。
        """
        snapshot = self.repository.get_active_publication()
        if snapshot is None:
            return None
        with self.repository.store.connect() as connection:
            deleting = connection.execute(
                """SELECT version.document_version_id
                FROM v7_publication_document_versions AS publication_document
                JOIN v7_document_versions AS version
                    ON version.document_version_id = publication_document.document_version_id
                WHERE publication_document.publication_id = ?
                    AND version.index_status = 'deleting'
                ORDER BY version.document_version_id
                LIMIT 1""",
                (snapshot.publication_id,),
            ).fetchone()
        if deleting is not None:
            raise V7PublicationDeletingDocumentError(
                f"active publication 包含 deleting document_version_id: {deleting[0]}"
            )
        return snapshot

    def begin_request(self) -> PublicationSnapshot | None:
        """请求开始：捕获当前 active 快照并固定，请求期间保持不变。

        请求期间即使激活了新 publication，本请求仍读取 begin 时固定的快照；
        无 active publication 时固定 None 并返回 None，不抛错。
        """
        snapshot = self.resolve_active()
        self._request_snapshot.set(snapshot)
        if snapshot is not None:
            owner_token = str(uuid.uuid4())
            lease_id = self.repository.acquire_request_lease(
                snapshot.publication_id,
                owner_token,
                ttl_seconds=self.request_lease_ttl_seconds,
            )
            self._request_lease_id.set(lease_id)
            self._request_owner_token.set(owner_token)
        return snapshot

    def current_snapshot(self) -> PublicationSnapshot | None:
        """返回当前请求固定的快照；未处于请求作用域时返回 None。"""
        return self._request_snapshot.get()

    def resolve_generation_id(self) -> str | None:
        """返回当前请求快照的 generation_id；无请求或无快照时返回 None。

        索引、文档、artifact、事实查询应统一从该代际读取，保证同一请求内视图一致。
        """
        snapshot = self.current_snapshot()
        return snapshot.generation_id if snapshot is not None else None

    def end_request(self) -> None:
        """请求结束：释放固定快照。"""
        lease_id = self._request_lease_id.get()
        if lease_id is not None:
            self.repository.release_request_lease(lease_id)
        self._request_lease_id.set(None)
        self._request_owner_token.set(None)
        self._request_snapshot.set(None)

    @contextmanager
    def request_scope(self):
        """请求作用域：进入固定快照，退出时无论成败均释放。"""
        snapshot = self.begin_request()
        try:
            yield snapshot
        finally:
            self.end_request()
