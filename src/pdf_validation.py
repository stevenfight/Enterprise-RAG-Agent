# -*- coding: utf-8 -*-
"""v7 PDF 输入校验。"""

from dataclasses import dataclass

import fitz


@dataclass(frozen=True)
class PdfValidationResult:
    """PDF 可读性与物理页数校验结果。"""

    valid: bool
    status: str
    physical_page_count: int | None


def inspect_pdf_bytes(file_content: bytes) -> PdfValidationResult:
    """验证 PDF 字节，返回稳定错误状态且不修改输入。"""
    if not isinstance(file_content, bytes) or not file_content.startswith(b"%PDF-"):
        return PdfValidationResult(False, "invalid_magic", None)
    try:
        document = fitz.open(stream=file_content, filetype="pdf")
    except (fitz.FileDataError, RuntimeError, ValueError):
        return PdfValidationResult(False, "unreadable", None)

    try:
        if document.needs_pass:
            return PdfValidationResult(False, "unsupported_encrypted", None)
        if document.page_count <= 0:
            return PdfValidationResult(False, "zero_pages", 0)
        return PdfValidationResult(True, "valid", document.page_count)
    finally:
        document.close()
