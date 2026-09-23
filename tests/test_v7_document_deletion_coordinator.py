# -*- coding: utf-8 -*-
"""M3.10 已发布文档删除异步状态协调测试。"""

import json

import pytest


def _published_active_document(tmp_path):
    from src.publication_set import PublicationSetRepository
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    document_repository = V7DocumentRepository(store, tmp_path / "blobs")
    version = document_repository.register_document_version(
        logical_document_key="annual-report",
        display_name="年度报告",
        original_filename="annual-report.pdf",
        file_content=b"%PDF-1.7\nfixture",
        physical_page_count=1,
    )
    document_repository.promote_document_version_to_active(version.document_version_id)
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO v7_generation_candidates(
                generation_id, corpus_revision, status, payload_json, validation_json
            ) VALUES ('generation-1', 'revision-1', 'validated', ?, ?)""",
            (json.dumps({"document_version_ids": [version.document_version_id]}), json.dumps({"status": "validated", "artifact_manifest": [{"name": "index.faiss"}]})),
        )
        connection.execute("INSERT INTO v7_publication_sets VALUES ('publication-1', 'generation-1', 'revision-1', CURRENT_TIMESTAMP)")
        connection.execute("INSERT INTO v7_publication_document_versions VALUES ('publication-1', ?)", (version.document_version_id,))
        connection.execute("INSERT INTO v7_active_publication(singleton_id, publication_id) VALUES (1, 'publication-1')")
        connection.commit()
    return store, version, PublicationSetRepository(store)


def test_published_deletion_returns_waiting_status_then_rebuild_required_after_lease_release(tmp_path):
    """已发布版本删除不能提前完成：有 lease 等待，无 lease 后明确要求重建。"""
    from src.publication_set import PublicationResolver
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator

    store, version, publication_repository = _published_active_document(tmp_path)
    resolver = PublicationResolver(publication_repository)
    assert resolver.begin_request().publication_id == "publication-1"
    coordinator = V7DocumentDeletionCoordinator(store)

    waiting = coordinator.request_deletion(version.document_version_id)

    assert waiting.status == "waiting_for_active_requests"
    assert waiting.active_request_lease_count == 1
    resolver.end_request()
    ready = coordinator.refresh_request(version.document_version_id)
    assert ready.status == "rebuild_required"
    assert ready.active_request_lease_count == 0


def test_expired_request_leases_stop_blocking_deletion_progress(tmp_path):
    """过期租约不再计入活动租约；刷新后删除请求进入 rebuild_required。"""
    from src.publication_set import PublicationResolver
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator

    store, version, publication_repository = _published_active_document(tmp_path)
    resolver = PublicationResolver(publication_repository)
    assert resolver.begin_request().publication_id == "publication-1"
    coordinator = V7DocumentDeletionCoordinator(store)
    waiting = coordinator.request_deletion(version.document_version_id)
    assert waiting.status == "waiting_for_active_requests"

    # 模拟租约自然到期：把 expires_at 置为过去时刻
    with store.connect() as connection:
        connection.execute(
            "UPDATE v7_publication_request_leases SET expires_at = CAST(strftime('%s', 'now') AS REAL) - 1"
        )
        connection.commit()

    rebuilt = coordinator.refresh_request(version.document_version_id)
    assert rebuilt.status == "rebuild_required"
    assert rebuilt.active_request_lease_count == 0


def _activate_replacement_publication_excluding_version(store, document_version_id: str) -> None:
    """登记并激活一个不含指定版本的替代 publication（重建链已在别处端到端验证）。"""
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO v7_generation_candidates(
                generation_id, corpus_revision, status, payload_json, validation_json
            ) VALUES ('generation-2', 'revision-2', 'validated', ?, ?)""",
            (
                json.dumps({"document_version_ids": []}),
                json.dumps({"status": "validated", "artifact_manifest": [{"name": "index.faiss"}]}),
            ),
        )
        connection.execute("INSERT INTO v7_publication_sets VALUES ('publication-2', 'generation-2', 'revision-2', CURRENT_TIMESTAMP)")
        connection.execute(
            "UPDATE v7_active_publication SET publication_id = 'publication-2' WHERE singleton_id = 1"
        )
        connection.commit()
    assert document_version_id  # 替代代际的文档集为空，天然不含被删除版本


def test_advance_request_keeps_rebuild_required_until_replacement_publication_active(tmp_path):
    """异步推进：替代 publication 生效前保持 rebuild_required，生效后进入 cleanup_ready。"""
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator

    store, version, _ = _published_active_document(tmp_path)
    coordinator = V7DocumentDeletionCoordinator(store)
    request = coordinator.request_deletion(version.document_version_id)
    assert request.status == "rebuild_required"

    # 替代 publication 未生效：active publication 仍包含被删版本，不得进入清理
    stalled = coordinator.advance_request(version.document_version_id)
    assert stalled.status == "rebuild_required"

    _activate_replacement_publication_excluding_version(store, version.document_version_id)
    ready = coordinator.advance_request(version.document_version_id)
    assert ready.status == "cleanup_ready"
    assert ready.active_request_lease_count == 0

    # 执行器不触碰版本本体：物理清理只能由 M3.11 的零引用与保留期治理推进
    with store.connect() as connection:
        row = connection.execute(
            "SELECT index_status FROM v7_document_versions WHERE document_version_id = ?",
            (version.document_version_id,),
        ).fetchone()
    assert row[0] == "deleting"

    # cleanup_ready 是稳定终态：重复推进与刷新都不降级
    again = coordinator.advance_request(version.document_version_id)
    assert again.status == "cleanup_ready"
    refreshed = coordinator.refresh_request(version.document_version_id)
    assert refreshed.status == "cleanup_ready"


def test_advance_request_returns_waiting_while_unexpired_lease_exists(tmp_path):
    """存在未过期租约时异步推进只回报等待状态，不做任何清理。"""
    from src.publication_set import PublicationResolver
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator

    store, version, publication_repository = _published_active_document(tmp_path)
    resolver = PublicationResolver(publication_repository)
    assert resolver.begin_request().publication_id == "publication-1"
    coordinator = V7DocumentDeletionCoordinator(store)
    assert coordinator.request_deletion(version.document_version_id).status == "waiting_for_active_requests"

    advanced = coordinator.advance_request(version.document_version_id)
    assert advanced.status == "waiting_for_active_requests"
    assert advanced.active_request_lease_count == 1


def _seed_fact_lineage(store, document_version_id: str) -> None:
    """写入 fact/calculation/claim/report 溯源链并关联到指定文档版本。"""
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO v7_financial_facts VALUES ('fact-1', 'revenue', '示例公司', '1', '元', '1', '元', 'CNY', 'FY2024', 'consolidated', '报告.pdf', '[1]', '摘录', CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO v7_fact_calculations VALUES ('calc-1', 'identity', 'v1', '[\"fact-1\"]', '{}', CURRENT_TIMESTAMP)"
        )
        connection.execute("INSERT INTO v7_claims VALUES ('claim-1', '示例声明', CURRENT_TIMESTAMP)")
        connection.commit()
    from src.provenance_repository import ProvenanceRepository

    provenance = ProvenanceRepository(store)
    provenance.link_fact_to_document_version("fact-1", document_version_id)
    provenance.link_calculation_input("calc-1", "fact-1")
    provenance.link_claim_fact("claim-1", "fact-1")
    provenance.link_claim_calculation("claim-1", "calc-1")
    provenance.create_report("report-1", "报告结论")
    provenance.link_report_claim("report-1", "claim-1")


def test_cleanup_request_requires_cleanup_ready_state(tmp_path):
    """删除请求未达到 cleanup_ready 时拒绝执行物理清理。"""
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator
    from src.v7_document_repository import V7DocumentRepository

    store, version, _ = _published_active_document(tmp_path)
    document_repository = V7DocumentRepository(store, tmp_path / "blobs")
    coordinator = V7DocumentDeletionCoordinator(store)

    with pytest.raises(ValueError, match="尚未创建删除请求"):
        coordinator.cleanup_request(version.document_version_id, document_repository)

    coordinator.request_deletion(version.document_version_id)
    with pytest.raises(ValueError, match="cleanup_ready"):
        coordinator.cleanup_request(version.document_version_id, document_repository)


def test_cleanup_request_invalidates_facts_propagates_stale_and_reclaims_blob(tmp_path):
    """cleanup_ready 后物理清理：失效事实可见性、传播 stale、回收独占 blob。"""
    from src.provenance_repository import ProvenanceRepository
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator
    from src.v7_document_repository import V7DocumentRepository

    store, version, _ = _published_active_document(tmp_path)
    document_repository = V7DocumentRepository(store, tmp_path / "blobs")
    _seed_fact_lineage(store, version.document_version_id)
    coordinator = V7DocumentDeletionCoordinator(store)

    coordinator.request_deletion(version.document_version_id)
    # 替代 publication 生效前不得进入物理清理
    with pytest.raises(ValueError, match="cleanup_ready"):
        coordinator.cleanup_request(version.document_version_id, document_repository)

    _activate_replacement_publication_excluding_version(store, version.document_version_id)
    assert coordinator.advance_request(version.document_version_id).status == "cleanup_ready"

    result = coordinator.cleanup_request(
        version.document_version_id, document_repository, retention_seconds=0.0
    )
    assert result["reclaimed"] is True

    with store.connect() as connection:
        # 事实可见性失效：该版本的事实关联行删除
        assert connection.execute(
            "SELECT 1 FROM v7_fact_document_versions WHERE document_version_id = ?",
            (version.document_version_id,),
        ).fetchone() is None
        # 软失效审计记录保留（M3.12 历史审计要求）
        assert connection.execute(
            "SELECT 1 FROM v7_document_version_invalidations WHERE document_version_id = ?",
            (version.document_version_id,),
        ).fetchone() is not None
        # 版本本体保持 deleting：软删除，不物理删行
        assert connection.execute(
            "SELECT index_status FROM v7_document_versions WHERE document_version_id = ?",
            (version.document_version_id,),
        ).fetchone()[0] == "deleting"
        # deleting 版本行的外键引用保护 blob 登记行（文件已物理回收）
        assert connection.execute("SELECT 1 FROM v7_blobs").fetchone() is not None

    provenance = ProvenanceRepository(store)
    assert provenance.get_statuses("calc-1", "claim-1", "report-1") == {
        "calculation_status": "stale",
        "claim_status": "stale",
        "report_status": "stale",
    }
    # 独占 blob 文件已物理回收
    assert not (tmp_path / "blobs" / version.blob_sha256).exists()

    # 请求状态保持 cleanup_ready 终态
    assert coordinator.refresh_request(version.document_version_id).status == "cleanup_ready"


def test_cleanup_request_keeps_shared_blob_while_other_version_holds_reference(tmp_path):
    """共享 blob 在其他版本仍持引用时不回收；删除版本不再计入引用。"""
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator
    from src.v7_document_repository import V7DocumentRepository

    store, version, _ = _published_active_document(tmp_path)
    document_repository = V7DocumentRepository(store, tmp_path / "blobs")
    # 第二个逻辑文档注册相同内容，共享同一内容寻址 blob
    other = document_repository.register_document_version(
        logical_document_key="annual-report-b",
        display_name="年度报告 B",
        original_filename="annual-report-b.pdf",
        file_content=b"%PDF-1.7\nfixture",
        physical_page_count=1,
    )
    assert other.blob_sha256 == version.blob_sha256

    coordinator = V7DocumentDeletionCoordinator(store)
    coordinator.request_deletion(version.document_version_id)
    _activate_replacement_publication_excluding_version(store, version.document_version_id)
    assert coordinator.advance_request(version.document_version_id).status == "cleanup_ready"

    result = coordinator.cleanup_request(
        version.document_version_id, document_repository, retention_seconds=0.0
    )
    assert result["reclaimed"] is False
    # 共享 blob 仍被其他版本持有：文件与登记记录保留
    assert (tmp_path / "blobs" / version.blob_sha256).exists()
    with store.connect() as connection:
        assert connection.execute("SELECT 1 FROM v7_blobs").fetchone() is not None


def test_cleanup_request_keeps_foreign_key_consistency_and_soft_audit(tmp_path):
    """M3.12：物理清理后全库外键一致，软失效审计保留历史。"""
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator
    from src.v7_document_repository import V7DocumentRepository

    store, version, _ = _published_active_document(tmp_path)
    document_repository = V7DocumentRepository(store, tmp_path / "blobs")
    _seed_fact_lineage(store, version.document_version_id)
    coordinator = V7DocumentDeletionCoordinator(store)

    coordinator.request_deletion(version.document_version_id)
    _activate_replacement_publication_excluding_version(store, version.document_version_id)
    assert coordinator.advance_request(version.document_version_id).status == "cleanup_ready"
    coordinator.cleanup_request(
        version.document_version_id, document_repository, retention_seconds=0.0
    )

    with store.connect() as connection:
        # 外键 RESTRICT 下清理链路不产生任何悬空引用
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        # 软失效审计保留历史：删除请求与清理动作各有记录
        assert connection.execute(
            "SELECT 1 FROM v7_document_version_invalidations WHERE document_version_id = ? AND reason = 'document_cleanup'",
            (version.document_version_id,),
        ).fetchone() is not None


def test_reclamation_serializes_with_concurrent_reference_insertion(tmp_path):
    """M3.12：blob 删除资格判定与并发引用变更在同一写锁上串行化。"""
    import threading
    import time

    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    repository = V7DocumentRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"), tmp_path / "blobs")
    registration = repository.register_document_version(
        logical_document_key="company-a", display_name="公司 A", original_filename="a.pdf",
        file_content=b"%PDF-1.7\nshared", physical_page_count=1,
    )
    # 预先物理移除版本行，使回收资格判定只能依赖锁内最新引用
    with repository.store.connect() as connection:
        connection.execute(
            "DELETE FROM v7_document_versions WHERE document_version_id = ?",
            (registration.document_version_id,),
        )
        connection.commit()

    lock_held = threading.Event()

    def hold_lock_then_insert_reference() -> None:
        with repository.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                lock_held.set()
                # 持锁期间插入共享 blob 的新引用（模拟并发上传的引用变更）
                time.sleep(0.05)
                connection.execute(
                    "INSERT INTO v7_logical_documents(logical_document_id, logical_document_key, display_name)"
                    " VALUES ('logical-b', 'company-b', '公司 B')"
                )
                connection.execute(
                    "INSERT INTO v7_document_versions(document_version_id, logical_document_id, blob_sha256,"
                    " original_filename, physical_page_count, index_status)"
                    " VALUES ('version-b', 'logical-b', ?, 'b.pdf', 1, 'pending_index')",
                    (registration.blob_sha256,),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    worker = threading.Thread(target=hold_lock_then_insert_reference)
    worker.start()
    assert lock_held.wait(timeout=5.0)

    # 回收与并发引用变更竞争同一写锁：判定在锁释放后基于最新引用执行
    result = repository.reclaim_blob_if_eligible(
        registration.blob_sha256, retention_seconds=0.0
    )
    worker.join(timeout=5.0)
    assert result is False
    assert (tmp_path / "blobs" / registration.blob_sha256).exists()
