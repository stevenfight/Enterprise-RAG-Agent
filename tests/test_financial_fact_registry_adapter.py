"""旧已核验事实注册表到 FinancialFact 的兼容适配。"""


def test_adapter_imports_legacy_revenue_facts_and_preserves_comparison_contract(tmp_path):
    from src.financial_fact_registry_adapter import FinancialFactRegistryAdapter
    from src.financial_fact_repository import FinancialFactRepository
    from src.v7_metadata_store import V7MetadataStore
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    legacy = VerifiedFinancialFactRegistry()
    adapter = FinancialFactRegistryAdapter(
        legacy_registry=legacy,
        repository=FinancialFactRepository(V7MetadataStore(tmp_path / "metadata.sqlite3")),
    )

    imported = adapter.import_registered_revenue_facts()
    comparison = adapter.get_comparison(
        metric_key="operating_revenue",
        fiscal_year=2024,
        companies=["中国移动", "中国联通", "中国电信"],
    )

    assert [item.created for item in imported] == [True, True, True]
    assert comparison == legacy.get_comparison(
        "operating_revenue", 2024, ["中国移动", "中国联通", "中国电信"]
    )


def test_adapter_does_not_claim_unregistered_metric_is_available(tmp_path):
    from src.financial_fact_registry_adapter import FinancialFactRegistryAdapter
    from src.financial_fact_repository import FinancialFactRepository
    from src.v7_metadata_store import V7MetadataStore
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    adapter = FinancialFactRegistryAdapter(
        legacy_registry=VerifiedFinancialFactRegistry(),
        repository=FinancialFactRepository(V7MetadataStore(tmp_path / "metadata.sqlite3")),
    )

    assert adapter.get_comparison("net_profit", 2024, ["中国移动"]) == {
        "available": False,
        "items": [],
    }


def test_adapter_import_does_not_fabricate_document_versions_for_legacy_facts(tmp_path):
    from src.financial_fact_registry_adapter import FinancialFactRegistryAdapter
    from src.financial_fact_repository import FinancialFactRepository
    from src.v7_metadata_store import V7MetadataStore
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    adapter = FinancialFactRegistryAdapter(
        legacy_registry=VerifiedFinancialFactRegistry(),
        repository=FinancialFactRepository(store),
    )

    adapter.import_registered_revenue_facts()

    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM v7_document_versions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM v7_financial_fact_sources").fetchone()[0] == 0
