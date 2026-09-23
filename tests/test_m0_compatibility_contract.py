"""M0.10 旧知识库契约冻结与多模态可选字段测试。"""

import json
from pathlib import Path

import fitz

import src.knowledge_service as knowledge_service


def _pdf_bytes() -> bytes:
    """构造可被 v7 校验器读取的一页 PDF。"""
    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    return payload


def _legacy_contract() -> dict:
    """读取冻结的旧 JSON 字段集合。"""
    path = Path(__file__).parent / "fixtures" / "knowledge_legacy_contract.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _v7_service(tmp_path: Path):
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore
    from src.v7_pdf_upload_service import V7PdfUploadService

    return V7PdfUploadService(
        V7DocumentRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"), tmp_path / "blobs"),
        tmp_path / "staging",
    )


def test_multimodal_disabled_preserves_frozen_upload_query_and_delete_contract(tmp_path: Path, monkeypatch):
    contract = _legacy_contract()
    legacy_dir = tmp_path / "legacy"
    monkeypatch.setattr(knowledge_service, "_PDF_DIR", legacy_dir)
    monkeypatch.setattr(knowledge_service, "_MANIFEST_PATH", tmp_path / "manifest.json")

    upload = knowledge_service.upload_pdf(b"%PDF-1.7\nlegacy", "旧契约.pdf")

    assert sorted(upload) == contract["upload_result_keys"]
    documents = knowledge_service.get_documents()
    assert len(documents) == 1
    assert sorted(documents[0]) == contract["document_result_keys"]
    assert knowledge_service.delete_pdf("旧契约.pdf") is contract["delete_result"]


def test_multimodal_enabled_only_adds_declared_async_fields_and_keeps_pending_status(tmp_path: Path):
    from src.v7_feature_flags import V7FeatureFlags

    contract = _legacy_contract()
    flags = V7FeatureFlags.from_mapping(
        {
            "financial_trust_enabled": True,
            "durable_execution_enabled": True,
            "multimodal_enabled": True,
        }
    )

    result = knowledge_service.upload_pdf(
        _pdf_bytes(),
        "多模态报告.pdf",
        v7_flags=flags,
        v7_upload_service=_v7_service(tmp_path),
        logical_document_key="multimodal-report",
    )

    assert set(contract["upload_result_keys"]).issubset(result)
    assert result["index_status"] == "pending_index"
    assert result["processing_status"] == "pending_processing"
    assert result["document_version_id"]
    assert result["logical_document_id"]
    assert result["physical_page_count"] == 1
    assert set(result) == set(contract["upload_result_keys"]) | {
        "processing_status", "logical_document_id", "document_version_id", "physical_page_count",
    }


def test_api_upload_model_exposes_only_optional_v7_contract_extensions():
    from src.api_service import KnowledgeUploadResponse

    response = KnowledgeUploadResponse(
        success=True,
        filename="多模态报告.pdf",
        size=1,
        size_mb=0.0,
        sha256="a" * 64,
        index_status="pending_index",
        idempotent=False,
        processing_status="pending_processing",
        logical_document_id="logical-1",
        document_version_id="version-1",
        physical_page_count=1,
    ).model_dump(exclude_none=True)

    assert response["processing_status"] == "pending_processing"
    assert response["document_version_id"] == "version-1"


def test_api_upload_uses_v7_dependencies_only_when_multimodal_flag_is_enabled(tmp_path: Path, monkeypatch):
    from src import api_service
    from src.v7_feature_flags import V7FeatureFlags

    monkeypatch.setattr(api_service, "project_root", tmp_path)
    disabled = V7FeatureFlags()
    monkeypatch.setattr(api_service, "_load_agent_config", lambda: {"v7_feature_flags": disabled})
    assert api_service._v7_upload_kwargs("报告.pdf") == {}

    enabled = V7FeatureFlags.from_mapping(
        {
            "financial_trust_enabled": True,
            "durable_execution_enabled": True,
            "multimodal_enabled": True,
        }
    )
    monkeypatch.setattr(api_service, "_load_agent_config", lambda: {"v7_feature_flags": enabled})

    kwargs = api_service._v7_upload_kwargs("报告.pdf")

    assert kwargs["v7_flags"] is enabled
    assert kwargs["logical_document_key"] == "api-upload:报告.pdf"
    assert kwargs["display_name"] == "报告.pdf"
    assert kwargs["v7_upload_service"].repository.store.database_path == tmp_path / "data" / "v7" / "metadata.sqlite3"
