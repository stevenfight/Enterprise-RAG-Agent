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
from pathlib import Path
from datetime import datetime
from typing import List

logger = logging.getLogger("knowledge_service")

# 路径常量
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PDF_DIR = _PROJECT_ROOT / "data" / "stock_data" / "pdf_reports"
_VECTOR_DB_DIR = _PROJECT_ROOT / "data" / "stock_data" / "databases" / "vector_dbs"

# 上传限制: 50MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


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

        # 判断索引状态：文件名包含已索引的公司名
        indexed = any(company in filename for company in indexed_companies)

        documents.append({
            "filename": filename,
            "size": stat.st_size,
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "upload_time": datetime.fromtimestamp(stat.st_mtime)
                .strftime("%Y-%m-%d %H:%M:%S"),
            "indexed": indexed,
        })

    logger.info("[knowledge] 文档列表获取完成 | 共 %d 个文件 | 已索引: %d 个",
                 len(documents),
                 sum(1 for d in documents if d["indexed"]))
    return documents


def upload_pdf(file_content: bytes, filename: str) -> dict:
    """上传 PDF 文件

    Raises:
        ValueError: 文件非 PDF 或超过大小限制
    """
    logger.info("[knowledge] 开始上传 PDF | 原始文件名: %s | 大小: %d bytes",
                 filename, len(file_content))

    # 安全检查：只允许 .pdf
    if not filename.lower().endswith(".pdf"):
        logger.warning("[knowledge] 上传被拒绝: 非 PDF 文件 | 文件名: %s", filename)
        raise ValueError("仅支持 PDF 文件")

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

    # 检测是否覆盖已有文件
    if dest_path.exists():
        existing_size = dest_path.stat().st_size
        logger.warning("[knowledge] 将覆盖已有文件 | 文件名: %s | 已有大小: %d bytes | 新文件大小: %d bytes",
                        safe_name, existing_size, len(file_content))

    try:
        with open(dest_path, "wb") as f:
            f.write(file_content)
    except OSError as e:
        logger.error("[knowledge] PDF 写入磁盘失败 | 文件名: %s | 路径: %s | 错误: %s",
                      safe_name, str(dest_path), str(e))
        raise

    logger.info("[knowledge] PDF 上传成功 | 文件名: %s | 路径: %s | 大小: %d bytes (%.2f MB)",
                 safe_name, str(dest_path), len(file_content),
                 round(len(file_content) / 1024 / 1024, 2))

    return {
        "filename": safe_name,
        "size": len(file_content),
        "size_mb": round(len(file_content) / 1024 / 1024, 2),
    }


def delete_pdf(filename: str) -> bool:
    """删除 PDF 文件（不清理对应的向量索引数据）

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

    file_size = filepath.stat().st_size
    logger.info("[knowledge] 开始删除 PDF | 文件名: %s | 路径: %s | 大小: %d bytes",
                 filename, str(filepath), file_size)

    try:
        filepath.unlink()
    except OSError as e:
        logger.error("[knowledge] PDF 删除失败: 磁盘错误 | 文件名: %s | 路径: %s | 错误: %s",
                      filename, str(filepath), str(e))
        raise

    logger.info("[knowledge] PDF 已删除 | 文件名: %s | 路径: %s | 释放空间: %d bytes (%.2f MB)",
                 filename, str(filepath), file_size,
                 round(file_size / 1024 / 1024, 2))
    return True
