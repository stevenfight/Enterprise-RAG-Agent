# -*- coding: utf-8 -*-
"""既有 Markdown 多模态制品的只读清点工具。"""

import json
import os
import re
from pathlib import Path
from typing import Any


_IMAGE_REFERENCE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_HTML_TABLE_PATTERN = re.compile(r"<table\b", re.IGNORECASE)
_MARKDOWN_TABLE_PATTERN = re.compile(r"(?m)^(?:\s*\|.*\|\s*\r?\n){2,}")
_FORMULA_MARKER_PATTERN = re.compile(r"\$\$|(?<!\$)\$(?!\$)")


def _is_remote_reference(reference: str) -> bool:
    """判断图片引用是否为网络或内嵌数据，二者都不在本地读取。"""
    lowered = reference.lower()
    return lowered.startswith(("http://", "https://", "data:"))


def _is_within_directory(path: Path, directory: Path) -> bool:
    """防止 Markdown 相对路径越出受控制品根目录。"""
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _inspect_markdown(markdown_path: Path, markdown_root: Path) -> dict[str, Any]:
    """统计 Markdown 中已有的表格、公式和图片引用，不生成或下载制品。"""
    content = markdown_path.read_text(encoding="utf-8")
    local_references: list[str] = []
    missing_assets: list[str] = []
    unsafe_references: list[str] = []
    existing_local_image_count = 0
    remote_image_reference_count = 0
    root_path = markdown_root.resolve()

    for match in _IMAGE_REFERENCE_PATTERN.finditer(content):
        reference = match.group(1).strip()
        if _is_remote_reference(reference):
            remote_image_reference_count += 1
            continue
        local_references.append(reference)
        candidate = (markdown_path.parent / reference).resolve()
        if not _is_within_directory(candidate, root_path):
            unsafe_references.append(reference)
        elif candidate.is_file():
            existing_local_image_count += 1
        else:
            missing_assets.append(reference)

    return {
        "markdown_table_count": len(_MARKDOWN_TABLE_PATTERN.findall(content)),
        "html_table_count": len(_HTML_TABLE_PATTERN.findall(content)),
        "formula_marker_count": len(_FORMULA_MARKER_PATTERN.findall(content)),
        "local_image_reference_count": len(local_references),
        "existing_local_image_count": existing_local_image_count,
        "missing_local_image_count": len(missing_assets),
        "remote_image_reference_count": remote_image_reference_count,
        "missing_local_assets": missing_assets,
        "unsafe_local_references": unsafe_references,
    }


def build_document_asset_inventory(pdf_dir: Path, markdown_dir: Path) -> dict[str, Any]:
    """为每份源 PDF 清点同名 Markdown 及其可复用制品。"""
    markdown_files = {item.stem: item for item in markdown_dir.glob("*.md")}
    documents: list[dict[str, Any]] = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf"), key=lambda item: item.name):
        markdown_path = markdown_files.get(pdf_path.stem)
        if markdown_path is None:
            documents.append({
                "filename": pdf_path.name,
                "markdown_status": "missing",
                "asset_status": "incomplete",
                "missing_local_assets": [],
                "unsafe_local_references": [],
            })
            continue

        details = _inspect_markdown(markdown_path, markdown_dir)
        asset_status = (
            "incomplete"
            if details["missing_local_assets"] or details["unsafe_local_references"]
            else "complete"
        )
        documents.append({
            "filename": pdf_path.name,
            "markdown_status": "matched",
            "markdown_filename": markdown_path.name,
            "asset_status": asset_status,
            **details,
        })

    orphan_markdown_files = sorted(
        item.name for stem, item in markdown_files.items()
        if not (pdf_dir / f"{stem}.pdf").is_file()
    )
    return {
        "schema_version": 1,
        "documents": documents,
        "orphan_markdown_files": orphan_markdown_files,
    }


def write_document_asset_inventory(inventory: dict[str, Any], output_path: Path) -> None:
    """原子写入仅供诊断和复核的制品清点报告。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(output_path.name + ".writing")
    temporary_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, output_path)
