"""评测来源文件与冻结清单的只读完整性绑定审计。"""

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import fitz

from .models import EvaluationCase


def _sha256_file(path: Path) -> str:
    """按固定块大小计算文件 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _physical_page_count(path: Path) -> int | None:
    """读取 PDF 物理页数，无法读取时返回空值。"""
    try:
        document = fitz.open(path)
    except (fitz.FileDataError, OSError, RuntimeError):
        return None
    try:
        if document.needs_pass:
            return None
        return document.page_count
    finally:
        document.close()


def _load_inventory(path: Path) -> tuple[dict[str, dict[str, Any]], str | None]:
    """读取冻结清单，拒绝无法解析的清单而不触碰来源目录。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"无法读取来源清单: {path} ({exc.__class__.__name__})"
    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not isinstance(documents, list):
        return {}, f"来源清单缺少 documents 列表: {path}"
    result: dict[str, dict[str, Any]] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        filename = document.get("filename")
        if isinstance(filename, str) and filename.strip():
            result[filename] = document
    return result, None


def _resolve_source(source_file: str, source_roots: tuple[Path, ...]) -> Path | None:
    """只在调用方显式提供的根目录内解析来源文件。"""
    candidate = Path(source_file)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    for root in source_roots:
        resolved = root / candidate
        if resolved.is_file():
            return resolved
    return None


def audit_source_integrity(
    cases: Iterable[EvaluationCase],
    source_roots: Iterable[str | Path],
    inventory_path: str | Path,
) -> dict[str, object]:
    """核对样本来源与冻结清单的文件存在性、哈希、大小和物理页数。"""
    source_files = sorted(
        {
            source.source_file
            for case in cases
            for source in case.expected_sources
        }
    )
    roots = tuple(Path(root) for root in source_roots)
    inventory, inventory_error = _load_inventory(Path(inventory_path))
    missing_inventory_files: list[str] = []
    missing_source_files: list[str] = []
    sha256_mismatches: list[str] = []
    size_mismatches: list[str] = []
    physical_page_mismatches: list[str] = []

    for source_file in source_files:
        expected = inventory.get(source_file)
        if expected is None:
            missing_inventory_files.append(source_file)
            continue
        source_path = _resolve_source(source_file, roots)
        if source_path is None:
            missing_source_files.append(source_file)
            continue
        if _sha256_file(source_path) != expected.get("sha256"):
            sha256_mismatches.append(source_file)
        if source_path.stat().st_size != expected.get("size_bytes"):
            size_mismatches.append(source_file)
        if _physical_page_count(source_path) != expected.get("physical_page_count"):
            physical_page_mismatches.append(source_file)

    return {
        "inventory_path": str(inventory_path),
        "checked_source_count": len(source_files),
        "missing_inventory_files": missing_inventory_files,
        "missing_source_files": missing_source_files,
        "sha256_mismatches": sha256_mismatches,
        "size_mismatches": size_mismatches,
        "physical_page_mismatches": physical_page_mismatches,
        "inventory_error": inventory_error,
        "ready": not (
            inventory_error
            or missing_inventory_files
            or missing_source_files
            or sha256_mismatches
            or size_mismatches
            or physical_page_mismatches
        ),
    }
