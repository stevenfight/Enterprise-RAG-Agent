"""M0.7～M0.9 候选 generation 迁移与审计测试。"""

import hashlib
import json

import pytest


def _seed_active_documents(store) -> None:
    """建立两个 active 文档版本，模拟固定迁移基线。"""
    store.initialize()
    with store.connect() as connection:
        for suffix in ("1", "2"):
            sha256 = hashlib.sha256(f"pdf-{suffix}".encode()).hexdigest()
            connection.execute("INSERT INTO v7_blobs(sha256, size_bytes) VALUES (?, 1)", (sha256,))
            connection.execute(
                "INSERT INTO v7_logical_documents(logical_document_id, logical_document_key, display_name) VALUES (?, ?, ?)",
                (f"logical-{suffix}", f"report-{suffix}", f"报告{suffix}"),
            )
            connection.execute(
                "INSERT INTO v7_document_versions(document_version_id, logical_document_id, blob_sha256, original_filename, physical_page_count, index_status) VALUES (?, ?, ?, ?, 1, 'active')",
                (f"version-{suffix}", f"logical-{suffix}", sha256, f"报告{suffix}.pdf"),
            )
        connection.commit()


def _chunks() -> list[dict]:
    return [
        {
            "chunk_id": "chunk-1", "document_version_id": "version-1", "text_sha256": "a" * 64,
            "parser_version": "mineru-v4", "splitter_version": "split-v2", "preprocess_version": "prep-v1",
            "embedding_model": "text-embedding-v3", "embedding_version": "2026-08", "vector_dimension": 1024,
            "schema_version": 1,
        },
        {
            "chunk_id": "chunk-2", "document_version_id": "version-2", "text_sha256": "b" * 64,
            "parser_version": "mineru-v4", "splitter_version": "split-v2", "preprocess_version": "prep-v1",
            "embedding_model": "text-embedding-v3", "embedding_version": "2026-08", "vector_dimension": 1024,
            "schema_version": 1,
        },
    ]


def test_candidate_generation_covers_every_active_document_and_is_not_active(tmp_path):
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)

    result = migrator.build_candidate("generation-1", _chunks())

    assert result["status"] == "candidate"
    assert result["document_version_ids"] == ["version-1", "version-2"]
    assert result["corpus_revision"]
    assert migrator.get_candidate("generation-1")["status"] == "candidate"
    with store.connect() as connection:
        audit_types = {
            row[0] for row in connection.execute(
                "SELECT audit_type FROM v7_generation_migration_audit WHERE generation_id = 'generation-1'"
            ).fetchall()
        }
    assert {"baseline_frozen", "chunk_migration_decision", "provenance_foreign_key_check", "publication_boundary"}.issubset(audit_types)


def test_missing_old_vector_evidence_requires_reembedding_instead_of_reuse(tmp_path):
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    chunks = _chunks()
    chunks[1].pop("embedding_version")

    result = V7GenerationMigrator(store).build_candidate("generation-1", chunks)

    assert result["chunk_actions"] == {"chunk-1": "reuse_eligible", "chunk-2": "reembed_required"}


def test_candidate_rejects_incomplete_active_document_coverage(tmp_path):
    from src.v7_generation_migration import GenerationMigrationError, V7GenerationMigrator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)

    with pytest.raises(GenerationMigrationError, match="覆盖"):
        V7GenerationMigrator(store).build_candidate("generation-1", _chunks()[:1])


def test_validation_records_hash_dimension_and_sample_retrieval_without_publishing_legacy_pointer(tmp_path):
    from src.v7_generation_migration import GenerationMigrationError, V7GenerationMigrator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    migrator.build_candidate("generation-1", _chunks())
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    for name in ("index.faiss", "bm25_index.pkl"):
        (artifacts / name).write_bytes(name.encode())
    (artifacts / "metadata.json").write_text("[]", encoding="utf-8")
    (artifacts / "parent_texts.json").write_text("{}", encoding="utf-8")
    active_pointer = tmp_path / "legacy-active.json"
    active_pointer.write_text(json.dumps({"generation_id": "legacy"}), encoding="utf-8")

    validation = migrator.validate_candidate(
        "generation-1", artifacts, sample_retriever=lambda: ["chunk-1"], legacy_active_pointer=active_pointer,
    )

    assert validation["status"] == "validated"
    assert validation["vector_dimension"] == 1024
    assert json.loads(active_pointer.read_text(encoding="utf-8"))["generation_id"] == "legacy"
    (artifacts / "metadata.json").write_bytes(b"changed")
    with pytest.raises(GenerationMigrationError, match="哈希"):
        migrator.validate_candidate(
            "generation-1", artifacts, sample_retriever=lambda: ["chunk-1"], legacy_active_pointer=active_pointer,
        )
    assert json.loads(active_pointer.read_text(encoding="utf-8"))["generation_id"] == "legacy"
    assert migrator.get_candidate("generation-1")["status"] == "validation_failed"
    with store.connect() as connection:
        failure = connection.execute(
            "SELECT payload_json FROM v7_generation_migration_audit WHERE generation_id = 'generation-1' AND audit_type = 'validation_failed'"
        ).fetchone()
    assert "哈希" in failure[0]


def test_validation_rejects_invalid_bm25_faiss_metadata_sidecar(tmp_path):
    from src.v7_generation_migration import GenerationMigrationError, V7GenerationMigrator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    migrator.build_candidate("generation-1", _chunks())
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "index.faiss").write_bytes(b"index")
    (artifacts / "bm25_index.pkl").write_bytes(b"bm25")
    (artifacts / "metadata.json").write_text("not-json", encoding="utf-8")
    (artifacts / "parent_texts.json").write_text("{}", encoding="utf-8")

    with pytest.raises(GenerationMigrationError, match="metadata"):
        migrator.validate_candidate("generation-1", artifacts, sample_retriever=lambda: ["chunk-1"])


def test_candidate_replay_is_idempotent_but_conflicting_payload_is_rejected(tmp_path):
    from src.v7_generation_migration import GenerationMigrationError, V7GenerationMigrator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    migrator.build_candidate("generation-1", _chunks())
    migrator.build_candidate("generation-1", _chunks())
    changed = _chunks()
    changed[0]["text_sha256"] = "c" * 64
    with pytest.raises(GenerationMigrationError, match="不一致"):
        migrator.build_candidate("generation-1", changed)


def test_excluding_indexed_document_builds_candidate_without_changing_active_publication(tmp_path):
    """已索引文档只能先从候选代际排除，不能原地破坏当前发布集。"""
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    migrator.build_candidate("generation-active", _chunks())
    with store.connect() as connection:
        connection.execute("UPDATE v7_generation_candidates SET status = 'validated' WHERE generation_id = 'generation-active'")
        connection.execute(
            """INSERT INTO v7_publication_sets(publication_id, generation_id, corpus_revision)
            VALUES ('publication-active', 'generation-active', 'revision-active')"""
        )
        connection.execute("INSERT INTO v7_active_publication(singleton_id, publication_id) VALUES (1, 'publication-active')")
        connection.commit()

    result = migrator.build_candidate_excluding_document(
        "generation-without-version-2", "version-2", _chunks()[:1]
    )

    assert result["status"] == "candidate"
    assert result["document_version_ids"] == ["version-1"]
    with store.connect() as connection:
        active_publication = connection.execute(
            "SELECT publication_id FROM v7_active_publication WHERE singleton_id = 1"
        ).fetchone()
        document_status = connection.execute(
            "SELECT index_status FROM v7_document_versions WHERE document_version_id = 'version-2'"
        ).fetchone()
        exclusion = connection.execute(
            """SELECT payload_json FROM v7_generation_migration_audit
            WHERE generation_id = 'generation-without-version-2' AND audit_type = 'document_exclusion_planned'"""
        ).fetchone()
    assert active_publication == ("publication-active",)
    assert document_status == ("active",)
    assert json.loads(exclusion[0]) == {"excluded_document_version_id": "version-2"}
