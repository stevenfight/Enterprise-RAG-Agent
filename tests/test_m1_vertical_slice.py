# -*- coding: utf-8 -*-
"""M1.7 单文档多模态清单、事实、来源和定位的纵向试点。"""

import hashlib
from pathlib import Path

import fitz

from src.api_service import _build_agent_answer_sources
from src.complex_table_vision import (
    ComplexTableVisionRequest,
    ComplexTableVisionService,
)
from src.financial_fact import FinancialFact
from src.financial_fact_repository import FinancialFactRepository
from src.table_structure import parse_html_table
from src.v7_feature_flags import V7FeatureFlags
from src.vision_provider import (
    BaseVisionProvider,
    VisionProviderConfig,
    VisionResponse,
)
from src.visual_fact_admission import VisualFactAdmission, VisualFactAdmissionService
from src.visual_artifact_repository import VisualArtifactRepository
from src.visual_region_repository import VisualRegionRepository


class _StaticComplexTableProvider(BaseVisionProvider):
    """只返回固定结构的视觉替身，不调用外部模型。"""

    def __init__(self) -> None:
        super().__init__(
            VisionProviderConfig(
                enabled=True,
                api_key="test-key",
                model="test-table-model",
                capabilities=frozenset({"table_structure"}),
            )
        )

    def _analyze(self, request):
        return VisionResponse(
            success=True,
            status="complete",
            payload={
                "structured_table": {
                    "headers": ["项目", "2024 年"],
                    "rows": [["营业收入", "123"]],
                },
                "confidence": 0.94,
            },
            model=self.config.model,
        )


def _registered_manifest(tmp_path: Path):
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer
    from src.parse_batch_repository import ParseBatchRepository
    from src.v7_document_processing_coordinator import V7DocumentProcessingCoordinator
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    pdf_path = tmp_path / "vertical-slice.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "普通表格来源页")
    document.save(pdf_path)
    document.close()
    pdf_bytes = pdf_path.read_bytes()

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    registration = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="vertical-slice-report",
        display_name="纵向试点报告",
        original_filename="纵向试点报告.pdf",
        file_content=pdf_bytes,
        physical_page_count=1,
    )
    coordinator = V7DocumentProcessingCoordinator(
        manifest_repository=DocumentAssetManifestRepository(store),
        parse_batch_repository=ParseBatchRepository(store),
        page_image_renderer=PageImageRenderer(tmp_path / "rendered"),
        page_artifact_repository=PageArtifactRepository(store),
    )
    manifest = coordinator.start(
        document_version_id=registration.document_version_id,
        source_pdf_path=registration.blob_path,
        source_sha256=registration.blob_sha256,
        physical_page_count=1,
    )
    coordinator.record_parse_batch(
        manifest_id=manifest.manifest_id,
        batch_id="vertical-slice-pages-1",
        physical_page_start=1,
        physical_page_end=1,
        parser_name="mineru",
        parser_version="v4",
        batch_status="complete",
    )
    registered_page_artifact = coordinator.render_all_page_images(
        manifest_id=manifest.manifest_id,
        document_version_id=registration.document_version_id,
        source_pdf_path=registration.blob_path,
    )[0]
    assert coordinator.finalize(manifest.manifest_id).complete is True
    rendered_page_artifact = coordinator.page_image_renderer.render(
        registration.document_version_id,
        registration.blob_path,
        physical_page_number=1,
    )
    return store, registration, manifest, registered_page_artifact, rendered_page_artifact


def test_single_pdf_multimodal_vertical_slice_reaches_source_locator_and_shared_fact_store(
    tmp_path: Path,
):
    """单文档试点串联普通表格、复杂区域、统一事实和来源定位。"""
    store, registration, manifest, page_artifact, rendered_page_artifact = _registered_manifest(tmp_path)

    ordinary_table = parse_html_table(
        """
        <table><caption>营业收入表</caption>
          <tr><th>项目</th><th>2024 年</th></tr>
          <tr><td>营业收入</td><td>123</td></tr>
        </table>
        """
    )
    assert ordinary_table.caption == "营业收入表"
    assert ordinary_table.grid() == [["项目", "2024 年"], ["营业收入", "123"]]

    region = VisualRegionRepository(store).register(
        page_artifact_id=page_artifact.page_artifact_id,
        x0=0.1,
        y0=0.2,
        x1=0.8,
        y1=0.9,
        region_status="complete",
    )
    table_artifact = VisualArtifactRepository(store).register_table(
        manifest_id=manifest.manifest_id,
        visual_region_id=region.visual_region_id,
        source_format="mineru-html-and-vision",
        artifact_status="complete",
    )
    evidence = VisualArtifactRepository(store).register_evidence(
        manifest_id=manifest.manifest_id,
        page_artifact_id=page_artifact.page_artifact_id,
        visual_region_id=region.visual_region_id,
        table_artifact_id=table_artifact.artifact_id,
        chart_artifact_id=None,
        evidence_status="complete",
    )

    vision_result = ComplexTableVisionService(_StaticComplexTableProvider()).analyze(
        ComplexTableVisionRequest(
            manifest_id=manifest.manifest_id,
            visual_region_id=region.visual_region_id,
            image_bytes=rendered_page_artifact.image_path.read_bytes(),
            mime_type="image/png",
            prompt="提取复杂财务表格结构",
        )
    )
    assert vision_result.status == "candidate"
    assert vision_result.structured_table["rows"] == [["营业收入", "123"]]
    assert vision_result.visual_region_id == region.visual_region_id

    from src.visual_fact_normalizer import normalize_visual_numeric_payload

    normalized = normalize_visual_numeric_payload(
        {
            "raw_value": "123",
            "raw_unit": "亿元",
            "currency": "CNY",
            "period": "FY2024",
        }
    )
    fact = FinancialFact.create(
        fact_id="vertical-slice-revenue",
        metric_key="operating_revenue",
        company_name="纵向试点公司",
        raw_value=normalized.raw_value,
        raw_unit=normalized.raw_unit,
        normalized_value=normalized.normalized_value,
        normalized_unit=normalized.normalized_unit,
        currency=normalized.currency,
        period=normalized.period,
        scope="consolidated",
        source_file="纵向试点报告.pdf",
        physical_pages=(1,),
        excerpt="营业收入 123 亿元",
    )
    fact_repository = FinancialFactRepository(store)
    admission = VisualFactAdmissionService(fact_repository).admit(
        VisualFactAdmission(
            fact=fact,
            confidence=vision_result.confidence,
            review_status="verified",
            manifest_id=manifest.manifest_id,
            visual_region_id=region.visual_region_id,
        )
    )
    assert admission.admitted is True
    assert fact_repository.get(fact.fact_id) == fact

    sources = _build_agent_answer_sources(
        [
            {
                "source_file": "纵向试点报告.pdf",
                "pages": [1],
                "company_name": "纵向试点公司",
                "content": "营业收入 123 亿元",
                "visual_locator": {
                    "manifest_id": manifest.manifest_id,
                    "page_artifact_id": page_artifact.page_artifact_id,
                    "visual_region_id": region.visual_region_id,
                    "normalized_bbox": [0.1, 0.2, 0.8, 0.9],
                    "artifact_status": "complete",
                },
            }
        ]
    )
    assert sources[0]["visual_locator"]["page_artifact_id"] == page_artifact.page_artifact_id
    assert sources[0]["visual_locator"]["visual_region_id"] == region.visual_region_id
    assert evidence.page_artifact_id == page_artifact.page_artifact_id
    assert evidence.table_artifact_id == table_artifact.artifact_id


def test_multimodal_default_off_keeps_legacy_upload_contract(tmp_path: Path, monkeypatch):
    """默认关闭时上传不进入 V7 路径，也不增加旧响应字段。"""
    import src.knowledge_service as knowledge_service

    monkeypatch.setattr(knowledge_service, "_PDF_DIR", tmp_path / "legacy")
    monkeypatch.setattr(knowledge_service, "_MANIFEST_PATH", tmp_path / "manifest.json")
    flags = V7FeatureFlags()

    result = knowledge_service.upload_pdf(
        b"%PDF-1.7\\nlegacy",
        "legacy.pdf",
        v7_flags=flags,
    )

    assert flags.multimodal_enabled is False
    assert set(result) == {"filename", "size", "size_mb", "sha256", "index_status", "idempotent"}
    assert "document_version_id" not in result
    assert hashlib.sha256(b"%PDF-1.7\\nlegacy").hexdigest() == result["sha256"]
