"""评测数据集与来源清单的只读版本绑定审计。"""

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    """按固定块大小计算文件 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_path(path: str | Path) -> Path:
    """把路径规范化为当前运行平台的绝对路径。"""
    return Path(str(path).replace("\\", "/")).resolve()


def _path_matches(expected: object, actual: Path) -> bool:
    """比较清单中的绝对或相对路径与 CLI 实际路径。"""
    if not isinstance(expected, str) or not expected.strip():
        return False
    expected_path = Path(expected.replace("\\", "/"))
    if expected_path.is_absolute():
        return _normalise_path(expected_path) == actual
    return _normalise_path(Path.cwd() / expected_path) == actual


def _load_manifest(path: Path) -> tuple[dict[str, Any], str | None]:
    """读取绑定清单，错误以报告字段返回而不修改任何文件。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"无法读取绑定清单: {path} ({exc.__class__.__name__})"
    if not isinstance(payload, dict):
        return {}, "绑定清单根节点必须是对象"
    if payload.get("schema_version") != 1:
        return {}, "绑定清单 schema_version 必须为 1"
    return payload, None


def audit_source_binding(
    dataset_path: str | Path,
    source_inventory_path: str | Path,
    manifest_path: str | Path,
) -> dict[str, object]:
    """核对数据集和来源清单的路径、存在性及 SHA-256。"""
    dataset = _normalise_path(dataset_path)
    source_inventory = _normalise_path(source_inventory_path)
    manifest = _normalise_path(manifest_path)
    payload, manifest_error = _load_manifest(manifest)
    path_mismatches: list[str] = []
    missing_files: list[str] = []
    hash_mismatches: list[str] = []
    actual_sha256: dict[str, str] = {}

    if manifest_error is None:
        path_fields = (
            ("dataset", "dataset_path", dataset),
            ("source_inventory", "source_inventory_path", source_inventory),
        )
        for label, field, actual in path_fields:
            if not _path_matches(payload.get(field), actual):
                path_mismatches.append(label)

        for label, actual, field in (
            ("dataset", dataset, "dataset_sha256"),
            ("source_inventory", source_inventory, "source_inventory_sha256"),
        ):
            if not actual.is_file():
                missing_files.append(label)
                continue
            digest = _sha256_file(actual)
            actual_sha256[label] = digest
            if payload.get(field) != digest:
                hash_mismatches.append(label)

    return {
        "manifest_path": str(manifest_path),
        "manifest_error": manifest_error,
        "path_mismatches": path_mismatches,
        "missing_files": missing_files,
        "hash_mismatches": hash_mismatches,
        "actual_sha256": actual_sha256,
        "ready": not (
            manifest_error
            or path_mismatches
            or missing_files
            or hash_mismatches
        ),
    }
