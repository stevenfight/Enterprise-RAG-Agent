# -*- coding: utf-8 -*-
"""视觉数值复用既有金额、币种和期间归一边界测试。"""

import pytest


def test_visual_numeric_payload_reuses_yuan_normalizer_and_financial_contract():
    from src.visual_fact_normalizer import normalize_visual_numeric_payload

    result = normalize_visual_numeric_payload(
        {"raw_value": "100", "raw_unit": "亿元", "currency": "CNY", "period": "FY2024"}
    )

    assert str(result.normalized_value) == "10000000000"
    assert result.normalized_unit == "元"
    assert result.currency == "CNY"
    assert result.period == "FY2024"
    assert "亿元" in result.conversion_trace


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"raw_value": "100", "raw_unit": "美元", "currency": "USD", "period": "FY2024"}, "金额单位"),
        ({"raw_value": "100", "raw_unit": "亿元", "currency": "CNY", "period": "2024"}, "period"),
        ({"raw_value": "100", "raw_unit": "亿元", "currency": "人民币", "period": "FY2024"}, "currency"),
    ],
)
def test_visual_numeric_payload_rejects_non_financial_contract_values(payload, message):
    from src.visual_fact_normalizer import normalize_visual_numeric_payload

    with pytest.raises(ValueError, match=message):
        normalize_visual_numeric_payload(payload)
