# -*- coding: utf-8 -*-
"""M3.7/M3.8 索引链 artifact 引用透传与 strict 模式测试。"""

import json

import pytest

from src import ingestion


def _chunk(child_id, **overrides):
    """构造一个满足既有 metadata 字段契约的子块。"""
    chunk = {
        "child_id": child_id,
        "text": f"{child_id} 的测试文本",
        "parent_key": "parent-1",
        "parent_id": "parent-1",
        "source_file": "年度报告.pdf",
        "pages": [1],
        "document_pages": 1,
        "company_name": "测试公司",
        "hash": f"hash-{child_id}",
        "tags": [],
    }
    chunk.update(overrides)
    return chunk


@pytest.fixture
def fake_embeddings(monkeypatch):
    """固定返回正常向量，避免真实 Embedding API 调用。"""

    def _fake(batch_texts, api_key):
        return [[1.0] * ingestion.EMBEDDING_DIM for _ in batch_texts]

    monkeypatch.setattr(ingestion, "get_embeddings_with_retry", _fake)


def test_artifact_refs_are_written_into_existing_metadata_chain(tmp_path, fake_embeddings):
    """携带 artifact_refs 的子块经既有 metadata 链写入引用；未携带的不写该字段。"""
    chunks = [
        _chunk("chunk-1", artifact_refs=["page-artifact-1"]),
        _chunk("chunk-2"),
    ]

    ingestion.build_company_index("测试公司", chunks, {}, tmp_path, "key")

    metadata = json.loads(
        (tmp_path / "测试公司" / "metadata.json").read_text(encoding="utf-8")
    )
    assert metadata[0]["artifact_refs"] == ["page-artifact-1"]
    # 未携带引用的子块保持旧字段契约，不新增空字段
    assert "artifact_refs" not in metadata[1]


def test_strict_faiss_build_aborts_on_embedding_failure_without_zero_vectors(tmp_path, monkeypatch):
    """strict 模式下 embedding 批次失败立即中止，不产生零向量索引。"""

    def _fail(batch_texts, api_key):
        raise RuntimeError("embedding api down")

    monkeypatch.setattr(ingestion, "get_embeddings_with_retry", _fail)

    with pytest.raises(ingestion.EmbeddingIncompleteError):
        ingestion.build_faiss_index([_chunk("chunk-1")], "key", strict=True)


def test_strict_company_index_writes_no_index_artifact(tmp_path, monkeypatch):
    """strict 构建失败时不写入 index.faiss 制品。"""

    def _fail(batch_texts, api_key):
        raise RuntimeError("embedding api down")

    monkeypatch.setattr(ingestion, "get_embeddings_with_retry", _fail)

    with pytest.raises(ingestion.EmbeddingIncompleteError):
        ingestion.build_company_index(
            "测试公司", [_chunk("chunk-1")], {}, tmp_path, "key", strict=True
        )

    assert not (tmp_path / "测试公司" / "index.faiss").exists()


def test_default_build_keeps_legacy_zero_vector_behavior(tmp_path, monkeypatch):
    """默认非 strict 保持 legacy 行为：失败批次补零向量并继续构建。"""
    calls = {"count": 0}

    def _fail_second_batch(batch_texts, api_key):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("embedding api down")
        return [[1.0] * ingestion.EMBEDDING_DIM for _ in batch_texts]

    monkeypatch.setattr(ingestion, "get_embeddings_with_retry", _fail_second_batch)
    monkeypatch.setattr(ingestion, "BATCH_SIZE", 1)

    index = ingestion.build_faiss_index([_chunk("chunk-1"), _chunk("chunk-2")], "key")

    assert index.ntotal == 2


def test_staging_adapter_forwards_explicit_strict_mode_to_existing_builder(
    tmp_path, monkeypatch
):
    """视觉 staging 调用可启用 strict，默认适配器签名仍由既有测试覆盖。"""
    calls = []

    def _strict_builder(
        company_name, child_chunks, parent_texts, output_dir, api_key, *, strict=False
    ):
        calls.append(strict)
        company_dir = output_dir / company_name
        company_dir.mkdir(parents=True, exist_ok=True)
        (company_dir / "index.faiss").write_bytes(b"index")
        (company_dir / "bm25_index.pkl").write_bytes(b"bm25")
        (company_dir / "metadata.json").write_text("[]", encoding="utf-8")
        (company_dir / "parent_texts.json").write_text("{}", encoding="utf-8")
        return {"source_files": [], "strict": strict}

    monkeypatch.setattr(ingestion, "build_company_index", _strict_builder)

    result = ingestion.build_company_index_to_publication(
        "测试公司", [], {}, tmp_path, "key", strict=True
    )

    assert result.generation_id
    assert calls == [True]


def test_strict_staging_failure_does_not_replace_active_generation(tmp_path, monkeypatch):
    """strict staging 失败时保留既有 active 指针并清理临时目录。"""
    def _stable_builder(company_name, child_chunks, parent_texts, output_dir, api_key):
        company_dir = output_dir / company_name
        company_dir.mkdir(parents=True, exist_ok=True)
        (company_dir / "index.faiss").write_bytes(b"stable")
        (company_dir / "bm25_index.pkl").write_bytes(b"stable")
        (company_dir / "metadata.json").write_text("[]", encoding="utf-8")
        (company_dir / "parent_texts.json").write_text("{}", encoding="utf-8")
        return {"source_files": []}

    monkeypatch.setattr(ingestion, "build_company_index", _stable_builder)
    stable = ingestion.build_company_index_to_publication(
        "测试公司", [], {}, tmp_path, "key"
    )

    def _fail_builder(
        company_name, child_chunks, parent_texts, output_dir, api_key, *, strict=False
    ):
        raise ingestion.EmbeddingIncompleteError("视觉 embedding 失败")

    monkeypatch.setattr(ingestion, "build_company_index", _fail_builder)
    with pytest.raises(ingestion.EmbeddingIncompleteError, match="视觉 embedding"):
        ingestion.build_company_index_to_publication(
            "测试公司", [], {}, tmp_path, "key", strict=True
        )

    from src.index_publication import IndexPublicationManager

    manager = IndexPublicationManager(tmp_path)
    assert manager.get_active("测试公司")["generation_id"] == stable.generation_id
    assert not list((tmp_path / ".staging").glob("*"))
