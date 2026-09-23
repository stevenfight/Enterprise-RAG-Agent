# -*- coding: utf-8 -*-
"""将既有制品决策转换为受边界约束的可执行复用计划。"""

import re
from pathlib import Path
from typing import Any, Iterable


_IMAGE_REFERENCE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_TARGETED_TASK_KINDS = {
    "failed_page",
    "complex_table",
    "chart",
    "scanned_page",
    "location_failure",
}


def _is_within_directory(path: Path, directory: Path) -> bool:
    """判断解析后的路径是否仍受 Markdown 根目录控制。"""
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _local_asset_paths(markdown_path: Path, markdown_root: Path) -> list[str]:
    """读取已存在且位于根目录内的本地图片，不下载或补造任何制品。"""
    content = markdown_path.read_text(encoding="utf-8")
    paths: list[str] = []
    for match in _IMAGE_REFERENCE_PATTERN.finditer(content):
        reference = match.group(1).strip()
        if reference.lower().startswith(("http://", "https://", "data:")):
            continue
        candidate = (markdown_path.parent / reference).resolve()
        if _is_within_directory(candidate, markdown_root) and candidate.is_file():
            paths.append(str(candidate))
    return paths


def _targeted_tasks_for(
    filename: str,
    targeted_requests: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """仅转换具有明确页码、类型和原因的定向处理请求。"""
    tasks: list[dict[str, Any]] = []
    for request in targeted_requests:
        if request.get("filename") != filename:
            continue
        task_kind = request.get("task_kind")
        pages = request.get("physical_pages")
        reason = request.get("reason")
        if (
            task_kind not in _TARGETED_TASK_KINDS
            or not isinstance(pages, list)
            or not pages
            or any(not isinstance(page, int) or page <= 0 for page in pages)
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            continue
        tasks.append({
            "task_kind": task_kind,
            "physical_pages": sorted(set(pages)),
            "reason": reason,
        })
    return tasks


def build_reuse_execution_plan(
    decisions: Iterable[dict[str, Any]],
    asset_documents: Iterable[dict[str, Any]],
    markdown_root: Path,
    targeted_requests: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """生成复用计划；未通过路径和文件门禁的文档回退为明确的全量重提取。"""
    root_path = Path(markdown_root).resolve()
    assets_by_filename = {
        item.get("filename"): item
        for item in asset_documents
        if isinstance(item.get("filename"), str)
    }
    target_requests = tuple(targeted_requests)
    documents: list[dict[str, Any]] = []

    for decision in sorted(decisions, key=lambda item: str(item.get("filename", ""))):
        filename = str(decision.get("filename", ""))
        asset = assets_by_filename.get(filename, {})
        result: dict[str, Any] = {
            "filename": filename,
            "decision": decision.get("decision"),
            "targeted_tasks": [],
        }
        if decision.get("decision") not in {"REUSE", "ENRICH"}:
            result.update({
                "action": "FULL_REEXTRACT",
                "error_status": decision.get("error_status"),
            })
            documents.append(result)
            continue

        markdown_filename = asset.get("markdown_filename")
        if asset.get("markdown_status") != "matched" or not isinstance(markdown_filename, str):
            result.update({"action": "FULL_REEXTRACT", "error_status": "missing_markdown"})
            documents.append(result)
            continue

        markdown_path = (root_path / markdown_filename).resolve()
        if not _is_within_directory(markdown_path, root_path):
            result.update({"action": "FULL_REEXTRACT", "error_status": "unsafe_markdown_path"})
            documents.append(result)
            continue
        if not markdown_path.is_file():
            result.update({"action": "FULL_REEXTRACT", "error_status": "missing_markdown_file"})
            documents.append(result)
            continue

        result.update({
            "action": "REUSE_EXISTING_ASSETS",
            "markdown_path": str(markdown_path),
            "local_asset_paths": _local_asset_paths(markdown_path, root_path),
            "targeted_tasks": _targeted_tasks_for(filename, target_requests),
            "error_status": decision.get("error_status"),
        })
        documents.append(result)

    return {"schema_version": 1, "documents": documents}
