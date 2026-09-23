# -*- coding: utf-8 -*-
"""M1.9 统一 PublicationResolver 接线测试。

验证：
- HybridRetriever 支持快照代际注入（generation_resolver 优先于 legacy 指针，M-T46 索引读取落地）；
- RetrieveTool / CompareTool / RAGGenerator 每次请求固定快照并在请求结束后释放，
  新请求自动刷新到最新激活的 publication（M-T47）。
"""

import hashlib
import json


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


def _activate_publication(repository, publication_id, generation_id="generation-1"):
    """以同一 generation 边界创建并激活 publication（首个无 CAS 基线，后续以当前 active 为基线）。"""
    active = repository.get_active_publication()
    repository.create_publication(
        publication_id,
        generation_id,
        document_version_ids=["version-1", "version-2"],
        page_artifact_ids=["artifact-1"],
        fact_ids=["fact-1"],
    )
    if active is None:
        repository.prepare_publication_build(publication_id, None, None)
    else:
        repository.prepare_publication_build(
            publication_id, active.publication_id, active.corpus_revision
        )
    repository.activate_publication(publication_id)


class _StubRetriever:
    """记录 search 调用并返回空结果的轻量检索器替身。"""

    def __init__(self):
        self.calls = []

    def search(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return []


def test_hybrid_retriever_prefers_snapshot_generation_and_keeps_legacy_fallback(tmp_path):
    """M1.9.b：注入 generation_resolver 时优先快照代际目录；未注入或返回空时保持 legacy 契约。"""
    from src.retrieval import HybridRetriever

    # 注入 resolver：优先使用快照代际目录
    retriever = HybridRetriever(
        tmp_path, generation_resolver=lambda company_name: "generation-snap"
    )
    company_dir, generation_id = retriever._resolve_company_dir("招商银行")
    assert generation_id == "generation-snap"
    assert company_dir == tmp_path / "generations" / "generation-snap" / "招商银行"

    # resolver 返回 None：回退 legacy 指针/旧目录契约
    retriever = HybridRetriever(tmp_path, generation_resolver=lambda company_name: None)
    legacy_dir, legacy_generation = retriever._resolve_company_dir("招商银行")
    assert legacy_generation == "legacy"
    assert legacy_dir == tmp_path / "招商银行"

    # 未注入 resolver：legacy 指针行为保持不变
    active_dir = tmp_path / "active"
    active_dir.mkdir()
    (active_dir / "招商银行.json").write_text(
        json.dumps({"company_name": "招商银行", "generation_id": "generation-pointer"}),
        encoding="utf-8",
    )
    retriever = HybridRetriever(tmp_path)
    pointer_dir, pointer_generation = retriever._resolve_company_dir("招商银行")
    assert pointer_generation == "generation-pointer"
    assert pointer_dir == tmp_path / "generations" / "generation-pointer" / "招商银行"


def test_retrieve_tool_pins_snapshot_per_request_and_refreshes_next_request(tmp_path):
    """M-T47（RetrieveTool）：每次请求固定快照并在结果携带 publication_id，新请求刷新。"""
    from src.publication_set import PublicationResolver, PublicationSetRepository
    from src.tools.retrieve_tool import RetrieveTool
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store)
    repository = PublicationSetRepository(store)
    _activate_publication(repository, "publication-a")
    resolver = PublicationResolver(repository)

    tool = RetrieveTool(api_key="stub", publication_resolver=resolver)
    stub = _StubRetriever()
    tool._retriever = stub

    result = tool.run(query="招商银行 2024 营收")
    assert result.success is True
    assert result.data["publication_id"] == "publication-a"
    assert len(stub.calls) == 1

    # 新请求前激活新 publication：下一次请求读取到新快照
    _activate_publication(repository, "publication-b")
    result = tool.run(query="招商银行 2024 营收")
    assert result.success is True
    assert result.data["publication_id"] == "publication-b"
    # 请求结束后释放固定快照
    assert resolver.current_snapshot() is None


def test_compare_tool_pins_snapshot_per_request_and_refreshes_next_request(tmp_path):
    """M-T47（CompareTool）：每次请求固定快照并在结果携带 publication_id，新请求刷新。"""
    from src.publication_set import PublicationResolver, PublicationSetRepository
    from src.tools.compare_tool import CompareTool
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store)
    repository = PublicationSetRepository(store)
    _activate_publication(repository, "publication-a")
    resolver = PublicationResolver(repository)

    tool = CompareTool(api_key="stub", publication_resolver=resolver)
    tool._retriever = _StubRetriever()

    result = tool.run(companies=["中芯国际", "中国移动"], metric="营收", year="2024")
    assert result.success is True
    assert result.data["publication_id"] == "publication-a"

    _activate_publication(repository, "publication-b")
    result = tool.run(companies=["中芯国际", "中国移动"], metric="营收", year="2024")
    assert result.success is True
    assert result.data["publication_id"] == "publication-b"
    assert resolver.current_snapshot() is None


def test_rag_generator_pins_snapshot_per_request_and_refreshes_next_request(tmp_path):
    """M-T47（RAGGenerator）：请求内检索代际来自固定快照，新请求刷新 publication。"""
    from src.publication_set import PublicationResolver, PublicationSetRepository
    from src.retrieval import RAGGenerator
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_validated_generation(store)
    repository = PublicationSetRepository(store)
    _activate_publication(repository, "publication-a")
    resolver = PublicationResolver(repository)

    generator = RAGGenerator(tmp_path, api_key="stub", publication_resolver=resolver)

    # 请求内：检索器通过快照代际解析目录（同一 publication）
    with resolver.request_scope():
        retriever = generator._get_retriever()
        _, generation_id = retriever._resolve_company_dir("招商银行")
        assert generation_id == "generation-1"

    # 后续 query 改用轻量替身，避免加载重型依赖（jieba/faiss/dashscope）
    stub = _StubRetriever()
    generator._retriever = stub

    # 请求开始固定快照：结果携带 publication_id
    result = generator.query("招商银行 2024 营收")
    assert result["publication_id"] == "publication-a"

    # 新请求刷新：结果携带新激活的 publication_id
    _activate_publication(repository, "publication-b")
    result = generator.query("招商银行 2024 营收")
    assert result["publication_id"] == "publication-b"
    assert resolver.current_snapshot() is None
