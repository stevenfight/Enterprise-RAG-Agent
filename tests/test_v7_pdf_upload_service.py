"""v7 PDF staging 上传服务的确定性测试。"""

from pathlib import Path

import fitz
import pytest


def _valid_pdf_bytes(page_count: int) -> bytes:
    document = fitz.open()
    for _ in range(page_count):
        document.new_page()
    payload = document.tobytes()
    document.close()
    return payload


def _service(tmp_path: Path):
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore
    from src.v7_pdf_upload_service import V7PdfUploadService

    repository = V7DocumentRepository(
        V7MetadataStore(tmp_path / "metadata.sqlite3"),
        tmp_path / "blobs",
    )
    return V7PdfUploadService(repository, tmp_path / "staging")


def test_v7_upload_stages_validates_and_registers_immutable_version(tmp_path: Path):
    service = _service(tmp_path)

    result = service.upload(
        logical_document_key="issuer-annual-2024",
        display_name="公司年报",
        original_filename="公司年报.pdf",
        file_content=_valid_pdf_bytes(2),
    )

    assert result.validation_status == "valid"
    assert result.physical_page_count == 2
    assert result.registration.created is True
    assert result.registration.blob_path.exists()
    assert list((tmp_path / "staging").glob("*")) == []


def test_v7_upload_rejects_invalid_pdf_before_document_version_registration(tmp_path: Path):
    from src.v7_pdf_upload_service import PdfUploadValidationError

    service = _service(tmp_path)
    with pytest.raises(PdfUploadValidationError, match="invalid_magic"):
        service.upload(
            logical_document_key="invalid",
            display_name="无效文件",
            original_filename="无效.pdf",
            file_content=b"not a PDF",
        )

    assert service.repository.count_document_versions() == 0
    assert service.repository.count_blobs() == 0
    assert list((tmp_path / "staging").glob("*")) == []
