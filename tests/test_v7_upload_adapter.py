"""v7 feature flag 下上传适配的确定性测试。"""

from pathlib import Path

import fitz
import pytest

import src.knowledge_service as knowledge_service


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    return payload


def _v7_service(tmp_path: Path):
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore
    from src.v7_pdf_upload_service import V7PdfUploadService

    return V7PdfUploadService(
        V7DocumentRepository(
            V7MetadataStore(tmp_path / "metadata.sqlite3"),
            tmp_path / "blobs",
        ),
        tmp_path / "staging",
    )


def test_multimodal_upload_routes_to_v7_and_does_not_write_legacy_pdf_dir(tmp_path: Path, monkeypatch):
    from src.v7_feature_flags import V7FeatureFlags

    legacy_pdf_dir = tmp_path / "legacy_pdf_reports"
    monkeypatch.setattr(knowledge_service, "_PDF_DIR", legacy_pdf_dir)
    flags = V7FeatureFlags.from_mapping(
        {
            "financial_trust_enabled": True,
            "durable_execution_enabled": True,
            "multimodal_enabled": True,
        }
    )

    result = knowledge_service.upload_pdf(
        _pdf_bytes(),
        "公司报告.pdf",
        v7_flags=flags,
        v7_upload_service=_v7_service(tmp_path),
        logical_document_key="company-report-2024",
    )

    assert result["index_status"] == "pending_index"
    assert result["document_version_id"]
    assert result["logical_document_id"]
    assert result["physical_page_count"] == 1
    assert not legacy_pdf_dir.exists()


def test_multimodal_upload_fails_closed_without_service_or_logical_key(tmp_path: Path):
    from src.v7_feature_flags import V7FeatureFlags

    flags = V7FeatureFlags.from_mapping(
        {
            "financial_trust_enabled": True,
            "durable_execution_enabled": True,
            "multimodal_enabled": True,
        }
    )
    with pytest.raises(RuntimeError, match="v7_upload_service"):
        knowledge_service.upload_pdf(_pdf_bytes(), "报告.pdf", v7_flags=flags)
    with pytest.raises(ValueError, match="logical_document_key"):
        knowledge_service.upload_pdf(
            _pdf_bytes(),
            "报告.pdf",
            v7_flags=flags,
            v7_upload_service=_v7_service(tmp_path),
        )
