"""B2.5 声明级 EvidenceBundle 测试：关联声明、事实、计算与冲突，并兼容既有证据链响应。"""

import copy
import json

from src.financial_fact import FinancialFact
from src.financial_fact_conflict_repository import FinancialFactConflictRepository
from src.financial_fact_conflict_service import FinancialFactConflictDecision
from src.financial_fact_registry_adapter import FinancialFactRegistryAdapter
from src.financial_fact_repository import FinancialFactRepository
from src.fact_calculation_repository import FactCalculationRepository
from src.fact_calculation_service import FactCalculationResult
from src.v7_metadata_store import V7MetadataStore
from src.verified_financial_facts import VerifiedFinancialFactRegistry


def _make_fact(fact_id: str, company_name: str, value: str) -> FinancialFact:
    """构造一份带完整来源信息的测试事实。"""
    return FinancialFact.create(
        fact_id=fact_id,
        metric_key="operating_revenue",
        company_name=company_name,
        raw_value=value,
        raw_unit="万元",
        normalized_value=value,
        normalized_unit="元",
        currency="CNY",
        period="FY2024",
        scope="consolidated",
        source_file="测试年报.pdf",
        physical_pages=(3,),
        excerpt="营业收入摘录",
    )


def _save_two_facts(store: V7MetadataStore) -> None:
    """先把两条事实写入 V7 存储，供证据包引用。"""
    repository = FinancialFactRepository(store)
    repository.save(_make_fact("revenue-mobile-2024", "中国移动", "1040800000000"))
    repository.save(_make_fact("revenue-telecom-2024", "中国电信", "529500000000"))


def test_evidence_bundle_links_claim_fact_calculation_and_conflict(tmp_path):
    """证据包把声明与事实、计算、冲突关联为可检索的不可变对象。"""
    from src.evidence_bundle import EvidenceBundle, EvidenceBundleRepository

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _save_two_facts(store)
    FactCalculationRepository(store).save(
        "calc-revenue-yoy-2024",
        FactCalculationResult("yoy_growth", "calculator-yoy-v1", ("revenue-mobile-2024", "revenue-mobile-2023"), {"growth_rate": 0.03}),
    )
    FinancialFactConflictRepository(store).save(
        "conflict-revenue-2024",
        FinancialFactConflictDecision("pending_review", "VALUE_CONFLICT", ("revenue-mobile-2024", "revenue-telecom-2024"), "0.9646"),
    )
    bundle = EvidenceBundle.create(
        bundle_id="bundle-claim-001",
        claim_id="claim-2024-mobile-revenue",
        claim_text="中国移动 2024 年营业收入为 10,408 亿元。",
        fact_ids=("revenue-mobile-2024", "revenue-telecom-2024"),
        calculation_ids=("calc-revenue-yoy-2024",),
        conflict_ids=("conflict-revenue-2024",),
    )

    EvidenceBundleRepository(store).save(bundle)

    stored = EvidenceBundleRepository(store).get("bundle-claim-001")
    assert stored == bundle


def test_evidence_bundle_replays_same_evidence_and_rejects_conflict(tmp_path):
    """同一 bundle_id 幂等重放；内容不一致时拒绝静默改写。"""
    from src.evidence_bundle import EvidenceBundle, EvidenceBundleConflictError, EvidenceBundleRepository

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _save_two_facts(store)
    repository = EvidenceBundleRepository(store)
    bundle = EvidenceBundle.create(
        bundle_id="bundle-claim-001",
        claim_id="claim-2024-mobile-revenue",
        claim_text="中国移动 2024 年营业收入为 10,408 亿元。",
        fact_ids=("revenue-mobile-2024",),
        calculation_ids=(),
        conflict_ids=(),
    )
    repository.save(bundle)
    repository.save(bundle)

    conflicting = EvidenceBundle.create(
        bundle_id="bundle-claim-001",
        claim_id="claim-2024-mobile-revenue",
        claim_text="中国移动 2024 年营业收入为 10,408 亿元。",
        fact_ids=("revenue-telecom-2024",),
        calculation_ids=(),
        conflict_ids=(),
    )
    import pytest

    with pytest.raises(EvidenceBundleConflictError):
        repository.save(conflicting)


def test_evidence_bundle_rejects_dangling_references(tmp_path):
    """引用尚未持久化的事实、计算或冲突时拒绝保存，不留悬空引用。"""
    import pytest

    from src.evidence_bundle import EvidenceBundle, EvidenceBundleRepository

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    _save_two_facts(store)
    bundle = EvidenceBundle.create(
        bundle_id="bundle-claim-002",
        claim_id="claim-2024-telecom-revenue",
        claim_text="中国电信 2024 年营业收入同比增长。",
        fact_ids=("revenue-telecom-2024", "fact-missing"),
        calculation_ids=(),
        conflict_ids=(),
    )

    with pytest.raises(ValueError):
        EvidenceBundleRepository(store).save(bundle)
    assert EvidenceBundleRepository(store).get("bundle-claim-002") is None


def test_evidence_bundle_validates_claim_text_and_associations():
    """声明文本不能为空，且证据包必须至少关联一条证据；重复引用被拒绝。"""
    import pytest

    from src.evidence_bundle import EvidenceBundle

    with pytest.raises(ValueError):
        EvidenceBundle.create(
            bundle_id="bundle-claim-003",
            claim_id="claim-empty",
            claim_text="   ",
            fact_ids=("revenue-mobile-2024",),
        )
    with pytest.raises(ValueError):
        EvidenceBundle.create(
            bundle_id="bundle-claim-003",
            claim_id="claim-no-evidence",
            claim_text="没有任何证据支撑的声明。",
            fact_ids=(),
            calculation_ids=(),
            conflict_ids=(),
        )
    with pytest.raises(ValueError):
        EvidenceBundle.create(
            bundle_id="bundle-claim-003",
            claim_id="claim-duplicated",
            claim_text="重复引用同一事实的声明。",
            fact_ids=("revenue-mobile-2024", "revenue-mobile-2024"),
        )


def test_existing_comparison_response_stays_unchanged_when_bundle_created(tmp_path):
    """创建证据包不改变既有比较响应字段，新字段仅以可选载荷提供。"""
    from src.evidence_bundle import EvidenceBundle, EvidenceBundleRepository

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    legacy = VerifiedFinancialFactRegistry()
    adapter = FinancialFactRegistryAdapter(
        legacy_registry=legacy,
        repository=FinancialFactRepository(store),
    )
    adapter.import_registered_revenue_facts()
    comparison = adapter.get_comparison("operating_revenue", 2024, ["中国移动", "中国电信"])
    snapshot = copy.deepcopy(comparison)

    bundle = EvidenceBundle.create(
        bundle_id="bundle-comparison-2024",
        claim_id="claim-comparison-2024",
        claim_text="2024 年中国移动与中国电信的营业收入对比。",
        fact_ids=tuple(comparison["fact_ids"]),
        calculation_ids=(),
        conflict_ids=(),
    )
    EvidenceBundleRepository(store).save(bundle)

    assert adapter.get_comparison("operating_revenue", 2024, ["中国移动", "中国电信"]) == snapshot
    payload = bundle.to_response()
    assert payload["claim_id"] == "claim-comparison-2024"
    assert payload["fact_ids"] == list(comparison["fact_ids"])
    assert payload["calculation_ids"] == []
    assert payload["conflict_ids"] == []
    json.dumps(payload, ensure_ascii=False)
