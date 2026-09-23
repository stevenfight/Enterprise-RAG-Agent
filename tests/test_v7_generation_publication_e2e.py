# -*- coding: utf-8 -*-
"""M1.8.e 端到端编排：排除文档候选 → 构建发布 → 绑定 → CAS 准备 → 显式激活 → 回收资格与整组回滚。"""

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


def _write_artifacts(directory) -> None:
    directory.mkdir(parents=True)
    (directory / "index.faiss").write_bytes(b"faiss")
    (directory / "bm25_index.pkl").write_bytes(b"bm25")
    (directory / "metadata.json").write_text("[]", encoding="utf-8")
    (directory / "parent_texts.json").write_text("{}", encoding="utf-8")


def _backdate_generation(store, generation_id: str) -> None:
    """把候选代际的 created_at 回拨，使保留期条件必然满足。"""
    with store.connect() as connection:
        connection.execute(
            "UPDATE v7_generation_candidates SET created_at = '2026-01-01 00:00:00' WHERE generation_id = ?",
            (generation_id,),
        )
        connection.commit()


def test_full_chain_activates_new_publication_and_marks_old_generation_retirable(tmp_path):
    """全链路：排除文档候选经实际发布、绑定、准备、显式激活后，旧代际获得回收资格；整组回滚后失格。"""
    from src.index_publication import IndexPublicationManager
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_publication_coordinator import V7GenerationPublicationCoordinator
    from src.v7_generation_retirement import V7GenerationRetirementEvaluator
    from src.v7_index_generation_binding import V7IndexGenerationBinder
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    repository = PublicationSetRepository(store)
    coordinator = V7GenerationPublicationCoordinator(migrator, repository)
    evaluator = V7GenerationRetirementEvaluator(store, repository)

    # 1. 旧代际：覆盖两个 active 文档版本，验证并激活为初始发布
    migrator.build_candidate("generation-old", [_chunk("version-1"), _chunk("version-2")])
    old_artifacts = tmp_path / "old-artifacts"
    _write_artifacts(old_artifacts)
    coordinator.validate_and_prepare_publication(
        "publication-old",
        "generation-old",
        old_artifacts,
        sample_retriever=lambda: ["chunk-version-1", "chunk-version-2"],
    )
    coordinator.activate_prepared_publication("publication-old")
    assert repository.get_active_publication().publication_id == "publication-old"

    # 2. 排除 version-1 构建新候选代际
    migrator.build_candidate_excluding_document("generation-new", "version-1", [_chunk("version-2")])

    # 3. 实际索引管理器构建并发布 staging generation（内容只含 version-2）
    def _builder(staging_company):
        staging_company.mkdir(parents=True)
        (staging_company / "index.faiss").write_bytes(b"faiss-new")
        (staging_company / "bm25_index.pkl").write_bytes(b"bm25-new")
        (staging_company / "metadata.json").write_text("[]", encoding="utf-8")
        (staging_company / "parent_texts.json").write_text("{}", encoding="utf-8")
        return {"doc_count": 1, "source": "builder"}

    manager = IndexPublicationManager(tmp_path / "index_root")
    published = manager.build_and_publish("招商银行", _builder)
    published_dir = manager.generations_dir / published.generation_id / "招商银行"

    # 4. 绑定：把已发布代际制品固化为 V7 候选的不可变 hash/size manifest
    binder = V7IndexGenerationBinder(manager, migrator)
    binder.bind_published_generation(
        published,
        "generation-new",
        sample_retriever=lambda: ["chunk-version-2"],
    )

    # 5. CAS 准备（基线为 publication-old）→ 显式激活
    coordinator.validate_and_prepare_publication(
        "publication-new",
        "generation-new",
        published_dir,
        sample_retriever=lambda: ["chunk-version-2"],
    )
    coordinator.activate_prepared_publication("publication-new")
    active = repository.get_active_publication()
    assert active.publication_id == "publication-new"
    assert active.generation_id == "generation-new"
    assert repository.get_publication_build("publication-new")["status"] == "published"
    # V7 激活绝不改写 legacy JSON 指针：真值只在 SQLite
    assert manager.get_active("招商银行")["generation_id"] == published.generation_id

    # 6. 旧代际回收资格：无 active 引用、无在途请求、保留期已过、制品未锁定
    _backdate_generation(store, "generation-old")
    record = evaluator.evaluate_retirement_eligibility(
        "generation-old", retention_seconds=0, artifact_root=old_artifacts
    )
    assert record["eligible"] is True
    assert record["conditions"]["no_active_publication_reference"] is True
    assert record["details"]["referencing_publications"] == ("publication-old",)

    # 7. 整组回滚：以新 publication 重指旧完整快照，active 真值回到旧代际
    rollback = repository.rollback_to_publication("publication-rollback", "publication-old")
    assert rollback.generation_id == "generation-old"
    assert repository.get_active_publication().publication_id == "publication-rollback"
    # 回滚后旧代际重新被 active 引用，回收资格必须转为 False
    after = evaluator.evaluate_retirement_eligibility(
        "generation-old", retention_seconds=0, artifact_root=old_artifacts
    )
    assert after["eligible"] is False
    assert after["conditions"]["no_active_publication_reference"] is False


def test_full_chain_superseded_activation_keeps_active_and_rollback_restores_old(tmp_path):
    """并发基线覆盖：后激活者得到 superseded 且 active 不变；整组回滚恢复旧代际且不物理删除任何候选。"""
    from src.publication_set import PublicationSetError, PublicationSetRepository
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_publication_coordinator import V7GenerationPublicationCoordinator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    repository = PublicationSetRepository(store)
    coordinator = V7GenerationPublicationCoordinator(migrator, repository)

    # 旧代际激活，作为两个并发发布者的共同 CAS 基线
    migrator.build_candidate("generation-old", [_chunk("version-1"), _chunk("version-2")])
    old_artifacts = tmp_path / "old-artifacts"
    _write_artifacts(old_artifacts)
    coordinator.validate_and_prepare_publication(
        "publication-old",
        "generation-old",
        old_artifacts,
        sample_retriever=lambda: ["chunk-version-1", "chunk-version-2"],
    )
    coordinator.activate_prepared_publication("publication-old")

    # 两个并发候选基于相同基线完成准备
    migrator.build_candidate("generation-a", [_chunk("version-1"), _chunk("version-2")])
    migrator.build_candidate("generation-b", [_chunk("version-1"), _chunk("version-2")])
    artifacts_a = tmp_path / "artifacts-a"
    artifacts_b = tmp_path / "artifacts-b"
    _write_artifacts(artifacts_a)
    _write_artifacts(artifacts_b)
    for publication_id, generation_id, chunk_ids, artifact_root in (
        ("publication-a", "generation-a", ["chunk-version-1", "chunk-version-2"], artifacts_a),
        ("publication-b", "generation-b", ["chunk-version-1", "chunk-version-2"], artifacts_b),
    ):
        coordinator.validate_and_prepare_publication(
            publication_id, generation_id, artifact_root, sample_retriever=lambda: chunk_ids
        )

    # publication-a 抢先激活；publication-b 的过期基线激活必须被拒绝
    coordinator.activate_prepared_publication("publication-a")
    assert repository.get_active_publication().publication_id == "publication-a"

    with pytest.raises(PublicationSetError):
        coordinator.activate_prepared_publication("publication-b")

    build_b = repository.get_publication_build("publication-b")
    assert build_b["status"] == "superseded"
    assert "publication-a" in build_b["superseded_reason"]
    assert repository.get_active_publication().publication_id == "publication-a"

    # 整组回滚恢复旧代际；被淘汰候选与制品保持完整（只记录资格，不物理删除）
    rollback = repository.rollback_to_publication("publication-rollback", "publication-old")
    assert rollback.generation_id == "generation-old"
    assert repository.get_active_publication().publication_id == "publication-rollback"
    assert repository.get_publication_build("publication-a")["status"] == "published"
    assert repository.get_publication_build("publication-b")["status"] == "superseded"
    assert (artifacts_b / "index.faiss").is_file()
    with store.connect() as connection:
        status = connection.execute(
            "SELECT status FROM v7_generation_candidates WHERE generation_id = 'generation-b'"
        ).fetchone()[0]
    assert status == "validated"
