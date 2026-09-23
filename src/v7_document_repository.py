# -*- coding: utf-8 -*-
"""v7 不可变文档版本与内容寻址 blob 仓储。"""

import hashlib
import os
import sqlite3
import time
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

    def get_active_document_version(self, logical_document_id: str) -> str | None:
        """返回逻辑文档当前 active 的 document_version_id；从未显式激活时返回 None。

        新版本登记始终为 pending_index，登记动作绝不改变 active；只有
        promote_document_version_to_active 在索引完成后显式切换。
        """
        if not isinstance(logical_document_id, str) or not logical_document_id.strip():
            raise ValueError("logical_document_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT document_version_id FROM v7_document_versions
                WHERE logical_document_id = ? AND index_status = 'active'
                """,
                (logical_document_id,),
            ).fetchone()
        return str(row[0]) if row else None

    def promote_document_version_to_active(self, document_version_id: str) -> None:
        """索引完成后显式激活版本：目标版本置 active，同逻辑文档旧 active 原子降级为 superseded。

        这是唯一改变 active 版本的入口；调用方契约是仅在完整索引后调用。
        """
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise ValueError("document_version_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT logical_document_id FROM v7_document_versions WHERE document_version_id = ?",
                    (document_version_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("document_version_id 不存在")
                logical_document_id = row[0]
                connection.execute(
                    """
                    UPDATE v7_document_versions SET index_status = 'superseded'
                    WHERE logical_document_id = ? AND index_status = 'active'
                    """,
                    (logical_document_id,),
                )
                connection.execute(
                    """
                    UPDATE v7_document_versions SET index_status = 'active'
                    WHERE document_version_id = ?
                    """,
                    (document_version_id,),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

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

    def blob_reference_count(self, blob_sha256: str) -> int:
        """返回当前不可变文档版本对共享 blob 的引用数。"""
        self.store.initialize()
        with self.store.connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM v7_document_versions WHERE blob_sha256 = ?",
                    (blob_sha256,),
                ).fetchone()[0]
            )

    def resolve_document_blob_path(self, document_version_id: str) -> Path:
        """仅按已登记 document version 解析 blob，拒绝调用方直接按路径或哈希读取。"""
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise ValueError("document_version_id 不能为空")
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT blob_sha256, index_status FROM v7_document_versions WHERE document_version_id = ?",
                (document_version_id,),
            ).fetchone()
        if row is None:
            raise ValueError("document_version_id 不存在或不可见")
        if row[1] == "deleting":
            raise ValueError("document_version_id 正在删除中，不可解析 blob")
        blob_path = self.blob_root / row[0]
        if not blob_path.is_file():
            raise FileNotFoundError("已登记 blob 文件不存在")
        return blob_path

    def reclaim_blob_if_eligible(
        self,
        blob_sha256: str,
        *,
        retention_seconds: float,
        now: float | None = None,
    ) -> bool:
        """仅在零引用并已超过保留期时删除内容寻址 blob。"""
        if retention_seconds < 0:
            raise ValueError("retention_seconds 不能为负数")
        now = time.time() if now is None else now
        blob_path = self.blob_root / blob_sha256
        self.store.initialize()
        with self.store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                # M3.11：deleting 版本已从索引可见性摘除，不再持有共享 blob 引用
                reference_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM v7_document_versions WHERE blob_sha256 = ? AND index_status != 'deleting'",
                        (blob_sha256,),
                    ).fetchone()[0]
                )
                if reference_count:
                    connection.rollback()
                    return False
                total_reference_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM v7_document_versions WHERE blob_sha256 = ?",
                        (blob_sha256,),
                    ).fetchone()[0]
                )
                row = connection.execute(
                    "SELECT 1 FROM v7_blobs WHERE sha256 = ?", (blob_sha256,)
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return False
                if not blob_path.is_file():
                    raise FileNotFoundError("待回收 blob 文件不存在")
                if now - blob_path.stat().st_mtime < retention_seconds:
                    connection.rollback()
                    return False
                blob_path.unlink()
                if total_reference_count == 0:
                    # 仅当所有版本行已物理移除时才删除登记行；
                    # deleting 版本行的外键引用保护软删审计链（M3.12）
                    connection.execute("DELETE FROM v7_blobs WHERE sha256 = ?", (blob_sha256,))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return True

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
