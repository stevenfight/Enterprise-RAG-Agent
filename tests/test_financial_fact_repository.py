"""FinancialFact 的 V7 SQLite 持久化与幂等边界。"""

import pytest


def _fact(value="10408"):
    from src.financial_fact import FinancialFact
    from src.financial_fact_normalizer import normalize_amount_to_yuan

    normalized = normalize_amount_to_yuan(value, "亿元")
    return FinancialFact.create(
        fact_id="operating-revenue-mobile-2024",
        metric_key="operating_revenue",
        company_name="中国移动",
        raw_value=value,
        raw_unit="亿元",
        normalized_value=normalized.normalized_value,
        normalized_unit=normalized.normalized_unit,
        currency="CNY",
        period="FY2024",
        scope="consolidated",
        source_file="移动2024年度报告.pdf",
        physical_pages=(3,),
        excerpt="2024 年，营业收入达到人民币 10,408 亿元。",
    )


def test_financial_fact_repository_persists_and_reads_immutable_fact(tmp_path):
    from src.financial_fact_repository import FinancialFactRepository
    from src.v7_metadata_store import V7MetadataStore

    repository = FinancialFactRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    fact = _fact()

    first = repository.save(fact)
    second = repository.save(fact)
    loaded = repository.get(fact.fact_id)

    assert first.created is True
    assert second.created is False
    assert loaded == fact


def test_financial_fact_repository_rejects_same_id_with_conflicting_evidence(tmp_path):
    from src.financial_fact_repository import FinancialFactConflictError, FinancialFactRepository
    from src.v7_metadata_store import V7MetadataStore

    repository = FinancialFactRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    repository.save(_fact())

    with pytest.raises(FinancialFactConflictError):
        repository.save(_fact("10409"))
