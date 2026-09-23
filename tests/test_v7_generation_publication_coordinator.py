"""M1.8 候选 generation staging 验证与发布准备测试。"""

import hashlib

import pytest


def _seed_active_documents(store) -> None:
    store.initialize()
    with store.connect() as connection:
        for suffix in ("1", "2"):
            sha256 = hashlib.sha256(f"pdf-{suffix}".encode()).hexdigest()
            connection.execute("INSERT INTO v7_blobs(sha256, size_bytes) VALUES (?, 1)", (sha256,))
            connection.execute(
                "INSERT INTO v7_logical_documents VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (f"logical-{suffix}", f"report-{suffix}", f"报告{suffix}"),
            )
            connection.execute(
                """INSERT INTO v7_document_versions(
                    document_version_id, logical_document_id, blob_sha256,
                    original_filename, physical_page_count, index_status
                ) VALUES (?, ?, ?, ?, 1, 'active')""",
                (f"version-{suffix}", f"logical-{suffix}", sha256, f"报告{suffix}.pdf"),
            )
        connection.commit()


def _chunk(version_id: str) -> dict:
    return {
        "chunk_id": f"chunk-{version_id}",
        "document_version_id": version_id,
        "text_sha256": hashlib.sha256(version_id.encode()).hexdigest(),
        "parser_version": "mineru-v4",
        "splitter_version": "split-v2",
        "preprocess_version": "prep-v1",
        "embedding_model": "text-embedding-v3",
        "embedding_version": "2026-08",
        "vector_dimension": 1024,
        "schema_version": 1,
    }


def _write_staging_artifacts(artifact_root) -> None:
    artifact_root.mkdir()
    (artifact_root / "index.faiss").write_bytes(b"index")
    (artifact_root / "bm25_index.pkl").write_bytes(b"bm25")
    (artifact_root / "metadata.json").write_text("[]", encoding="utf-8")
    (artifact_root / "parent_texts.json").write_text("{}", encoding="utf-8")


def test_staging_validation_prepares_new_publication_without_changing_active(tmp_path):
    """候选制品验证成功后只能进入 prepared，不能自动切换 active publication。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_publication_coordinator import V7GenerationPublicationCoordinator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    migrator.build_candidate("generation-active", [_chunk("version-1"), _chunk("version-2")])
    with store.connect() as connection:
        connection.execute("UPDATE v7_generation_candidates SET status = 'validated' WHERE generation_id = 'generation-active'")
        connection.execute(
            """INSERT INTO v7_publication_sets(publication_id, generation_id, corpus_revision)
            VALUES ('publication-active', 'generation-active', 'revision-active')"""
        )
        connection.execute("INSERT INTO v7_active_publication(singleton_id, publication_id) VALUES (1, 'publication-active')")
        connection.commit()
    migrator.build_candidate_excluding_document(
        "generation-without-version-2", "version-2", [_chunk("version-1")]
    )
    artifact_root = tmp_path / "staging-artifacts"
    _write_staging_artifacts(artifact_root)

    result = V7GenerationPublicationCoordinator(
        migrator, PublicationSetRepository(store)
    ).validate_and_prepare_publication(
        "publication-without-version-2",
        "generation-without-version-2",
        artifact_root,
        sample_retriever=lambda: ["chunk-version-1"],
    )

    assert result.publication_id == "publication-without-version-2"
    assert result.document_version_ids == ("version-1",)
    assert PublicationSetRepository(store).get_publication_build(result.publication_id)["status"] == "prepared"
    assert PublicationSetRepository(store).get_active_publication().publication_id == "publication-active"


def _prepare_publication(coordinator, migrator, publication_id: str, generation_id: str, chunk_ids: list[str], artifact_root) -> None:
    coordinator.validate_and_prepare_publication(
        publication_id,
        generation_id,
        artifact_root,
        sample_retriever=lambda: chunk_ids,
    )


def test_explicit_activation_switches_active_with_matching_baseline(tmp_path):
    """协调器显式激活入口在 CAS 基线匹配时切换唯一 active publication。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_publication_coordinator import V7GenerationPublicationCoordinator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    migrator.build_candidate("generation-1", [_chunk("version-1"), _chunk("version-2")])
    artifact_root = tmp_path / "staging-artifacts-1"
    _write_staging_artifacts(artifact_root)
    coordinator = V7GenerationPublicationCoordinator(migrator, PublicationSetRepository(store))

    _prepare_publication(coordinator, migrator, "publication-1", "generation-1", ["chunk-version-1", "chunk-version-2"], artifact_root)
    snapshot = coordinator.activate_prepared_publication("publication-1")

    assert snapshot.publication_id == "publication-1"
    assert PublicationSetRepository(store).get_active_publication().publication_id == "publication-1"
    assert PublicationSetRepository(store).get_publication_build("publication-1")["status"] == "published"


def test_stale_baseline_activation_is_superseded_and_keeps_active(tmp_path):
    """基线在准备与激活之间被并发发布覆盖时，激活必须得到 superseded 且 active 保持不变。"""
    from src.publication_set import PublicationSetRepository, PublicationSetError
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_publication_coordinator import V7GenerationPublicationCoordinator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    migrator.build_candidate("generation-1", [_chunk("version-1"), _chunk("version-2")])
    migrator.build_candidate("generation-2", [_chunk("version-1"), _chunk("version-2")])
    migrator.build_candidate("generation-3", [_chunk("version-1"), _chunk("version-2")])
    artifact_root_1 = tmp_path / "staging-artifacts-1"
    artifact_root_2 = tmp_path / "staging-artifacts-2"
    artifact_root_3 = tmp_path / "staging-artifacts-3"
    _write_staging_artifacts(artifact_root_1)
    _write_staging_artifacts(artifact_root_2)
    _write_staging_artifacts(artifact_root_3)
    coordinator = V7GenerationPublicationCoordinator(migrator, PublicationSetRepository(store))

    _prepare_publication(coordinator, migrator, "publication-1", "generation-1", ["chunk-version-1", "chunk-version-2"], artifact_root_1)
    coordinator.activate_prepared_publication("publication-1")
    _prepare_publication(coordinator, migrator, "publication-2", "generation-2", ["chunk-version-1", "chunk-version-2"], artifact_root_2)
    # 并发发布者以相同基线抢先完成激活
    _prepare_publication(coordinator, migrator, "publication-3", "generation-3", ["chunk-version-1", "chunk-version-2"], artifact_root_3)
    coordinator.activate_prepared_publication("publication-3")

    with pytest.raises(PublicationSetError):
        coordinator.activate_prepared_publication("publication-2")

    assert PublicationSetRepository(store).get_active_publication().publication_id == "publication-3"
    build = PublicationSetRepository(store).get_publication_build("publication-2")
    assert build["status"] == "superseded"
    assert "publication-3" in build["superseded_reason"]
