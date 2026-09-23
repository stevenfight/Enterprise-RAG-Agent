# -*- coding: utf-8 -*-
"""
知识库管理模块

提供 PDF 文档的列表、上传、删除功能。
数据源: data/stock_data/pdf_reports/ (PDF 文件)
索引状态对照: data/stock_data/databases/vector_dbs/ (已索引的公司目录)

已知限制:
- 删除 PDF 不会清理对应的向量索引数据，需手动重建索引
"""

import logging
import hashlib
import json
import os
import threading
from pathlib import Path
from datetime import datetime
from typing import List

logger = logging.getLogger("knowledge_service")

# 路径常量
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PDF_DIR = _PROJECT_ROOT / "data" / "stock_data" / "pdf_reports"
_VECTOR_DB_DIR = _PROJECT_ROOT / "data" / "stock_data" / "databases" / "vector_dbs"
_MANIFEST_PATH = _PROJECT_ROOT / "data" / "stock_data" / "pdf_ingestion_manifest.json"
_MANIFEST_LOCK = threading.RLock()

# 上传限制: 50MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


def _sha256_bytes(file_content: bytes) -> str:
    """计算上传内容哈希，作为文档版本的稳定身份。"""
    return hashlib.sha256(file_content).hexdigest()


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_manifest() -> dict:
    if not _MANIFEST_PATH.exists():
        return {"version": 1, "documents": {}}
    try:
        data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("PDF 热加载清单不可读") from exc
    if not isinstance(data, dict) or not isinstance(data.get("documents"), dict):
        raise RuntimeError("PDF 热加载清单格式无效")
    return data


def _write_manifest(manifest: dict) -> None:
    """通过临时文件替换清单，避免进程中断留下半份 JSON。"""
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _MANIFEST_PATH.with_name(_MANIFEST_PATH.name + ".uploading")
    temp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, _MANIFEST_PATH)


def _manifest_document(filename: str) -> dict | None:
    with _MANIFEST_LOCK:
        return _read_manifest()["documents"].get(filename)


def get_documents() -> List[dict]:
    """获取所有 PDF 文档列表，含索引状态"""
    _PDF_DIR.mkdir(parents=True, exist_ok=True)

    # 获取已索引的公司名（vector_dbs 下的子目录）
    indexed_companies = set()
    if _VECTOR_DB_DIR.exists():
        for d in _VECTOR_DB_DIR.iterdir():
            if d.is_dir():
                indexed_companies.add(d.name)

    logger.info("[knowledge] 获取文档列表 | 已索引公司: %d 个 | 目录: %s",
                 len(indexed_companies), str(_VECTOR_DB_DIR))

    documents = []
    for pdf_file in sorted(_PDF_DIR.glob("*.pdf"),
                           key=lambda f: f.stat().st_mtime, reverse=True):
        stat = pdf_file.stat()
        filename = pdf_file.name

        manifest_doc = _manifest_document(filename)
        # 清单记录是热加载/重试后的权威状态；仅在没有清单记录时兼容旧向量目录推断。
        legacy_indexed = any(company in filename for company in indexed_companies)
        index_status = manifest_doc.get("index_status") if manifest_doc else ("indexed" if legacy_indexed else "not_indexed")
        indexed = index_status == "indexed"
        documents.append({
            "filename": filename,
            "size": stat.st_size,
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "upload_time": datetime.fromtimestamp(stat.st_mtime)
                .strftime("%Y-%m-%d %H:%M:%S"),
            "indexed": indexed,
            "index_status": index_status,
            "sha256": manifest_doc.get("sha256") if manifest_doc else None,
            "index_generation": manifest_doc.get("index_generation") if manifest_doc else None,
            "index_error": manifest_doc.get("index_error") if manifest_doc else None,
            "index_attempts": int(manifest_doc.get("index_attempts", 0)) if manifest_doc else 0,
        })

    logger.info("[knowledge] 文档列表获取完成 | 共 %d 个文件 | 已索引: %d 个",
                 len(documents),
                 sum(1 for d in documents if d["indexed"]))
    return documents


def upload_pdf(
    file_content: bytes,
    filename: str,
    *,
    v7_flags=None,
    v7_upload_service=None,
    logical_document_key: str | None = None,
    display_name: str | None = None,
) -> dict:
    """上传 PDF 文件

    Raises:
        ValueError: 文件非 PDF 或超过大小限制
    """
    logger.info("[knowledge] 开始上传 PDF | 原始文件名: %s | 大小: %d bytes",
                filename, len(file_content))

    # v7 多模态路径显式开启时，使用不可变版本仓储；默认继续执行 legacy 逻辑。
    if v7_flags is not None and getattr(v7_flags, "multimodal_enabled", False):
        if v7_upload_service is None:
            raise RuntimeError("multimodal 上传需要 v7_upload_service")
        if not logical_document_key:
            raise ValueError("multimodal 上传需要 logical_document_key")
        result = v7_upload_service.upload(
            logical_document_key=logical_document_key,
            display_name=display_name or filename,
            original_filename=filename,
            file_content=file_content,
        )
        registration = result.registration
        return {
            "filename": filename,
            "size": len(file_content),
            "size_mb": round(len(file_content) / 1024 / 1024, 2),
            "sha256": registration.blob_sha256,
            "index_status": "pending_index",
            "processing_status": "pending_processing",
            "idempotent": not registration.created,
            "logical_document_id": registration.logical_document_id,
            "document_version_id": registration.document_version_id,
            "physical_page_count": result.physical_page_count,
        }

    # 安全检查：只允许 .pdf
    if not filename.lower().endswith(".pdf"):
        logger.warning("[knowledge] 上传被拒绝: 非 PDF 文件 | 文件名: %s", filename)
        raise ValueError("仅支持 PDF 文件")

    if not file_content.startswith(b"%PDF-"):
        logger.warning("[knowledge] 上传被拒绝: PDF 文件头无效 | 文件名: %s", filename)
        raise ValueError("PDF 文件内容无效")

    # 文件大小限制
    if len(file_content) > MAX_UPLOAD_SIZE:
        size_mb = round(len(file_content) / 1024 / 1024, 2)
        logger.warning("[knowledge] 上传被拒绝: 文件过大 | 文件名: %s | 大小: %.2f MB",
                        filename, size_mb)
        raise ValueError(
            f"文件过大 ({size_mb} MB)，最大允许 50 MB")

    _PDF_DIR.mkdir(parents=True, exist_ok=True)

    # 防止路径遍历攻击
    safe_name = Path(filename).name
    dest_path = _PDF_DIR / safe_name

    sha256 = _sha256_bytes(file_content)
    # 相同文件重复上传直接返回已有版本，不重复触发热加载。
    with _MANIFEST_LOCK:
        manifest = _read_manifest()
        existing = manifest["documents"].get(safe_name)
        if existing and existing.get("sha256") == sha256 and dest_path.exists():
            return {
                "filename": safe_name,
                "size": len(file_content),
                "size_mb": round(len(file_content) / 1024 / 1024, 2),
                "sha256": sha256,
                "index_status": existing.get("index_status", "pending_index"),
                "idempotent": True,
            }

    # 检测是否覆盖已有文件；不同内容会形成新的待索引版本。
    if dest_path.exists():
        existing_size = dest_path.stat().st_size
        logger.warning("[knowledge] 将覆盖已有文件 | 文件名: %s | 已有大小: %d bytes | 新文件大小: %d bytes",
                        safe_name, existing_size, len(file_content))

    temp_path = dest_path.with_name(dest_path.name + ".uploading")
    backup_path = dest_path.with_name(dest_path.name + ".previous")
    had_previous = dest_path.exists()
    try:
        with open(temp_path, "wb") as f:
            f.write(file_content)
        if had_previous:
            os.replace(dest_path, backup_path)
        os.replace(temp_path, dest_path)
    except OSError as e:
        logger.error("[knowledge] PDF 写入磁盘失败 | 文件名: %s | 路径: %s | 错误: %s",
                      safe_name, str(dest_path), str(e))
        if temp_path.exists():
            temp_path.unlink()
        if had_previous and backup_path.exists() and not dest_path.exists():
            os.replace(backup_path, dest_path)
        raise

    with _MANIFEST_LOCK:
        manifest = _read_manifest()
        previous = manifest["documents"].get(safe_name, {})
        manifest["documents"][safe_name] = {
            "filename": safe_name,
            "sha256": sha256,
            "size": len(file_content),
            "index_status": "pending_index",
            "index_generation": None,
            "index_error": None,
            "index_attempts": 0,
            "version": int(previous.get("version", 0)) + 1,
        }
        try:
            _write_manifest(manifest)
        except Exception:
            if dest_path.exists():
                dest_path.unlink()
            if had_previous and backup_path.exists():
                os.replace(backup_path, dest_path)
            raise

    if backup_path.exists():
        backup_path.unlink()

    logger.info("[knowledge] PDF 上传成功 | 文件名: %s | 路径: %s | 大小: %d bytes (%.2f MB)",
                 safe_name, str(dest_path), len(file_content),
                 round(len(file_content) / 1024 / 1024, 2))

    return {
        "filename": safe_name,
        "size": len(file_content),
        "size_mb": round(len(file_content) / 1024 / 1024, 2),
        "sha256": sha256,
        "index_status": "pending_index",
        "idempotent": False,
    }


def get_pending_documents() -> List[dict]:
    """返回等待解析或重建索引的文档，供后续后台 worker 热加载。"""
    pending = []
    for document in get_documents():
        if document["index_status"] not in {"pending_index", "index_failed"}:
            continue
        manifest_document = _manifest_document(document["filename"])
        if manifest_document is not None and not manifest_document.get("index_retryable", True):
            continue
        pending.append(document)
    return pending


def sync_pdf_directory() -> dict[str, list[str]]:
    """登记直接放入 PDF 目录的新文件，支持无 API 上传的热加载入口。"""
    _PDF_DIR.mkdir(parents=True, exist_ok=True)
    registered = []
    invalid = []
    legacy_indexed_files = set()
    registry_path = _VECTOR_DB_DIR / "company_registry.json"
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for info in registry.get("companies", {}).values():
                legacy_indexed_files.update(info.get("source_files", []))
        except (OSError, json.JSONDecodeError):
            logger.warning("[knowledge] 旧索引注册表不可读，无法自动认领历史 PDF")
    with _MANIFEST_LOCK:
        manifest = _read_manifest()
        changed = False
        for pdf_path in sorted(_PDF_DIR.glob("*.pdf")):
            try:
                with pdf_path.open("rb") as file_handle:
                    if file_handle.read(5) != b"%PDF-":
                        invalid.append(pdf_path.name)
                        continue
                sha256 = _sha256_file(pdf_path)
            except OSError:
                invalid.append(pdf_path.name)
                continue
            existing = manifest["documents"].get(pdf_path.name)
            if existing and existing.get("sha256") == sha256:
                continue
            is_legacy_indexed = pdf_path.name in legacy_indexed_files
            manifest["documents"][pdf_path.name] = {
                "filename": pdf_path.name,
                "sha256": sha256,
                "size": pdf_path.stat().st_size,
                "index_status": "indexed" if is_legacy_indexed else "pending_index",
                "index_generation": "legacy" if is_legacy_indexed else None,
                "index_error": None,
                "index_attempts": 0,
                "version": int(existing.get("version", 0)) + 1 if existing else 1,
            }
            if not is_legacy_indexed:
                registered.append(pdf_path.name)
            changed = True
        if changed:
            _write_manifest(manifest)
    return {"registered": registered, "invalid": invalid}


def _update_index_status(filename: str, sha256: str, status: str, **updates) -> bool:
    with _MANIFEST_LOCK:
        manifest = _read_manifest()
        document = manifest["documents"].get(filename)
        if not document or document.get("sha256") != sha256:
            return False
        document.update({"index_status": status, **updates})
        _write_manifest(manifest)
        return True


def mark_pdf_indexed(
    filename: str,
    sha256: str,
    index_generation: str,
    index_attempts: int | None = None,
) -> bool:
    """仅允许当前文件版本标记为已索引，阻止旧任务覆盖新上传版本。"""
    updates = {
        "index_generation": index_generation,
        "index_error": None,
        "index_error_category": None,
        "index_retryable": False,
    }
    if index_attempts is not None:
        updates["index_attempts"] = index_attempts
    return _update_index_status(filename, sha256, "indexed", **updates)


def mark_pdf_index_failed(
    filename: str,
    sha256: str,
    error: str,
    index_attempts: int | None = None,
    *,
    retryable: bool = True,
    error_category: str = "unknown",
) -> bool:
    """记录当前版本的索引失败，保留待重试状态和错误原因。"""
    updates = {
        "index_error": str(error),
        "index_error_category": error_category,
        "index_retryable": retryable,
    }
    if index_attempts is not None:
        updates["index_attempts"] = index_attempts
    return _update_index_status(filename, sha256, "index_failed", **updates)


def retry_pdf_index(filename: str) -> bool:
    """显式重新放行失败文档，重置自动重试次数。"""
    with _MANIFEST_LOCK:
        manifest = _read_manifest()
        document = manifest["documents"].get(filename)
        if not document or document.get("index_status") != "index_failed":
            return False
        document.update({
            "index_status": "pending_index",
            "index_error": None,
            "index_error_category": None,
            "index_retryable": True,
            "index_attempts": 0,
        })
        _write_manifest(manifest)
    return True


def delete_pdf(filename: str, *, deletion_coordinator=None) -> bool:
    """删除 PDF 文件（不清理对应的向量索引数据）

    传入 deletion_coordinator（M3.6）时，先为同名全部未删除的 V7 文档版本
    创建删除请求（幂等），再执行 legacy 文件与清单清理。

    Returns:
        True: 删除成功
        False: 文件不存在
    """
    logger.info("[knowledge] 收到删除请求 | 文件名: %s", filename)

    filepath = _PDF_DIR / filename

    # 防止路径遍历攻击
    if ".." in filename or "/" in filename or "\\" in filename:
        logger.warning("[knowledge] 删除被拒绝: 文件名包含危险路径字符 | 文件名: %s", filename)
        return False

    if not filepath.exists():
        logger.warning("[knowledge] 删除失败: 文件不存在 | 文件名: %s | 路径: %s",
                        filename, str(filepath))
        return False

    # M3.6：V7 删除请求先于文件删除创建，失败时不触碰 legacy 文件状态
    if deletion_coordinator is not None:
        deletion_coordinator.request_deletion_by_original_filename(filename)

    file_size = filepath.stat().st_size
    logger.info("[knowledge] 开始删除 PDF | 文件名: %s | 路径: %s | 大小: %d bytes",
                 filename, str(filepath), file_size)

    deleting_path = filepath.with_name(filepath.name + ".deleting")
    try:
        os.replace(filepath, deleting_path)
    except OSError as e:
        logger.error("[knowledge] PDF 删除失败: 磁盘错误 | 文件名: %s | 路径: %s | 错误: %s",
                      filename, str(filepath), str(e))
        raise

    with _MANIFEST_LOCK:
        manifest = _read_manifest()
        manifest["documents"].pop(filename, None)
        try:
            _write_manifest(manifest)
        except Exception:
            os.replace(deleting_path, filepath)
            raise

    try:
        deleting_path.unlink()
    except OSError:
        logger.warning("[knowledge] PDF 临时删除文件清理失败 | 路径: %s", str(deleting_path))

    logger.info("[knowledge] PDF 已删除 | 文件名: %s | 路径: %s | 释放空间: %d bytes (%.2f MB)",
                 filename, str(filepath), file_size,
                 round(file_size / 1024 / 1024, 2))
    return True
