"""B1.3 共享单位规则与旧 VerifyTool 兼容测试。"""

from decimal import Decimal

import pytest


def test_shared_decimal_unit_rules_match_verify_tool_public_multipliers():
    from src.financial_unit_rules import AMOUNT_UNIT_FACTORS
    from src.tools.verify_tool import UNIT_MULTIPLIERS

    assert AMOUNT_UNIT_FACTORS["亿元"] == Decimal("100000000")
    assert AMOUNT_UNIT_FACTORS["百万元"] == Decimal("1000000")
    assert UNIT_MULTIPLIERS == {
        "万亿": 1e12, "千亿": 1e11, "十亿": 1e9, "亿": 1e8,
        "百万": 1e6, "万": 1e4, "千": 1e3,
    }


def test_verify_tool_keeps_percentage_and_per_share_units_distinct():
    from src.tools.verify_tool import VerifyTool

    tool = VerifyTool()
    extracted = tool._extract_numbers("毛利率为-3.2%，基本每股收益为1.50元/股")

    assert [(item["value"], item["unit"]) for item in extracted] == [
        (-3.2, "%"),
        (1.5, "元/股"),
    ]
    result = tool.run(
        claim="毛利率为3.2%",
        source_text="经审计确认，基本每股收益为3.2元/股，数据完整。",
    )
    assert result.data["valid"] is False


@pytest.mark.parametrize("unit", ["%", "元/股"])
def test_amount_normalizer_rejects_percentage_and_per_share_units(unit):
    from src.financial_fact_normalizer import normalize_amount_to_yuan

    with pytest.raises(ValueError, match="金额单位"):
        normalize_amount_to_yuan("1", unit)
