"""M0.6 关系型溯源与失效传播的确定性测试。"""

import pytest


def _seed_lineage(store) -> None:
    """写入最小的已发布对象，供关联表测试使用。"""
    store.initialize()
    with store.connect() as connection:
        connection.execute("INSERT INTO v7_blobs(sha256, size_bytes) VALUES ('a', 1)")
        connection.execute("INSERT INTO v7_logical_documents(logical_document_id, logical_document_key, display_name) VALUES ('logical-1', 'report-2024', '报告')")
        connection.execute("INSERT INTO v7_document_versions VALUES ('version-1', 'logical-1', 'a', '报告.pdf', 1, 'active', CURRENT_TIMESTAMP)")
        connection.execute("INSERT INTO v7_document_asset_manifests VALUES ('manifest-1', 'version-1', 'a', 1, 'complete', 1, CURRENT_TIMESTAMP)")
        connection.execute(
            """INSERT INTO v7_page_artifacts(
                page_artifact_id, manifest_id, physical_page_number,
                artifact_kind, content_sha256, artifact_status, created_at,
                image_path, thumbnail_path
            ) VALUES ('artifact-1', 'manifest-1', 1, 'page_image', 'a', 'complete', CURRENT_TIMESTAMP, NULL, NULL)"""
        )
        connection.execute("INSERT INTO v7_financial_facts VALUES ('fact-1', 'revenue', '示例公司', '1', '元', '1', '元', 'CNY', 'FY2024', 'consolidated', '报告.pdf', '[1]', '摘录', CURRENT_TIMESTAMP)")
        connection.execute("INSERT INTO v7_fact_calculations VALUES ('calc-1', 'identity', 'v1', '[\"fact-1\"]', '{}', CURRENT_TIMESTAMP)")
        connection.execute("INSERT INTO v7_claims VALUES ('claim-1', '示例声明', CURRENT_TIMESTAMP)")
        connection.commit()


def test_provenance_repository_persists_all_relations_with_foreign_keys(tmp_path):
    from src.provenance_repository import ProvenanceRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_lineage(store)
    repository = ProvenanceRepository(store)

    repository.link_fact_to_document_version("fact-1", "version-1")
    repository.link_artifact_to_fact("artifact-1", "fact-1")
    repository.link_calculation_input("calc-1", "fact-1")
    repository.link_claim_fact("claim-1", "fact-1")
    repository.link_claim_calculation("claim-1", "calc-1")
    repository.create_report("report-1", "报告结论")
    repository.link_report_claim("report-1", "claim-1")

    with store.connect() as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT report_status FROM v7_reports WHERE report_id = 'report-1'").fetchone()[0] == "current"


def test_provenance_repository_rejects_dangling_relation_without_partial_write(tmp_path):
    from src.provenance_repository import ProvenanceRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_lineage(store)
    repository = ProvenanceRepository(store)

    with pytest.raises(ValueError, match="不存在"):
        repository.link_fact_to_document_version("fact-missing", "version-1")

    with store.connect() as connection:
        assert connection.execute("SELECT * FROM v7_fact_document_versions").fetchall() == []


def test_document_version_invalidation_marks_claim_calculation_and_report_stale(tmp_path):
    from src.provenance_repository import ProvenanceRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _seed_lineage(store)
    repository = ProvenanceRepository(store)
    repository.link_fact_to_document_version("fact-1", "version-1")
    repository.link_calculation_input("calc-1", "fact-1")
    repository.link_claim_fact("claim-1", "fact-1")
    repository.link_claim_calculation("claim-1", "calc-1")
    repository.create_report("report-1", "报告结论")
    repository.link_report_claim("report-1", "claim-1")

    invalidated = repository.invalidate_document_version("version-1", "source_superseded")

    assert invalidated == {
        "fact_ids": ["fact-1"],
        "calculation_ids": ["calc-1"],
        "claim_ids": ["claim-1"],
        "report_ids": ["report-1"],
    }
    assert repository.get_statuses("calc-1", "claim-1", "report-1") == {
        "calculation_status": "stale",
        "claim_status": "stale",
        "report_status": "stale",
    }
