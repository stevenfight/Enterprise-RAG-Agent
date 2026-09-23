# -*- coding: utf-8 -*-
"""v7 PDF staging 上传服务。"""

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .pdf_validation import inspect_pdf_bytes
from .v7_document_repository import DocumentVersionRegistration, V7DocumentRepository


class PdfUploadValidationError(ValueError):
    """上传的 PDF 未通过 v7 输入校验。"""


@dataclass(frozen=True)
class V7PdfUploadResult:
    """v7 PDF 上传结果。"""

    registration: DocumentVersionRegistration
    validation_status: str
    physical_page_count: int


class V7PdfUploadService:
    """通过同文件系统 staging 完成 PDF 校验和不可变版本登记。"""

    def __init__(self, repository: V7DocumentRepository, staging_root: Path) -> None:
        self.repository = repository
        self.staging_root = Path(staging_root)
        if self.staging_root.resolve().drive != repository.blob_root.resolve().drive:
            raise ValueError("v7 staging 与 blob 必须位于同一文件系统")

    def upload(
        self,
        *,
        logical_document_key: str,
        display_name: str,
        original_filename: str,
        file_content: bytes,
    ) -> V7PdfUploadResult:
        """暂存、关闭后校验、登记版本，并清理暂存文件。"""
        self.staging_root.mkdir(parents=True, exist_ok=True)
        staging_path = self.staging_root / f"{uuid.uuid4().hex}.uploading"
        try:
            with staging_path.open("xb") as staging_file:
                staging_file.write(file_content)
                staging_file.flush()
                os.fsync(staging_file.fileno())
            staged_content = staging_path.read_bytes()
            if staged_content != file_content:
                raise OSError("v7 staging 写入后字节不一致")
            validation = inspect_pdf_bytes(staged_content)
            if not validation.valid or validation.physical_page_count is None:
                raise PdfUploadValidationError(
                    f"PDF 上传校验失败: {validation.status}"
                )
            registration = self.repository.register_document_version(
                logical_document_key=logical_document_key,
                display_name=display_name,
                original_filename=original_filename,
                file_content=staged_content,
                physical_page_count=validation.physical_page_count,
            )
            return V7PdfUploadResult(
                registration=registration,
                validation_status=validation.status,
                physical_page_count=validation.physical_page_count,
            )
        finally:
            if staging_path.exists():
                staging_path.unlink()

    def cleanup_expired_staging(
        self,
        *,
        older_than_seconds: float,
        now: float | None = None,
    ) -> list[str]:
        """只清理超过保留期的上传暂存文件，避免干扰正在进行的上传。"""
        if older_than_seconds < 0:
            raise ValueError("older_than_seconds 不能为负数")
        now = time.time() if now is None else now
        if not self.staging_root.exists():
            return []
        removed: list[str] = []
        for staging_path in sorted(self.staging_root.glob("*.uploading")):
            if now - staging_path.stat().st_mtime < older_than_seconds:
                continue
            staging_path.unlink()
            removed.append(staging_path.name)
        return removed
