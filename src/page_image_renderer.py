# -*- coding: utf-8 -*-
"""基于 PDF 物理页的本地页图与缩略图渲染器。"""

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(frozen=True)
class PageImageArtifact:
    """已渲染的物理页图制品。"""

    artifact_id: str
    document_version_id: str
    physical_page_number: int
    image_path: Path
    thumbnail_path: Path
    created: bool


class PageImageRenderer:
    """按物理页渲染并缓存页图，不处理文档印刷页标签。"""

    RENDER_VERSION = "v1"
    _SAFE_DOCUMENT_VERSION_ID = re.compile(r"^[A-Za-z0-9_-]+$")

    def __init__(self, output_root: Path) -> None:
        self.output_root = Path(output_root)

    def render(
        self,
        document_version_id: str,
        pdf_path: Path,
        *,
        physical_page_number: int,
    ) -> PageImageArtifact:
        """渲染指定物理页及缩略图，命中完整缓存时不重复渲染。"""
        if (
            not isinstance(document_version_id, str)
            or not self._SAFE_DOCUMENT_VERSION_ID.fullmatch(document_version_id)
        ):
            raise ValueError("document_version_id 不符合页图路径安全规则")
        if type(physical_page_number) is not int or physical_page_number <= 0:
            raise ValueError("物理页必须为正整数")
        pdf_path = Path(pdf_path)
        pdf_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        artifact_id = hashlib.sha256(
            f"{document_version_id}:{pdf_hash}:{physical_page_number}:{self.RENDER_VERSION}".encode(
                "utf-8"
            )
        ).hexdigest()
        artifact_dir = self.output_root / document_version_id
        image_path = artifact_dir / f"{artifact_id}.png"
        thumbnail_path = artifact_dir / f"{artifact_id}.thumbnail.png"
        if image_path.is_file() and thumbnail_path.is_file():
            return PageImageArtifact(
                artifact_id,
                document_version_id,
                physical_page_number,
                image_path,
                thumbnail_path,
                False,
            )

        artifact_dir.mkdir(parents=True, exist_ok=True)
        document = fitz.open(pdf_path)
        try:
            if physical_page_number > document.page_count:
                raise ValueError(
                    f"物理页 {physical_page_number} 超出 PDF 总页数 {document.page_count}"
                )
            page = document.load_page(physical_page_number - 1)
            self._save_pixmap_atomic(
                page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False),
                image_path,
            )
            self._save_pixmap_atomic(
                page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5), alpha=False),
                thumbnail_path,
            )
        finally:
            document.close()
        return PageImageArtifact(
            artifact_id,
            document_version_id,
            physical_page_number,
            image_path,
            thumbnail_path,
            True,
        )

    @staticmethod
    def _save_pixmap_atomic(pixmap: fitz.Pixmap, output_path: Path) -> None:
        """写入后原子替换页图，避免读取端看到半张 PNG。"""
        temporary_path = PageImageRenderer._temporary_path(output_path)
        try:
            pixmap.save(temporary_path)
            os.replace(temporary_path, output_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _temporary_path(output_path: Path) -> Path:
        """生成短临时 PNG 路径，避免深目录下超过 Windows 文件路径限制。"""
        return output_path.with_name(f".{uuid.uuid4().hex}{output_path.suffix}")
