# -*- coding: utf-8 -*-
"""扫描视觉数值候选的持久化审核与事实准入链测试。"""

import hashlib
from pathlib import Path

import fitz

from src.financial_fact import FinancialFact
from src.financial_fact_repository import FinancialFactRepository
from src.scan_page_vision import ScanPageVisionResult
from src.v7_metadata_store import V7MetadataStore
from src.visual_fact_admission import VisualFactAdmissionService


def _visual_context(tmp_path: Path):
    from src.document_asset_manifest_repository import DocumentAssetManifestRepository
    from src.page_artifact_repository import PageArtifactRepository
    from src.page_image_renderer import PageImageRenderer
    from src.v7_document_repository import V7DocumentRepository

    pdf_path = tmp_path / "scan.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf_path)
    document.close()
    content = pdf_path.read_bytes()
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    version = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="scan-report",
        display_name="扫描报告",
        original_filename="scan.pdf",
        file_content=content,
        physical_page_count=1,
    )
    manifest = DocumentAssetManifestRepository(store).create_or_get(
        document_version_id=version.document_version_id,
        source_sha256=hashlib.sha256(content).hexdigest(),
        physical_page_count=1,
        asset_status="incomplete",
    )
    page = PageArtifactRepository(store).register_page_image(
        manifest.manifest_id,
        PageImageRenderer(tmp_path / "rendered").render(
            version.document_version_id, pdf_path, physical_page_number=1
        ),
    )
    return store, manifest, page


def _fact(fact_id: str) -> FinancialFact:
    return FinancialFact.create(
        fact_id=fact_id, metric_key="operating_revenue", company_name="示例公司",
        raw_value="100", raw_unit="亿元", normalized_value="10000000000",
        normalized_unit="元", currency="CNY", period="FY2024", scope="consolidated",
        source_file="scan.pdf", physical_pages=(1,), excerpt="扫描页候选",
    )


def test_low_confidence_scan_candidate_is_persisted_pending_and_cannot_be_admitted(tmp_path: Path):
    from src.visual_fact_candidate_repository import VisualFactCandidateRepository

    store, manifest, page = _visual_context(tmp_path)
    repository = VisualFactCandidateRepository(store)
    candidate = repository.register_scan_candidate(
        candidate_id="scan-low", manifest_id=manifest.manifest_id,
        page_artifact_id=page.page_artifact_id,
        scan_result=ScanPageVisionResult(
            manifest_id=manifest.manifest_id, page_artifact_id=page.page_artifact_id,
            status="candidate", extracted_text="营业收入 100 亿元", confidence=0.42,
        ),
        numeric_payload={"raw_value": "100", "raw_unit": "亿元", "currency": "CNY", "period": "FY2024"},
    )
    facts = FinancialFactRepository(store)
    result = VisualFactAdmissionService(facts).admit_candidate(candidate, _fact("scan-low-fact"))

    assert candidate.review_status == "pending_review"
    assert result.admitted is False
    assert facts.get("scan-low-fact") is None


def test_only_reviewed_candidate_can_be_admitted_and_links_saved_fact(tmp_path: Path):
    from src.visual_fact_candidate_repository import VisualFactCandidateRepository

    store, manifest, page = _visual_context(tmp_path)
    repository = VisualFactCandidateRepository(store)
    candidate = repository.register_scan_candidate(
        candidate_id="scan-high", manifest_id=manifest.manifest_id,
        page_artifact_id=page.page_artifact_id,
        scan_result=ScanPageVisionResult(
            manifest_id=manifest.manifest_id, page_artifact_id=page.page_artifact_id,
            status="candidate", extracted_text="营业收入 100 亿元", confidence=0.95,
        ),
        numeric_payload={"raw_value": "100", "raw_unit": "亿元", "currency": "CNY", "period": "FY2024"},
    )
    verified = repository.review(candidate.candidate_id, "verified")
    facts = FinancialFactRepository(store)
    result = VisualFactAdmissionService(facts).admit_candidate(verified, _fact("scan-high-fact"))
    linked = repository.link_fact(candidate.candidate_id, "scan-high-fact")

    assert result.admitted is True
    assert linked.fact_id == "scan-high-fact"
