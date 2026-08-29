"""B2.6 已核验比较响应的声明级证据载荷测试。"""

LEGACY_COMPANIES = ["中国移动", "中国联通", "中国电信"]


def _build_adapter(tmp_path, *, with_repositories):
    """构造共享同一 V7 store 的比较适配器，with_repositories 控制是否注入公式与冲突仓储。"""
    from src.fact_calculation_repository import FactCalculationRepository
    from src.financial_fact_conflict_repository import FinancialFactConflictRepository
    from src.financial_fact_registry_adapter import FinancialFactRegistryAdapter
    from src.financial_fact_repository import FinancialFactRepository
    from src.v7_metadata_store import V7MetadataStore
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    calculation_repository = FactCalculationRepository(store) if with_repositories else None
    conflict_repository = FinancialFactConflictRepository(store) if with_repositories else None
    return FinancialFactRegistryAdapter(
        legacy_registry=VerifiedFinancialFactRegistry(),
        repository=FinancialFactRepository(store),
        calculation_repository=calculation_repository,
        conflict_repository=conflict_repository,
    )


def test_comparison_items_carry_raw_and_normalized_fact_details(tmp_path):
    from src.financial_fact_registry_adapter import FinancialFactRegistryAdapter

    adapter = _build_adapter(tmp_path, with_repositories=True)
    adapter.import_registered_revenue_facts()

    comparison = adapter.get_comparison("operating_revenue", 2024, LEGACY_COMPANIES)

    assert comparison["available"] is True
    for item in comparison["items"]:
        assert isinstance(item["raw_value"], str)
        assert isinstance(item["normalized_value"], str)
        assert item["raw_value"] and item["raw_unit"]
        assert item["normalized_value"] and item["normalized_unit"]
    mobile = next(item for item in comparison["items"] if item["company_name"] == "中国移动")
    assert mobile["raw_value"] == "10408"
    assert mobile["raw_unit"] == "亿元"


def test_comparison_payload_includes_linked_calculations_and_conflicts(tmp_path):
    from src.fact_calculation_service import FactCalculationResult
    from src.financial_fact_conflict_service import FinancialFactConflictDecision

    adapter = _build_adapter(tmp_path, with_repositories=True)
    adapter.import_registered_revenue_facts()
    comparison = adapter.get_comparison("operating_revenue", 2024, LEGACY_COMPANIES)
    first_fact_id = comparison["items"][0]["fact_id"]
    second_fact_id = comparison["items"][1]["fact_id"]

    adapter.calculation_repository.save(
        "calc-revenue-yoy-2024",
        FactCalculationResult(
            operation="yoy_growth",
            formula_version="calculator-yoy-v1",
            input_fact_ids=(first_fact_id, second_fact_id),
            details={"growth_rate": 0.1},
        ),
    )
    adapter.conflict_repository.save(
        "conflict-revenue-2024",
        FinancialFactConflictDecision(
            status="pending_review",
            conflict_type="VALUE_CONFLICT",
            fact_ids=(first_fact_id, second_fact_id),
            relative_difference="0.06",
            preferred_fact_id=first_fact_id,
        ),
    )

    comparison = adapter.get_comparison("operating_revenue", 2024, LEGACY_COMPANIES)

    calculations = comparison["calculations"]
    assert [entry["calculation_id"] for entry in calculations] == ["calc-revenue-yoy-2024"]
    assert calculations[0]["operation"] == "yoy_growth"
    assert calculations[0]["formula_version"] == "calculator-yoy-v1"
    assert calculations[0]["input_fact_ids"] == [first_fact_id, second_fact_id]
    assert calculations[0]["details"] == {"growth_rate": 0.1}

    conflicts = comparison["conflicts"]
    assert [entry["conflict_id"] for entry in conflicts] == ["conflict-revenue-2024"]
    assert conflicts[0]["status"] == "pending_review"
    assert conflicts[0]["conflict_type"] == "VALUE_CONFLICT"
    assert conflicts[0]["fact_ids"] == [first_fact_id, second_fact_id]
    assert conflicts[0]["relative_difference"] == "0.06"
    assert conflicts[0]["preferred_fact_id"] == first_fact_id


def test_comparison_without_repositories_keeps_legacy_response_exactly(tmp_path):
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    adapter = _build_adapter(tmp_path, with_repositories=False)
    adapter.import_registered_revenue_facts()

    comparison = adapter.get_comparison("operating_revenue", 2024, LEGACY_COMPANIES)

    legacy = VerifiedFinancialFactRegistry().get_comparison(
        "operating_revenue", 2024, LEGACY_COMPANIES
    )
    assert comparison == legacy


def test_comparison_with_repositories_keeps_legacy_fields_unchanged(tmp_path):
    from src.verified_financial_facts import VerifiedFinancialFactRegistry

    adapter = _build_adapter(tmp_path, with_repositories=True)
    adapter.import_registered_revenue_facts()

    comparison = adapter.get_comparison("operating_revenue", 2024, LEGACY_COMPANIES)
    legacy = VerifiedFinancialFactRegistry().get_comparison(
        "operating_revenue", 2024, LEGACY_COMPANIES
    )

    assert comparison["available"] == legacy["available"]
    assert comparison["metric_key"] == legacy["metric_key"]
    assert comparison["fiscal_year"] == legacy["fiscal_year"]
    assert comparison["unit"] == legacy["unit"]
    assert comparison["fact_ids"] == legacy["fact_ids"]
    for enriched, original in zip(comparison["items"], legacy["items"]):
        for key, value in original.items():
            assert enriched[key] == value
