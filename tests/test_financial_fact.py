"""B 阶段 FinancialFact 的不可变证据与输入边界。"""

from decimal import Decimal

import pytest


def test_financial_fact_keeps_raw_and_normalized_values_with_source_pages():
    from src.financial_fact import FinancialFact

    fact = FinancialFact.create(
        fact_id="revenue-mobile-2024",
        metric_key="operating_revenue",
        company_name="中国移动",
        raw_value="10408",
        raw_unit="亿元",
        normalized_value="1040800000000",
        normalized_unit="元",
        currency="CNY",
        period="FY2024",
        scope="consolidated",
        source_file="移动2024年度报告.pdf",
        physical_pages=(3,),
        excerpt="2024 年，营业收入达到人民币 10,408 亿元。",
    )

    assert fact.raw_value == Decimal("10408")
    assert fact.normalized_value == Decimal("1040800000000")
    assert fact.physical_pages == (3,)
    assert fact.normalized_unit == "元"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("raw_value", "not-a-number"),
        ("physical_pages", (0,)),
        ("currency", ""),
        ("period", "2024"),
        ("scope", ""),
    ],
)
def test_financial_fact_rejects_invalid_evidence_boundaries(field: str, value):
    from src.financial_fact import FinancialFact

    values = {
        "fact_id": "revenue-mobile-2024",
        "metric_key": "operating_revenue",
        "company_name": "中国移动",
        "raw_value": "10408",
        "raw_unit": "亿元",
        "normalized_value": "1040800000000",
        "normalized_unit": "元",
        "currency": "CNY",
        "period": "FY2024",
        "scope": "consolidated",
        "source_file": "移动2024年度报告.pdf",
        "physical_pages": (3,),
        "excerpt": "来源摘录",
    }
    values[field] = value

    with pytest.raises(ValueError):
        FinancialFact.create(**values)
