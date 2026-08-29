# -*- coding: utf-8 -*-
"""v7 不可变文档版本与内容寻址 blob 仓储。"""

import hashlib
import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .v7_metadata_store import V7MetadataStore


class ContentHashConflictError(RuntimeError):
    """内容哈希键对应的现有 blob 与新内容不一致。"""


@dataclass(frozen=True)
class DocumentVersionRegistration:
    """文档版本登记结果。"""

    logical_document_id: str
    document_version_id: str
    blob_sha256: str
    blob_path: Path
    created: bool


class V7DocumentRepository:
    """通过 v7 元数据事务登记逻辑文档、不可变版本和共享 blob。"""

    _WINDOWS_RESERVED_NAMES = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
    _MAX_DISPLAY_FILENAME_LENGTH = 240

    def __init__(self, store: V7MetadataStore, blob_root: Path) -> None:
        self.store = store
        self.blob_root = Path(blob_root)

    def register_document_version(
        self,
        *,
        logical_document_key: str,
        display_name: str,
        original_filename: str,
        file_content: bytes,
        physical_page_count: int,
    ) -> DocumentVersionRegistration:
        """以内容哈希保存 blob，并原子登记文档版本。"""
        self._validate_registration(
            logical_document_key,
            display_name,
            original_filename,
            file_content,
            physical_page_count,
        )
        blob_sha256 = hashlib.sha256(file_content).hexdigest()
        blob_path = self._write_blob(blob_sha256, file_content)
        self.store.initialize()

        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._ensure_blob_record(connection, blob_sha256, len(file_content))
                logical_document_id = self._find_or_create_logical_document(
                    connection,
                    logical_document_key,
                    display_name,
                )
                existing_version = connection.execute(
                    """
                    SELECT document_version_id FROM v7_document_versions
                    WHERE logical_document_id = ? AND blob_sha256 = ?
                    """,
                    (logical_document_id, blob_sha256),
                ).fetchone()
                if existing_version:
                    connection.commit()
                    return DocumentVersionRegistration(
                        logical_document_id=logical_document_id,
                        document_version_id=existing_version[0],
                        blob_sha256=blob_sha256,
                        blob_path=blob_path,
                        created=False,
                    )

                document_version_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO v7_document_versions(
                        document_version_id, logical_document_id, blob_sha256,
                        original_filename, physical_page_count, index_status
                    ) VALUES (?, ?, ?, ?, ?, 'pending_index')
                    """,
                    (
                        document_version_id,
                        logical_document_id,
                        blob_sha256,
                        original_filename,
                        physical_page_count,
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return DocumentVersionRegistration(
            logical_document_id=logical_document_id,
            document_version_id=document_version_id,
            blob_sha256=blob_sha256,
            blob_path=blob_path,
            created=True,
        )

    def count_blobs(self) -> int:
        """返回已登记的共享 blob 数量。"""
        self.store.initialize()
        with self.store.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM v7_blobs").fetchone()[0])

    def count_document_versions(self) -> int:
        """返回已登记的不可变文档版本数量。"""
        self.store.initialize()
        with self.store.connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM v7_document_versions").fetchone()[0]
            )

    def _write_blob(self, blob_sha256: str, file_content: bytes) -> Path:
        """用哈希文件名原子写入 blob，并检查任何既有文件。"""
        self.blob_root.mkdir(parents=True, exist_ok=True)
        blob_path = self.blob_root / blob_sha256
        if blob_path.exists():
            self._ensure_blob_file_matches(blob_path, blob_sha256, file_content)
            return blob_path

        temporary_path = blob_path.with_name(blob_path.name + ".writing")
        temporary_path.write_bytes(file_content)
        os.replace(temporary_path, blob_path)
        self._ensure_blob_file_matches(blob_path, blob_sha256, file_content)
        return blob_path

    @staticmethod
    def _ensure_blob_file_matches(
        blob_path: Path,
        expected_sha256: str,
        expected_content: bytes,
    ) -> None:
        """检测磁盘 blob 的大小与字节哈希，拒绝哈希键冲突或篡改。"""
        if blob_path.stat().st_size != len(expected_content):
            raise ContentHashConflictError("内容哈希键对应的 blob 大小不一致")
        actual_sha256 = hashlib.sha256(blob_path.read_bytes()).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ContentHashConflictError("内容哈希键对应的 blob 字节不一致")

    @staticmethod
    def _validate_registration(
        logical_document_key: str,
        display_name: str,
        original_filename: str,
        file_content: bytes,
        physical_page_count: int,
    ) -> None:
        """验证仓储边界所需的稳定身份和页数，不尝试修复无效输入。"""
        if not isinstance(logical_document_key, str) or not logical_document_key.strip():
            raise ValueError("logical_document_key 不能为空")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("display_name 不能为空")
        if not isinstance(original_filename, str) or not original_filename.strip():
            raise ValueError("original_filename 不能为空")
        if not V7DocumentRepository._is_safe_display_filename(original_filename):
            raise ValueError("original_filename 不符合 Windows 安全显示名规则")
        if not isinstance(file_content, bytes) or not file_content:
            raise ValueError("file_content 必须为非空 bytes")
        if type(physical_page_count) is not int or physical_page_count <= 0:
            raise ValueError("physical_page_count 必须为正整数")

    @classmethod
    def _is_safe_display_filename(cls, filename: str) -> bool:
        """限制文件名为显示元数据，不接受可被 Windows 解释为路径或设备名的值。"""
        if len(filename) > cls._MAX_DISPLAY_FILENAME_LENGTH:
            return False
        if filename.endswith((" ", ".")) or "/" in filename or "\\" in filename:
            return False
        if any(ord(character) < 32 for character in filename):
            return False
        stem = filename.split(".", 1)[0].upper()
        return stem not in cls._WINDOWS_RESERVED_NAMES

    @staticmethod
    def _ensure_blob_record(
        connection: sqlite3.Connection,
        blob_sha256: str,
        size_bytes: int,
    ) -> None:
        """登记或校验同哈希 blob，阻止大小冲突被误复用。"""
        row = connection.execute(
            "SELECT size_bytes FROM v7_blobs WHERE sha256 = ?",
            (blob_sha256,),
        ).fetchone()
        if row:
            if int(row[0]) != size_bytes:
                raise ContentHashConflictError("内容哈希键对应的数据库大小不一致")
            return
        connection.execute(
            "INSERT INTO v7_blobs(sha256, size_bytes) VALUES (?, ?)",
            (blob_sha256, size_bytes),
        )

    @staticmethod
    def _find_or_create_logical_document(
        connection: sqlite3.Connection,
        logical_document_key: str,
        display_name: str,
    ) -> str:
        """按稳定逻辑键查找或建立文档，不按内容哈希合并语义身份。"""
        row = connection.execute(
            """
            SELECT logical_document_id FROM v7_logical_documents
            WHERE logical_document_key = ?
            """,
            (logical_document_key,),
        ).fetchone()
        if row:
            return str(row[0])
        logical_document_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO v7_logical_documents(
                logical_document_id, logical_document_key, display_name
            ) VALUES (?, ?, ?)
            """,
            (logical_document_id, logical_document_key, display_name),
        )
        return logical_document_id
