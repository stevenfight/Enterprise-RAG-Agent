"""财务事实比较前必须满足指标、币种、期间和口径兼容。"""

import pytest


def _fact(*, currency="CNY", period="FY2024", scope="consolidated", metric_key="operating_revenue"):
    from src.financial_fact import FinancialFact

    return FinancialFact.create(
        fact_id=f"fact-{currency}-{period}-{scope}-{metric_key}",
        metric_key=metric_key,
        company_name="示例公司",
        raw_value="1",
        raw_unit="亿元",
        normalized_value="100000000",
        normalized_unit="元",
        currency=currency,
        period=period,
        scope=scope,
        source_file="示例.pdf",
        physical_pages=(1,),
        excerpt="示例来源",
    )


def test_compatibility_accepts_same_metric_currency_period_and_scope():
    from src.financial_fact_compatibility import ensure_comparable

    ensure_comparable(_fact(), _fact())


def test_currency_mismatch_explicitly_refuses_conversion_without_exchange_rate_source():
    from src.financial_fact_compatibility import (
        CurrencyConversionNotAllowedError,
        ensure_comparable,
    )

    with pytest.raises(CurrencyConversionNotAllowedError, match="汇率来源"):
        ensure_comparable(_fact(currency="CNY"), _fact(currency="USD"))


@pytest.mark.parametrize(
    ("left", "right", "reason"),
    [
        (_fact(currency="CNY"), _fact(currency="USD"), "币种"),
        (_fact(period="FY2024"), _fact(period="FY2023"), "期间"),
        (_fact(scope="consolidated"), _fact(scope="parent"), "口径"),
        (_fact(metric_key="operating_revenue"), _fact(metric_key="net_profit"), "指标"),
    ],
)
def test_compatibility_rejects_incompatible_facts(left, right, reason: str):
    from src.financial_fact_compatibility import IncompatibleFinancialFactsError, ensure_comparable

    with pytest.raises(IncompatibleFinancialFactsError, match=reason):
        ensure_comparable(left, right)
