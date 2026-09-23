# -*- coding: utf-8 -*-
"""默认关闭的 V7 文档处理协调器。"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import fitz

from .document_asset_manifest_repository import (
    DocumentAssetManifest,
    DocumentAssetManifestRepository,
    ManifestPageImageCompleteness,
)
from .durable_execution import AttemptClaim, DurableExecutionStore
from .page_artifact_repository import PageArtifactRepository, RegisteredPageArtifact
from .page_image_renderer import PageImageRenderer
from .page_router import PageRouteDecision, PageRouter, PageSignals
from .parse_batch_repository import ParseBatchRecord, ParseBatchRepository
from .v7_document_deletion import V7DocumentDeletionService


@dataclass(frozen=True)
class PageRoutingSnapshot:
    """一次经校验的文档处理路由快照，供后续受控视觉分发审计。"""

    manifest_id: str
    document_version_id: str
    decisions: tuple[PageRouteDecision, ...]


class V7DocumentProcessingCoordinator:
    """以 document version 和 blob 为唯一身份协调 V7 的页级处理证据。"""

    def __init__(
        self,
        *,
        manifest_repository: DocumentAssetManifestRepository,
        parse_batch_repository: ParseBatchRepository,
        page_image_renderer: PageImageRenderer,
        page_artifact_repository: PageArtifactRepository,
        durable_execution_store: DurableExecutionStore | None = None,
        page_router: PageRouter | None = None,
    ) -> None:
        stores = {
            id(manifest_repository.store),
            id(parse_batch_repository.store),
            id(page_artifact_repository.store),
        }
        if len(stores) != 1:
            raise ValueError("V7 协调器的所有仓储必须使用同一个 metadata store")
        self.manifest_repository = manifest_repository
        self.parse_batch_repository = parse_batch_repository
        self.page_image_renderer = page_image_renderer
        self.page_artifact_repository = page_artifact_repository
        self.store = manifest_repository.store
        if (
            durable_execution_store is not None
            and durable_execution_store.metadata_store is not self.store
        ):
            raise ValueError("V7 协调器的执行仓储必须复用同一个 metadata store")
        self.execution_store = durable_execution_store
        self.page_router = page_router or PageRouter()

    def claim_processing_attempt(
        self,
        run_id: str,
        document_version_id: str,
        owner_token: str,
        *,
        now: float | None = None,
    ) -> AttemptClaim:
        """为文档处理领取 C0 租约，不在 M 内维护平行步骤状态。"""
        if self.execution_store is None:
            raise RuntimeError("未配置 C0 DurableExecutionStore，拒绝启动文档处理")
        return self.execution_store.acquire_lease(
            run_id,
            f"document:{document_version_id}",
            owner_token,
            now=now,
        )

    def start(
        self,
        *,
        document_version_id: str,
        source_pdf_path: Path,
        source_sha256: str,
        physical_page_count: int,
    ) -> DocumentAssetManifest:
        """核对不可变版本和源 PDF 后创建或复用 incomplete manifest。"""
        self._validate_document_version(
            document_version_id,
            source_sha256,
            physical_page_count,
        )
        self._validate_source_pdf(
            source_pdf_path,
            source_sha256,
            physical_page_count,
        )
        return self.manifest_repository.create_or_get(
            document_version_id=document_version_id,
            source_sha256=source_sha256,
            physical_page_count=physical_page_count,
            asset_status="incomplete",
        )

    def record_parse_batch(self, **kwargs) -> ParseBatchRecord:
        """记录解析器实际处理的 PDF 物理页段。"""
        return self.parse_batch_repository.record(**kwargs)

    def render_all_page_images(
        self,
        *,
        manifest_id: str,
        document_version_id: str,
        source_pdf_path: Path,
    ) -> tuple[RegisteredPageArtifact, ...]:
        """按 manifest 的物理页范围渲染并登记全部页图。"""
        manifest = self._get_manifest(manifest_id)
        if manifest.document_version_id != document_version_id:
            raise ValueError("document_version_id 与 manifest 不一致")
        self._validate_source_pdf(
            source_pdf_path,
            manifest.source_sha256,
            manifest.physical_page_count,
        )
        registered: list[RegisteredPageArtifact] = []
        for physical_page_number in range(1, manifest.physical_page_count + 1):
            artifact = self.page_image_renderer.render(
                document_version_id,
                source_pdf_path,
                physical_page_number=physical_page_number,
            )
            registered.append(
                self.page_artifact_repository.register_page_image(manifest_id, artifact)
            )
        return tuple(registered)

    def route_document_pages(
        self,
        *,
        manifest_id: str,
        document_version_id: str,
        source_pdf_path: Path,
        vision_dispatcher: Callable[[PageRouteDecision], None] | None = None,
    ) -> PageRoutingSnapshot:
        """用真实 PDF 页信号生成路由快照，只分发明确允许视觉处理的页面。"""
        manifest = self._get_manifest(manifest_id)
        if manifest.document_version_id != document_version_id:
            raise ValueError("document_version_id 与 manifest 不一致")
        self._validate_source_pdf(
            source_pdf_path,
            manifest.source_sha256,
            manifest.physical_page_count,
        )
        decisions: list[PageRouteDecision] = []
        document = fitz.open(source_pdf_path)
        try:
            for page_number in range(1, manifest.physical_page_count + 1):
                page = document.load_page(page_number - 1)
                decision = self.page_router.route(
                    PageSignals(
                        page_number=page_number,
                        text_layer_chars=len(page.get_text("text")),
                        image_count=len(page.get_images(full=True)),
                    )
                )
                decisions.append(decision)
                if decision.use_vision and vision_dispatcher is not None:
                    vision_dispatcher(decision)
        finally:
            document.close()
        return PageRoutingSnapshot(
            manifest_id=manifest_id,
            document_version_id=document_version_id,
            decisions=tuple(decisions),
        )

    def finalize(self, manifest_id: str) -> ManifestPageImageCompleteness:
        """以页图文件和解析批次的双门禁核验最终完整性。"""
        return self.manifest_repository.verify_page_image_completeness(manifest_id)

    def recover_pending_page_file_cleanup(self) -> tuple[Path, ...]:
        """在已配置的页图输出根目录恢复中断删除遗留文件。"""
        return V7DocumentDeletionService.resume_pending_page_file_cleanup(
            self.page_image_renderer.output_root
        )

    def _validate_document_version(
        self,
        document_version_id: str,
        source_sha256: str,
        physical_page_count: int,
    ) -> None:
        """拒绝与已登记 document version 不一致的哈希或物理页数。"""
        self.store.initialize()
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT blob_sha256, physical_page_count
                FROM v7_document_versions
                WHERE document_version_id = ?
                """,
                (document_version_id,),
            ).fetchone()
        if row is None:
            raise ValueError("document_version_id 不存在")
        if row[0] != source_sha256:
            raise ValueError("source_sha256 与 document version 不一致")
        if int(row[1]) != physical_page_count:
            raise ValueError("physical_page_count 与 document version 不一致")

    def _get_manifest(self, manifest_id: str) -> DocumentAssetManifest:
        """读取 manifest，缺失时返回稳定错误。"""
        manifest = self.manifest_repository.get(manifest_id)
        if manifest is None:
            raise ValueError("manifest_id 不存在")
        return manifest

    @staticmethod
    def _validate_source_pdf(
        source_pdf_path: Path,
        expected_sha256: str,
        expected_page_count: int,
    ) -> None:
        """核验实际 PDF 字节哈希和物理页数，不按文件名推断版本。"""
        source_pdf_path = Path(source_pdf_path)
        if not source_pdf_path.is_file():
            raise ValueError("source_pdf_path 不存在")
        digest = hashlib.sha256()
        with source_pdf_path.open("rb") as source_file:
            for block in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != expected_sha256:
            raise ValueError("source_pdf_path 的 SHA-256 与预期不一致")
        try:
            document = fitz.open(source_pdf_path)
        except (fitz.FileDataError, OSError, RuntimeError) as exc:
            raise ValueError("source_pdf_path 无法读取为 PDF") from exc
        try:
            if document.needs_pass or document.page_count != expected_page_count:
                raise ValueError("source_pdf_path 的物理页数与预期不一致")
        finally:
            document.close()
