"""增量索引 staging 与 active 发布指针测试。"""

import json
from pathlib import Path

import pytest

from src.index_publication import IndexPublicationManager
from src.retrieval import HybridRetriever
import src.ingestion as ingestion


def write_valid_company_index(company_dir: Path, marker: str) -> dict:
    company_dir.mkdir(parents=True, exist_ok=True)
    (company_dir / "index.faiss").write_bytes(marker.encode("utf-8"))
    (company_dir / "bm25_index.pkl").write_bytes(marker.encode("utf-8"))
    (company_dir / "metadata.json").write_text("[]", encoding="utf-8")
    (company_dir / "parent_texts.json").write_text("{}", encoding="utf-8")
    return {"source_files": [f"{marker}.pdf"], "child_chunk_count": 0}


def test_successful_build_publishes_new_generation_without_overwriting_previous(tmp_path: Path):
    manager = IndexPublicationManager(tmp_path)
    first = manager.build_and_publish("中国移动", lambda path: write_valid_company_index(path, "first"))
    second = manager.build_and_publish("中国移动", lambda path: write_valid_company_index(path, "second"))

    assert first.generation_id != second.generation_id
    assert manager.get_active("中国移动")["generation_id"] == second.generation_id
    assert (tmp_path / "generations" / first.generation_id / "中国移动" / "index.faiss").read_bytes() == b"first"
    assert (tmp_path / "generations" / second.generation_id / "中国移动" / "index.faiss").read_bytes() == b"second"


def test_failed_build_does_not_change_active_generation(tmp_path: Path):
    manager = IndexPublicationManager(tmp_path)
    first = manager.build_and_publish("中国电信", lambda path: write_valid_company_index(path, "stable"))

    def broken_builder(path: Path):
        path.mkdir(parents=True, exist_ok=True)
        (path / "index.faiss").write_bytes(b"incomplete")
        raise RuntimeError("embedding failed")

    with pytest.raises(RuntimeError, match="embedding failed"):
        manager.build_and_publish("中国电信", broken_builder)
    assert manager.get_active("中国电信")["generation_id"] == first.generation_id
    assert not list((tmp_path / ".staging").glob("*"))


def test_active_pointer_is_atomic_json_and_unknown_company_is_empty(tmp_path: Path):
    manager = IndexPublicationManager(tmp_path)
    assert manager.get_active("未知公司") is None
    result = manager.build_and_publish("中国联通", lambda path: write_valid_company_index(path, "ok"))
    pointer = tmp_path / "active" / "中国联通.json"
    assert json.loads(pointer.read_text(encoding="utf-8"))["generation_id"] == result.generation_id
    assert not list((tmp_path / "active").glob("*.uploading"))


def test_retriever_resolves_active_generation_and_keeps_legacy_fallback(tmp_path: Path):
    manager = IndexPublicationManager(tmp_path)
    result = manager.build_and_publish("中国移动", lambda path: write_valid_company_index(path, "active"))
    retriever = HybridRetriever(tmp_path, api_key="test-key")
    active_dir, active_generation = retriever._resolve_company_dir("中国移动")
    assert active_generation == result.generation_id
    assert active_dir == tmp_path / "generations" / result.generation_id / "中国移动"

    legacy_dir = tmp_path / "中国电信"
    legacy_dir.mkdir()
    legacy_resolved, legacy_generation = retriever._resolve_company_dir("中国电信")
    assert legacy_resolved == legacy_dir
    assert legacy_generation == "legacy"


def test_retriever_registry_discovers_company_from_active_pointer(tmp_path: Path):
    manager = IndexPublicationManager(tmp_path)
    manager.build_and_publish("新增公司", lambda path: write_valid_company_index(path, "new"))
    (tmp_path / "company_registry.json").write_text('{"companies": {}}', encoding="utf-8")
    retriever = HybridRetriever(tmp_path, api_key="test-key")
    registry = retriever._load_company_registry()
    assert "新增公司" in registry["companies"]


def test_retriever_discovers_active_company_without_legacy_registry(tmp_path: Path):
    manager = IndexPublicationManager(tmp_path)
    manager.build_and_publish("仅有新发布", lambda path: write_valid_company_index(path, "new"))

    retriever = HybridRetriever(tmp_path, api_key="test-key")

    assert "仅有新发布" in retriever._load_company_registry()["companies"]


def test_retriever_rejects_root_without_registry_or_active_index(tmp_path: Path):
    retriever = HybridRetriever(tmp_path, api_key="test-key")

    with pytest.raises(FileNotFoundError, match="没有 active 索引"):
        retriever._load_company_registry()


def test_ingestion_adapter_reuses_existing_builder_inside_staging(tmp_path: Path, monkeypatch):
    calls = []

    def fake_builder(company_name, child_chunks, parent_texts, output_dir, api_key):
        calls.append(Path(output_dir))
        return write_valid_company_index(Path(output_dir) / company_name, "adapter")

    monkeypatch.setattr(ingestion, "build_company_index", fake_builder)
    result = ingestion.build_company_index_to_publication(
        "中国移动", [], {}, tmp_path, "test-key"
    )
    assert result.generation_id
    assert calls[0] == tmp_path / ".staging" / result.generation_id


def test_existing_index_can_be_published_without_rebuilding(tmp_path: Path):
    legacy_root = tmp_path / "legacy"
    write_valid_company_index(legacy_root / "中国移动", "legacy")
    manager = IndexPublicationManager(tmp_path / "published")
    result = manager.publish_existing_company_index("中国移动", legacy_root)
    assert manager.get_active("中国移动")["generation_id"] == result.generation_id
    assert (
        tmp_path / "published" / "generations" / result.generation_id / "中国移动" / "index.faiss"
    ).read_bytes() == b"legacy"


def test_pre_publish_validation_failure_keeps_previous_active(tmp_path: Path):
    manager = IndexPublicationManager(tmp_path)
    first = manager.build_and_publish("中国移动", lambda path: write_valid_company_index(path, "stable"))
    with pytest.raises(RuntimeError, match="source changed"):
        manager.build_and_publish(
            "中国移动",
            lambda path: write_valid_company_index(path, "stale"),
            pre_publish_validator=lambda: (_ for _ in ()).throw(RuntimeError("source changed")),
        )
    assert manager.get_active("中国移动")["generation_id"] == first.generation_id


def test_ingestion_source_hash_change_cancels_publication(tmp_path: Path, monkeypatch):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.7\nold")
    expected = __import__("hashlib").sha256(source_pdf.read_bytes()).hexdigest()

    def fake_builder(company_name, child_chunks, parent_texts, output_dir, api_key):
        source_pdf.write_bytes(b"%PDF-1.7\nchanged")
        return write_valid_company_index(Path(output_dir) / company_name, "stale")

    monkeypatch.setattr(ingestion, "build_company_index", fake_builder)
    with pytest.raises(RuntimeError, match="源 PDF 在索引构建期间发生变化"):
        ingestion.build_company_index_to_publication(
            "中国移动", [], {}, tmp_path / "published", "test-key", source_pdf, expected
        )
    assert not (tmp_path / "published" / "active" / "中国移动.json").exists()
