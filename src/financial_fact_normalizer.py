# -*- coding: utf-8 -*-
"""财务事实金额归一器，复用 VerifyTool 的量级定义。"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .financial_unit_rules import AMOUNT_UNIT_FACTORS


@dataclass(frozen=True)
class NormalizedAmount:
    """金额归一结果及完整换算轨迹。"""

    normalized_value: Decimal
    normalized_unit: str
    conversion_trace: str


def normalize_amount_to_yuan(raw_value: str | int | float | Decimal, raw_unit: str) -> NormalizedAmount:
    """把人民币金额单位统一到元，不处理汇率或每股等不同量纲。"""
    if not isinstance(raw_unit, str):
        raise ValueError("单位必须是字符串")
    unit = raw_unit.strip()
    factors = {
        "元": AMOUNT_UNIT_FACTORS["元"],
        "千元": AMOUNT_UNIT_FACTORS["千元"],
        "万元": AMOUNT_UNIT_FACTORS["万元"],
        "百万元": AMOUNT_UNIT_FACTORS["百万元"],
        "亿元": AMOUNT_UNIT_FACTORS["亿元"],
    }
    if unit not in factors:
        raise ValueError("单位不属于可归一的人民币金额单位")
    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("raw_value 必须是有限数值") from exc
    if not value.is_finite():
        raise ValueError("raw_value 必须是有限数值")
    factor = factors[unit]
    normalized_value = value * factor
    return NormalizedAmount(
        normalized_value=normalized_value,
        normalized_unit="元",
        conversion_trace=(
            f"{_format_decimal(value)} {unit} × {_format_decimal(factor)} = "
            f"{_format_decimal(normalized_value)} 元"
        ),
    )


def _format_decimal(value: Decimal) -> str:
    """以不引入科学计数法或无意义尾随零的形式记录审计轨迹。"""
    return format(value.normalize(), "f")
