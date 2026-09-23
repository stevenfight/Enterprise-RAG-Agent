# -*- coding: utf-8 -*-
"""M1.8.b 已发布 legacy generation 制品与 V7 candidate 的不可变绑定测试。"""

import hashlib
import json

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


def _build_company_index(staging_company) -> dict:
    """模拟真实索引构建器：写入四个必需制品并返回对象元数据。"""
    staging_company.mkdir(parents=True)
    (staging_company / "index.faiss").write_bytes(b"faiss-bytes-v1")
    (staging_company / "bm25_index.pkl").write_bytes(b"bm25-bytes-v1")
    (staging_company / "metadata.json").write_text("[]", encoding="utf-8")
    (staging_company / "parent_texts.json").write_text("{}", encoding="utf-8")
    return {"doc_count": 2, "source": "builder"}


def _expected_manifest(company_dir) -> list[dict]:
    manifest = []
    for name in ("index.faiss", "bm25_index.pkl", "metadata.json", "parent_texts.json"):
        content = (company_dir / name).read_bytes()
        manifest.append(
            {"name": name, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        )
    return manifest


def _make_binder(tmp_path):
    from src.index_publication import IndexPublicationManager
    from src.v7_generation_migration import V7GenerationMigrator
    from src.v7_index_generation_binding import V7IndexGenerationBinder
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_active_documents(store)
    migrator = V7GenerationMigrator(store)
    migrator.build_candidate("generation-bind", [_chunk("version-1"), _chunk("version-2")])
    manager = IndexPublicationManager(tmp_path / "index_root")
    result = manager.build_and_publish("招商银行", _build_company_index)
    binder = V7IndexGenerationBinder(manager, migrator)
    return binder, manager, migrator, result, store


def test_binding_registers_published_artifacts_as_immutable_manifest(tmp_path):
    """绑定必须把已发布代际的公司制品目录固化为路径无关 hash/size manifest，且不创建 PublicationSet。"""
    from src.publication_set import PublicationSetRepository

    binder, manager, migrator, result, store = _make_binder(tmp_path)
    final_company_dir = manager.generations_dir / result.generation_id / "招商银行"

    validation = binder.bind_published_generation(
        result,
        "generation-bind",
        sample_retriever=lambda: ["chunk-version-1", "chunk-version-2"],
    )

    assert validation["status"] == "validated"
    with store.connect() as connection:
        manifest = json.loads(
            connection.execute(
                "SELECT artifact_manifest_json FROM v7_generation_candidates WHERE generation_id = 'generation-bind'"
            ).fetchone()[0]
        )
    assert manifest == _expected_manifest(final_company_dir)
    # 绑定只登记清单，不创建任何 PublicationSet，也不改写 legacy active 指针
    assert PublicationSetRepository(store).get_active_publication() is None
    assert manager.get_active("招商银行")["generation_id"] == result.generation_id

    # 幂等：同 generation 重复绑定相同制品保持 validated
    again = binder.bind_published_generation(
        result,
        "generation-bind",
        sample_retriever=lambda: ["chunk-version-1", "chunk-version-2"],
    )
    assert again["status"] == "validated"
    assert again["artifact_manifest"] == manifest


def test_binding_failure_keeps_candidate_without_publication_and_active_unchanged(tmp_path):
    """制品缺失时绑定必须失败：candidate 进入 validation_failed，legacy active 指针不变，无 PublicationSet。"""
    from src.publication_set import PublicationSetRepository
    from src.v7_generation_migration import GenerationMigrationError

    binder, manager, migrator, result, store = _make_binder(tmp_path)
    (manager.generations_dir / result.generation_id / "招商银行" / "index.faiss").unlink()

    with pytest.raises(GenerationMigrationError):
        binder.bind_published_generation(
            result,
            "generation-bind",
            sample_retriever=lambda: ["chunk-version-1", "chunk-version-2"],
        )

    with store.connect() as connection:
        status = connection.execute(
            "SELECT status FROM v7_generation_candidates WHERE generation_id = 'generation-bind'"
        ).fetchone()[0]
    assert status == "validation_failed"
    assert manager.get_active("招商银行")["generation_id"] == result.generation_id
    assert PublicationSetRepository(store).get_active_publication() is None


def test_generation_manifest_mismatch_blocks_binding_before_validation(tmp_path):
    """generation.json 与发布结果不一致时直接拒绝绑定，candidate 状态保持 candidate，指针不变。"""
    from src.v7_index_generation_binding import IndexGenerationBindingError

    binder, manager, migrator, result, store = _make_binder(tmp_path)
    generation_dir = manager.generations_dir / result.generation_id
    (generation_dir / "generation.json").write_text(
        json.dumps({"generation_id": "generation-other", "company_name": "招商银行"}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(IndexGenerationBindingError):
        binder.bind_published_generation(
            result,
            "generation-bind",
            sample_retriever=lambda: ["chunk-version-1", "chunk-version-2"],
        )

    with store.connect() as connection:
        status = connection.execute(
            "SELECT status FROM v7_generation_candidates WHERE generation_id = 'generation-bind'"
        ).fetchone()[0]
    assert status == "candidate"
    assert manager.get_active("招商银行")["generation_id"] == result.generation_id
