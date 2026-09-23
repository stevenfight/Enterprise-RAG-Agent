# -*- coding: utf-8 -*-
"""M-T41 文档删除线性化点与新查询可见性测试。"""


def _register_active_document(tmp_path):
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    repository = V7DocumentRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"), tmp_path / "blobs")
    version = repository.register_document_version(
        logical_document_key="annual-report",
        display_name="年度报告",
        original_filename="annual-report.pdf",
        file_content=b"%PDF-1.7\nfixture",
        physical_page_count=1,
    )
    repository.promote_document_version_to_active(version.document_version_id)
    return repository, version


def test_deletion_linearization_hides_active_version_from_new_query_and_preserves_old_snapshot(tmp_path):
    """删除事务提交后，新查询不再取得版本；已固定的旧快照保持其原始身份。"""
    from src.v7_document_deletion_lifecycle import (
        V7DocumentDeletionLifecycle,
        V7DocumentVersionVisibilityResolver,
    )

    repository, version = _register_active_document(tmp_path)
    resolver = V7DocumentVersionVisibilityResolver(repository.store)

    assert resolver.begin_query(version.logical_document_id) == version.document_version_id
    assert resolver.current_document_version_id() == version.document_version_id
    lifecycle = V7DocumentDeletionLifecycle(repository.store)
    result = lifecycle.begin_deletion(version.document_version_id)

    assert result.changed is True
    assert result.previous_status == "active"
    assert resolver.current_document_version_id() == version.document_version_id
    resolver.end_query()
    assert resolver.begin_query(version.logical_document_id) is None
    assert repository.get_active_document_version(version.logical_document_id) is None
    with repository.store.connect() as connection:
        status = connection.execute(
            "SELECT index_status FROM v7_document_versions WHERE document_version_id = ?",
            (version.document_version_id,),
        ).fetchone()[0]
        invalidation = connection.execute(
            "SELECT reason FROM v7_document_version_invalidations WHERE document_version_id = ?",
            (version.document_version_id,),
        ).fetchone()[0]
    assert status == "deleting"
    assert invalidation == "deletion_requested"


def test_deletion_linearization_is_idempotent_and_blob_resolution_refuses_deleting_version(tmp_path):
    """重复请求不改变线性化结果，删除中的版本不能再被按 ID 解析原始 blob。"""
    import pytest

    from src.v7_document_deletion_lifecycle import V7DocumentDeletionLifecycle

    repository, version = _register_active_document(tmp_path)
    lifecycle = V7DocumentDeletionLifecycle(repository.store)

    assert lifecycle.begin_deletion(version.document_version_id).changed is True
    repeated = lifecycle.begin_deletion(version.document_version_id)
    assert repeated.changed is False
    assert repeated.previous_status == "deleting"
    with pytest.raises(ValueError, match="删除中"):
        repository.resolve_document_blob_path(version.document_version_id)


def test_new_publication_request_fails_closed_when_active_snapshot_contains_deleting_version(tmp_path):
    """已删除线性化的文档仍在 active publication 时，新请求不得回退到 legacy generation。"""
    import json
    import pytest

    from src.publication_set import PublicationResolver, PublicationSetRepository
    from src.v7_document_deletion_lifecycle import (
        V7DocumentDeletionLifecycle,
        V7PublicationDeletingDocumentError,
    )

    repository, version = _register_active_document(tmp_path)
    with repository.store.connect() as connection:
        connection.execute(
            """INSERT INTO v7_generation_candidates(
                generation_id, corpus_revision, status, payload_json, validation_json
            ) VALUES ('generation-1', 'revision-1', 'validated', ?, ?)""",
            (
                json.dumps({"document_version_ids": [version.document_version_id]}),
                json.dumps({"status": "validated", "artifact_manifest": [{"name": "index.faiss"}]}),
            ),
        )
        connection.execute(
            "INSERT INTO v7_publication_sets(publication_id, generation_id, corpus_revision) VALUES ('publication-1', 'generation-1', 'revision-1')"
        )
        connection.execute(
            "INSERT INTO v7_publication_document_versions VALUES ('publication-1', ?)",
            (version.document_version_id,),
        )
        connection.execute(
            "INSERT INTO v7_active_publication(singleton_id, publication_id) VALUES (1, 'publication-1')"
        )
        connection.commit()
    resolver = PublicationResolver(PublicationSetRepository(repository.store))
    old_snapshot = resolver.begin_request()
    resolver.end_request()

    V7DocumentDeletionLifecycle(repository.store).begin_deletion(version.document_version_id)

    with pytest.raises(V7PublicationDeletingDocumentError, match="deleting"):
        resolver.begin_request()
    assert old_snapshot.document_version_ids == (version.document_version_id,)
    assert resolver.current_snapshot() is None


def test_deletion_records_active_publication_request_lease_until_request_ends(tmp_path):
    """删除线性化会记录已固定 publication 的活动租约，但不会提前物理删除。"""
    import json

    from src.publication_set import PublicationResolver, PublicationSetRepository
    from src.v7_document_deletion_lifecycle import V7DocumentDeletionLifecycle

    repository, version = _register_active_document(tmp_path)
    with repository.store.connect() as connection:
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
    resolver = PublicationResolver(PublicationSetRepository(repository.store))
    assert resolver.begin_request().publication_id == "publication-1"

    result = V7DocumentDeletionLifecycle(repository.store).begin_deletion(version.document_version_id)

    assert result.active_request_lease_count == 1
    resolver.end_request()
    with repository.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM v7_publication_request_leases").fetchone()[0] == 0
