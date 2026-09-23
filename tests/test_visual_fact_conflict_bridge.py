# -*- coding: utf-8 -*-
"""已审核视觉事实与正文事实进入统一冲突引擎的测试。"""

from src.financial_fact import FinancialFact
from src.financial_fact_repository import FinancialFactRepository
from src.v7_metadata_store import V7MetadataStore
from src.visual_fact_candidate_repository import VisualFactCandidate


def _fact(fact_id: str, value: str) -> FinancialFact:
    return FinancialFact.create(
        fact_id=fact_id, metric_key="operating_revenue", company_name="示例公司",
        raw_value=value, raw_unit="亿元", normalized_value=str(int(value) * 100000000),
        normalized_unit="元", currency="CNY", period="FY2024", scope="consolidated",
        source_file=f"{fact_id}.pdf", physical_pages=(1,), excerpt="来源",
    )


def test_verified_visual_fact_conflict_uses_existing_engine_and_persists_review(tmp_path):
    from src.financial_fact_conflict_repository import FinancialFactConflictRepository
    from src.visual_fact_conflict_bridge import VisualFactConflictBridge

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    facts = FinancialFactRepository(store)
    text_fact = _fact("text-fact", "100")
    visual_fact = _fact("visual-fact", "110")
    facts.save(text_fact)
    facts.save(visual_fact)
    visual_candidate = VisualFactCandidate(
        candidate_id="visual-candidate", manifest_id="manifest-1", page_artifact_id="page-1",
        extracted_text="营业收入 110 亿元", numeric_payload={}, confidence=0.95,
        review_status="verified", fact_id=visual_fact.fact_id,
    )
    conflicts = FinancialFactConflictRepository(store)

    decision = VisualFactConflictBridge(facts, conflicts).compare_and_save(
        conflict_id="visual-vs-text", reference_fact_id=text_fact.fact_id,
        visual_candidate=visual_candidate,
    )

    assert decision.status == "pending_review"
    assert decision.fact_ids == ("text-fact", "visual-fact")
    assert conflicts.get("visual-vs-text") == decision
