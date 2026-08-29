"""事实驱动计算必须记录输入 ID 与公式版本。"""

import pytest


def _fact(fact_id: str, value: str, period: str, *, currency="CNY"):
    from src.financial_fact import FinancialFact

    return FinancialFact.create(
        fact_id=fact_id,
        metric_key="operating_revenue",
        company_name="中国移动",
        raw_value=value,
        raw_unit="亿元",
        normalized_value=str(int(value) * 100000000),
        normalized_unit="元",
        currency=currency,
        period=period,
        scope="consolidated",
        source_file="移动年报.pdf",
        physical_pages=(3,),
        excerpt="来源",
    )


def test_fact_calculation_uses_calculator_and_records_input_fact_ids():
    from src.fact_calculation_service import FactCalculationService

    result = FactCalculationService().calculate_yoy(
        current=_fact("revenue-2024", "10408", "FY2024"),
        previous=_fact("revenue-2023", "10000", "FY2023"),
    )

    assert result.formula_version == "calculator-yoy-v1"
    assert result.input_fact_ids == ("revenue-2024", "revenue-2023")
    assert result.details["growth_rate_pct"] == 4.08


def test_fact_calculation_rejects_currency_or_non_adjacent_periods():
    from src.fact_calculation_service import FactCalculationError, FactCalculationService

    service = FactCalculationService()
    with pytest.raises(FactCalculationError, match="币种"):
        service.calculate_yoy(
            current=_fact("revenue-2024", "10408", "FY2024"),
            previous=_fact("revenue-2023", "10000", "FY2023", currency="USD"),
        )
    with pytest.raises(FactCalculationError, match="相邻"):
        service.calculate_yoy(
            current=_fact("revenue-2024", "10408", "FY2024"),
            previous=_fact("revenue-2022", "10000", "FY2022"),
        )


def test_fact_calculation_can_persist_the_existing_result_without_changing_calculate_yoy(tmp_path):
    from src.fact_calculation_repository import FactCalculationRepository
    from src.fact_calculation_service import FactCalculationService
    from src.v7_metadata_store import V7MetadataStore

    repository = FactCalculationRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    result = FactCalculationService().calculate_yoy_and_save(
        calculation_id="mobile-revenue-yoy-2024", repository=repository,
        current=_fact("revenue-2024", "10408", "FY2024"),
        previous=_fact("revenue-2023", "10000", "FY2023"),
    )

    assert repository.get("mobile-revenue-yoy-2024") == result


def test_fact_calculation_cagr_derives_years_from_fact_periods():
    from src.fact_calculation_service import FactCalculationService

    result = FactCalculationService().calculate_cagr(
        start=_fact("revenue-2021", "100", "FY2021"),
        end=_fact("revenue-2024", "133", "FY2024"),
    )

    assert result.operation == "cagr"
    assert result.formula_version == "calculator-cagr-v1"
    assert result.input_fact_ids == ("revenue-2021", "revenue-2024")
    assert result.details["years"] == 3
