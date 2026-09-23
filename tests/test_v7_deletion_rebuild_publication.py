# -*- coding: utf-8 -*-
"""M3.10.b rebuild_required 删除请求的重建发布链测试。

验证删除线性化（版本已进入 deleting）之后，仍能构建排除该版本的
candidate generation，经制品验证与 PublicationSet CAS 发布使替代
publication 生效；重建过程不触碰 deleting 版本本体，也不执行物理清理。
"""

import hashlib


def _seed_active_documents(store) -> None:
    """与 M1.8.e 端到端夹具一致：注册两个 active 文档版本。"""
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


def test_rebuild_required_deletion_request_publishes_replacement_excluding_deleting_version(tmp_path):
    """rebuild_required 删除请求经排除候选、制品绑定与 CAS 发布后，替代 publication 生效。"""
    from src.index_publication import IndexPublicationManager
    from src.publication_set import PublicationSetRepository
    from src.v7_document_deletion_coordinator import V7DocumentDeletionCoordinator
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_generation_publication_coordinator import V7GenerationPublicationCoordinator
    from src.v7_index_generation_binding import V7IndexGenerationBinder
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    repository = PublicationSetRepository(store)
    coordinator = V7GenerationPublicationCoordinator(migrator, repository)

    # 1. 旧代际：覆盖两个 active 文档版本，验证并激活为初始发布
    migrator.build_candidate("generation-old", [_chunk("version-1"), _chunk("version-2")])
    old_artifacts = tmp_path / "old-artifacts"
    old_artifacts.mkdir(parents=True)
    (old_artifacts / "index.faiss").write_bytes(b"faiss")
    (old_artifacts / "bm25_index.pkl").write_bytes(b"bm25")
    (old_artifacts / "metadata.json").write_text("[]", encoding="utf-8")
    (old_artifacts / "parent_texts.json").write_text("{}", encoding="utf-8")
    coordinator.validate_and_prepare_publication(
        "publication-old",
        "generation-old",
        old_artifacts,
        sample_retriever=lambda: ["chunk-version-1", "chunk-version-2"],
    )
    coordinator.activate_prepared_publication("publication-old")
    assert repository.get_active_publication().publication_id == "publication-old"

    # 2. 删除线性化：version-1 进入 deleting，且无在途请求租约时删除请求为 rebuild_required
    deletion_coordinator = V7DocumentDeletionCoordinator(store)
    request = deletion_coordinator.request_deletion("version-1")
    assert request.status == "rebuild_required"
    assert request.active_request_lease_count == 0

    # 3. 为 rebuild_required 删除请求构建排除 deleting 版本的候选代际
    migrator.build_candidate_excluding_document("generation-new", "version-1", [_chunk("version-2")])
    candidate = migrator.get_candidate("generation-new")
    assert candidate["document_version_ids"] == ["version-2"]

    # 4. 实际索引管理器构建并发布 staging generation（内容只含 version-2）
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

    # 5. 绑定：把已发布代际制品固化为 V7 候选的不可变 hash/size manifest
    binder = V7IndexGenerationBinder(manager, migrator)
    binder.bind_published_generation(
        published,
        "generation-new",
        sample_retriever=lambda: ["chunk-version-2"],
    )

    # 6. CAS 准备（基线为 publication-old）→ 显式激活替代 publication
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

    # 7. 替代 publication 的文档集不再包含 deleting 版本
    with store.connect() as connection:
        replacement_versions = connection.execute(
            "SELECT document_version_id FROM v7_publication_document_versions WHERE publication_id = 'publication-new' ORDER BY document_version_id"
        ).fetchall()
        deleting_status = connection.execute(
            "SELECT index_status FROM v7_document_versions WHERE document_version_id = 'version-1'"
        ).fetchone()[0]
    assert [row[0] for row in replacement_versions] == ["version-2"]
    # 重建发布不触碰 deleting 版本本体；物理清理只能由后续租约治理与异步删除执行推进
    assert deleting_status == "deleting"
