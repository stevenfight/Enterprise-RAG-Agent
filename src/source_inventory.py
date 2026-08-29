# -*- coding: utf-8 -*-
"""源 PDF 冻结清单工具。

该模块仅读取 PDF 和已有 legacy registry，输出可复核的迁移基线；不修改源 PDF，
也不把物理页数推断为文档印刷页码。
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import fitz


def _sha256_file(file_path: Path) -> str:
    """以固定块大小计算源文件 SHA-256。"""
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_legacy_company_mapping(registry_path: Path) -> tuple[dict[str, str], set[str]]:
    """读取 registry 的既有文件—公司映射，并显式保留冲突文件。"""
    if not registry_path.exists():
        return {}, set()
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, set()

    mapping: dict[str, str] = {}
    ambiguous_filenames: set[str] = set()
    for company_name, info in registry.get("companies", {}).items():
        if not isinstance(info, dict):
            continue
        for filename in info.get("source_files", []):
            if not isinstance(filename, str):
                continue
            existing_company = mapping.get(filename)
            if existing_company and existing_company != str(company_name):
                ambiguous_filenames.add(filename)
                mapping.pop(filename, None)
            elif filename not in ambiguous_filenames:
                mapping[filename] = str(company_name)
    return mapping, ambiguous_filenames


def _inspect_pdf(pdf_path: Path) -> tuple[str, str, int | None]:
    """返回加密状态、可读状态和物理页数，失败时保持页数为空。"""
    try:
        document = fitz.open(pdf_path)
    except (fitz.FileDataError, OSError, RuntimeError):
        return "unknown", "unreadable", None

    try:
        if document.needs_pass:
            return "encrypted", "unsupported_encrypted", None
        page_count = document.page_count
        if page_count <= 0:
            return "not_encrypted", "zero_pages", 0
        return "not_encrypted", "readable", page_count
    finally:
        document.close()


def build_source_inventory(pdf_dir: Path, registry_path: Path) -> dict[str, Any]:
    """构建当前 PDF 目录的只读迁移基线。"""
    company_mapping, ambiguous_filenames = _load_legacy_company_mapping(registry_path)
    documents: list[dict[str, Any]] = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf"), key=lambda item: item.name):
        encryption_status, readability_status, page_count = _inspect_pdf(pdf_path)
        company_name = company_mapping.get(pdf_path.name)
        logical_mapping_status = (
            "ambiguous" if pdf_path.name in ambiguous_filenames
            else "mapped" if company_name
            else "unmapped"
        )
        logical_document_key = (
            f"legacy:{company_name}:{pdf_path.name}" if company_name else None
        )
        documents.append({
            "filename": pdf_path.name,
            "relative_source_path": pdf_path.name,
            "sha256": _sha256_file(pdf_path),
            "size_bytes": pdf_path.stat().st_size,
            "physical_page_count": page_count,
            "encryption_status": encryption_status,
            "readability_status": readability_status,
            "logical_mapping_status": logical_mapping_status,
            "company_name": company_name,
            "logical_document_key": logical_document_key,
        })
    return {"schema_version": 1, "documents": documents}


def write_source_inventory(inventory: dict[str, Any], output_path: Path) -> None:
    """通过同目录临时文件原子写入冻结清单。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(output_path.name + ".writing")
    temporary_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, output_path)
