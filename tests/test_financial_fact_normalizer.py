"""统一金额单位时必须保留可审计换算过程。"""

from decimal import Decimal

import pytest


def test_normalizer_converts_revenue_to_yuan_with_explicit_trace():
    from src.financial_fact_normalizer import normalize_amount_to_yuan

    result = normalize_amount_to_yuan("10408", "亿元")

    assert result.normalized_value == Decimal("1040800000000")
    assert result.normalized_unit == "元"
    assert result.conversion_trace == "10408 亿元 × 100000000 = 1040800000000 元"


def test_normalizer_supports_million_yuan_and_does_not_round():
    from src.financial_fact_normalizer import normalize_amount_to_yuan

    result = normalize_amount_to_yuan("1040759.25", "百万元")

    assert result.normalized_value == Decimal("1040759250000")


@pytest.mark.parametrize("unit", ["美元", "元/股", ""])
def test_normalizer_rejects_unknown_or_non_amount_units(unit: str):
    from src.financial_fact_normalizer import normalize_amount_to_yuan

    with pytest.raises(ValueError, match="单位"):
        normalize_amount_to_yuan("1", unit)
