# -*- coding: utf-8 -*-
"""金融金额单位的共享精确换算规则。"""

from decimal import Decimal


AMOUNT_UNIT_FACTORS: dict[str, Decimal] = {
    "元": Decimal("1"),
    "千元": Decimal("1000"),
    "万元": Decimal("10000"),
    "百万元": Decimal("1000000"),
    "亿元": Decimal("100000000"),
}

VERIFY_UNIT_MULTIPLIERS: dict[str, float] = {
    "万亿": 1e12,
    "千亿": 1e11,
    "十亿": 1e9,
    "亿": float(AMOUNT_UNIT_FACTORS["亿元"]),
    "百万": float(AMOUNT_UNIT_FACTORS["百万元"]),
    "万": float(AMOUNT_UNIT_FACTORS["万元"]),
    "千": float(AMOUNT_UNIT_FACTORS["千元"]),
}
