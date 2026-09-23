# -*- coding: utf-8 -*-
"""视觉候选进入 FinancialFact 前的置信度与审核门禁测试。"""

from src.financial_fact import FinancialFact
from src.financial_fact_repository import FinancialFactRepository
from src.visual_fact_admission import VisualFactAdmission, VisualFactAdmissionService
from src.v7_metadata_store import V7MetadataStore


def _fact(fact_id: str) -> FinancialFact:
    return FinancialFact.create(
        fact_id=fact_id,
        metric_key="operating_revenue",
        company_name="示例公司",
        raw_value="100",
        raw_unit="亿元",
        normalized_value="10000000000",
        normalized_unit="元",
        currency="CNY",
        period="FY2024",
        scope="consolidated",
        source_file="示例报告.pdf",
        physical_pages=(1,),
        excerpt="扫描页候选数值",
    )


def test_low_confidence_visual_number_cannot_be_saved_even_when_marked_verified(tmp_path):
    repository = FinancialFactRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    service = VisualFactAdmissionService(repository)
    fact = _fact("visual-low")

    result = service.admit(
        VisualFactAdmission(
            fact=fact,
            confidence=0.42,
            review_status="verified",
            manifest_id="manifest-1",
            visual_region_id="region-1",
        )
    )

    assert result.admitted is False
    assert "置信度" in result.reason
    assert repository.get(fact.fact_id) is None


def test_unreviewed_visual_candidate_cannot_be_saved_but_high_confidence_reviewed_one_can(tmp_path):
    repository = FinancialFactRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    service = VisualFactAdmissionService(repository)
    pending_fact = _fact("visual-pending")
    verified_fact = _fact("visual-verified")

    pending = service.admit(
        VisualFactAdmission(
            fact=pending_fact,
            confidence=0.95,
            review_status="candidate",
            manifest_id="manifest-1",
            visual_region_id="region-1",
        )
    )
    verified = service.admit(
        VisualFactAdmission(
            fact=verified_fact,
            confidence=0.95,
            review_status="verified",
            manifest_id="manifest-1",
            visual_region_id="region-1",
        )
    )

    assert pending.admitted is False
    assert "审核" in pending.reason
    assert repository.get(pending_fact.fact_id) is None
    assert verified.admitted is True
    assert repository.get(verified_fact.fact_id) == verified_fact
