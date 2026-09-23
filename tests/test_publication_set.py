"""M0.13 PublicationSet 与请求级快照解析测试。"""

import hashlib
import json

import pytest


def _seed_validated_generation(store, generation_id="generation-1"):
    """建立已验证 generation 与可见性边界所需的最小溯源记录。"""
    store.initialize()
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO v7_generation_candidates(
                generation_id, corpus_revision, status, payload_json, validation_json
            ) VALUES (?, 'revision-1', 'validated', ?, ?)""",
            (
                generation_id,
                json.dumps({"document_version_ids": ["version-1", "version-2"]}),
                json.dumps({"status": "validated", "artifact_manifest": [{"name": "index.faiss"}]}),
            ),
        )
        for suffix in ("1", "2"):
            sha256 = hashlib.sha256(f"pdf-{suffix}".encode()).hexdigest()
            connection.execute("INSERT INTO v7_blobs(sha256, size_bytes) VALUES (?, 1)", (sha256,))
            connection.execute(
                """INSERT INTO v7_logical_documents(
                    logical_document_id, logical_document_key, display_name
                ) VALUES (?, ?, ?)""",
                (f"logical-{suffix}", f"document-{suffix}", f"报告{suffix}"),
            )
            connection.execute(
                """INSERT INTO v7_document_versions(
                    document_version_id, logical_document_id, blob_sha256,
                    original_filename, physical_page_count, index_status
                ) VALUES (?, ?, ?, ?, 1, 'active')""",
                (f"version-{suffix}", f"logical-{suffix}", sha256, f"报告{suffix}.pdf"),
            )
            connection.execute(
                "INSERT INTO v7_generation_documents VALUES (?, ?, ?)",
                (generation_id, f"version-{suffix}", sha256),
            )
        connection.execute(
            "INSERT INTO v7_document_asset_manifests VALUES ('manifest-1', 'version-1', 'a', 1, 'complete', 1, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            """INSERT INTO v7_page_artifacts(
                page_artifact_id, manifest_id, physical_page_number, artifact_kind,
                content_sha256, artifact_status
            ) VALUES ('artifact-1', 'manifest-1', 1, 'page_image', 'b', 'complete')"""
        )
        connection.execute(
            """INSERT INTO v7_financial_facts(
                fact_id, metric_key, company_name, raw_value, raw_unit,
                normalized_value, normalized_unit, currency, period, scope,
                source_file, physical_pages_json, excerpt
            ) VALUES ('fact-1', 'revenue', '示例公司', '1', '元', '1', '元', 'CNY',
                '2025', 'consolidated', '报告1.pdf', '[1]', '示例')"""
        )
        connection.execute("INSERT INTO v7_fact_document_versions VALUES ('fact-1', 'version-1')")
        connection.commit()


def test_publication_set_uses_sqlite_as_the_only_active_truth(tmp_path):
    from src.publication_set import PublicationResolver, PublicationSetError, PublicationSetRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store)
    repository = PublicationSetRepository(store)

    publication = repository.create_publication(
        "publication-1",
        "generation-1",
        document_version_ids=["version-1", "version-2"],
        page_artifact_ids=["artifact-1"],
        fact_ids=["fact-1"],
    )
    assert PublicationResolver(repository).resolve_active() is None
    with pytest.raises(PublicationSetError, match="expected revision"):
        repository.activate_publication("publication-1")

    repository.prepare_publication_build("publication-1", None, None)
    repository.activate_publication("publication-1")
    snapshot = PublicationResolver(repository).resolve_active()

    assert publication.publication_id == "publication-1"
    assert snapshot.publication_id == "publication-1"
    assert snapshot.generation_id == "generation-1"
    assert snapshot.corpus_revision == "revision-1"
    assert snapshot.document_version_ids == ("version-1", "version-2")
    assert snapshot.page_artifact_ids == ("artifact-1",)
    assert snapshot.fact_ids == ("fact-1",)


def test_publication_rejects_unvalidated_generation_and_out_of_boundary_records(tmp_path):
    from src.publication_set import PublicationSetError, PublicationSetRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store)
    repository = PublicationSetRepository(store)
    with store.connect() as connection:
        connection.execute("UPDATE v7_generation_candidates SET status = 'candidate'")
        connection.commit()

    with pytest.raises(PublicationSetError, match="validated"):
        repository.create_publication("publication-1", "generation-1", ["version-1", "version-2"])

    with store.connect() as connection:
        connection.execute("UPDATE v7_generation_candidates SET status = 'validated'")
        connection.commit()
    with pytest.raises(PublicationSetError, match="文档边界"):
        repository.create_publication("publication-1", "generation-1", ["version-1"])
    with pytest.raises(PublicationSetError, match="制品"):
        repository.create_publication(
            "publication-1", "generation-1", ["version-1", "version-2"], ["unknown-artifact"]
        )
    with pytest.raises(PublicationSetError, match="事实"):
        repository.create_publication(
            "publication-1", "generation-1", ["version-1", "version-2"], fact_ids=["unknown-fact"]
        )
    with store.connect() as connection:
        connection.execute("UPDATE v7_generation_candidates SET validation_json = '{}'")
        connection.commit()
    with pytest.raises(PublicationSetError, match="索引制品"):
        repository.create_publication("publication-1", "generation-1", ["version-1", "version-2"])


def test_request_snapshot_remains_stable_after_later_publication_activation(tmp_path):
    from src.publication_set import PublicationResolver, PublicationSetRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store, "generation-1")
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO v7_generation_candidates(
                generation_id, corpus_revision, status, payload_json, validation_json
            ) VALUES ('generation-2', 'revision-2', 'validated', '{}', ?)""",
            (json.dumps({"status": "validated", "artifact_manifest": [{"name": "index.faiss"}]}),),
        )
        for version_id, sha256 in connection.execute(
            "SELECT document_version_id, blob_sha256 FROM v7_document_versions ORDER BY document_version_id"
        ).fetchall():
            connection.execute("INSERT INTO v7_generation_documents VALUES ('generation-2', ?, ?)", (version_id, sha256))
        connection.commit()

    repository = PublicationSetRepository(store)
    repository.create_publication("publication-1", "generation-1", ["version-1", "version-2"])
    repository.prepare_publication_build("publication-1", None, None)
    repository.activate_publication("publication-1")
    request_snapshot = PublicationResolver(repository).resolve_active()
    repository.create_publication("publication-2", "generation-2", ["version-1", "version-2"])
    repository.prepare_publication_build("publication-2", "publication-1", "revision-1")
    repository.activate_publication("publication-2")

    assert request_snapshot.publication_id == "publication-1"
    assert PublicationResolver(repository).resolve_active().publication_id == "publication-2"


def test_concurrent_publications_with_same_expected_revision_allow_only_one(tmp_path):
    from src.publication_set import PublicationSetError, PublicationSetRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store, "generation-1")
    with store.connect() as connection:
        for generation_id, revision in (("generation-2", "revision-2"), ("generation-3", "revision-3")):
            connection.execute(
                """INSERT INTO v7_generation_candidates(
                    generation_id, corpus_revision, status, payload_json, validation_json
                ) VALUES (?, ?, 'validated', '{}', ?)""",
                (generation_id, revision, json.dumps({"status": "validated", "artifact_manifest": [{"name": "index.faiss"}]})),
            )
            for version_id, sha256 in connection.execute(
                "SELECT document_version_id, blob_sha256 FROM v7_document_versions ORDER BY document_version_id"
            ).fetchall():
                connection.execute("INSERT INTO v7_generation_documents VALUES (?, ?, ?)", (generation_id, version_id, sha256))
        connection.commit()

    repository = PublicationSetRepository(store)
    repository.create_publication("publication-1", "generation-1", ["version-1", "version-2"])
    repository.prepare_publication_build("publication-1", None, None)
    repository.activate_publication("publication-1")
    for publication_id, generation_id in (("publication-2", "generation-2"), ("publication-3", "generation-3")):
        repository.create_publication(publication_id, generation_id, ["version-1", "version-2"])
        repository.prepare_publication_build(publication_id, "publication-1", "revision-1")

    repository.activate_publication("publication-2")
    with pytest.raises(PublicationSetError, match="superseded"):
        repository.activate_publication("publication-3")

    assert repository.get_active_publication().publication_id == "publication-2"
    assert repository.get_publication_build("publication-3")["status"] == "superseded"


def test_publish_transaction_failure_keeps_new_publication_invisible(tmp_path):
    from src.publication_set import PublicationSetRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store, "generation-1")
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO v7_generation_candidates(
                generation_id, corpus_revision, status, payload_json, validation_json
            ) VALUES ('generation-2', 'revision-2', 'validated', '{}', ?)""",
            (json.dumps({"status": "validated", "artifact_manifest": [{"name": "index.faiss"}]}),),
        )
        for version_id, sha256 in connection.execute(
            "SELECT document_version_id, blob_sha256 FROM v7_document_versions ORDER BY document_version_id"
        ).fetchall():
            connection.execute("INSERT INTO v7_generation_documents VALUES ('generation-2', ?, ?)", (version_id, sha256))
        connection.commit()

    repository = PublicationSetRepository(store)
    repository.create_publication("publication-1", "generation-1", ["version-1", "version-2"])
    repository.prepare_publication_build("publication-1", None, None)
    repository.activate_publication("publication-1")
    repository.create_publication("publication-2", "generation-2", ["version-1", "version-2"])
    repository.prepare_publication_build("publication-2", "publication-1", "revision-1")
    with store.connect() as connection:
        connection.execute(
            """CREATE TRIGGER reject_publication_build_completion
            BEFORE UPDATE OF status ON v7_publication_builds
            WHEN NEW.publication_id = 'publication-2' AND NEW.status = 'published'
            BEGIN SELECT RAISE(ABORT, 'injected publication failure'); END"""
        )
        connection.commit()

    with pytest.raises(Exception, match="injected publication failure"):
        repository.activate_publication("publication-2")

    assert repository.get_active_publication().publication_id == "publication-1"
    assert repository.get_publication_build("publication-2")["status"] == "prepared"


def test_resolver_request_scope_pins_snapshot_and_refreshes_next_request(tmp_path):
    """M-T46：请求开始固定 publication 快照，请求期间激活新 publication 不影响本请求。"""
    from src.publication_set import PublicationResolver, PublicationSetRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store, "generation-1")
    repository = PublicationSetRepository(store)
    repository.create_publication(
        "publication-1", "generation-1", ["version-1", "version-2"], ["artifact-1"], ["fact-1"]
    )
    repository.prepare_publication_build("publication-1", None, None)
    repository.activate_publication("publication-1")

    resolver = PublicationResolver(repository)
    snapshot = resolver.begin_request()
    assert snapshot.publication_id == "publication-1"
    assert resolver.current_snapshot() is snapshot
    assert resolver.resolve_generation_id() == "generation-1"

    # 请求期间激活新 publication：本请求固定快照保持不变
    repository.create_publication(
        "publication-2", "generation-1", ["version-1", "version-2"], ["artifact-1"], ["fact-1"]
    )
    repository.prepare_publication_build("publication-2", "publication-1", "revision-1")
    repository.activate_publication("publication-2")
    assert resolver.current_snapshot().publication_id == "publication-1"

    # 请求结束释放，下一次请求读取到新激活的 publication
    resolver.end_request()
    assert resolver.current_snapshot() is None
    assert resolver.resolve_generation_id() is None
    with resolver.request_scope() as scoped_snapshot:
        assert scoped_snapshot.publication_id == "publication-2"
    assert resolver.current_snapshot() is None


def test_resolver_request_scope_without_active_publication_returns_none(tmp_path):
    """M-T46：无 active publication 时请求作用域返回 None，不抛错。"""
    from src.publication_set import PublicationResolver, PublicationSetRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store, "generation-1")
    resolver = PublicationResolver(PublicationSetRepository(store))

    assert resolver.begin_request() is None
    assert resolver.current_snapshot() is None
    resolver.end_request()
    with resolver.request_scope() as scoped_snapshot:
        assert scoped_snapshot is None
    assert resolver.current_snapshot() is None


def test_rollback_creates_new_publication_for_the_entire_previous_snapshot(tmp_path):
    from src.publication_set import PublicationSetRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store)
    repository = PublicationSetRepository(store)
    repository.create_publication(
        "publication-1", "generation-1", ["version-1", "version-2"], ["artifact-1"], ["fact-1"]
    )
    repository.prepare_publication_build("publication-1", None, None)
    repository.activate_publication("publication-1")

    rollback = repository.rollback_to_publication("publication-rollback-1", "publication-1")

    assert rollback.publication_id == "publication-rollback-1"
    assert rollback.generation_id == "generation-1"
    assert rollback.page_artifact_ids == ("artifact-1",)
    assert rollback.fact_ids == ("fact-1",)
    assert repository.get_active_publication().publication_id == "publication-rollback-1"
    with store.connect() as connection:
        audit = connection.execute(
            """SELECT restored_publication_id, replaced_publication_id
            FROM v7_publication_rollbacks WHERE rollback_publication_id = 'publication-rollback-1'"""
        ).fetchone()
    assert audit == ("publication-1", "publication-1")
