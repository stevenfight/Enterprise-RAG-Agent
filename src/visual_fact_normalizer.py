# -*- coding: utf-8 -*-
"""视觉数值候选复用既有金融事实归一与契约校验。"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from .financial_fact import FinancialFact
from .financial_fact_normalizer import normalize_amount_to_yuan


@dataclass(frozen=True)
class NormalizedVisualNumeric:
    """视觉候选的金额、币种与期间归一结果。"""

    raw_value: Decimal
    raw_unit: str
    normalized_value: Decimal
    normalized_unit: str
    currency: str
    period: str
    conversion_trace: str


def normalize_visual_numeric_payload(payload: Mapping[str, object]) -> NormalizedVisualNumeric:
    """只接受既有 FinancialFact 金额、币种和期间契约，不从候选文本推断字段。"""
    if not isinstance(payload, Mapping):
        raise ValueError("视觉数值载荷必须是对象")
    raw_value = payload.get("raw_value")
    raw_unit = payload.get("raw_unit")
    currency = payload.get("currency")
    period = payload.get("period")
    normalized = normalize_amount_to_yuan(raw_value, raw_unit)
    validated = FinancialFact.create(
        fact_id="visual-normalization-validation",
        metric_key="visual_candidate",
        company_name="visual_candidate",
        raw_value=raw_value,
        raw_unit=raw_unit,
        normalized_value=normalized.normalized_value,
        normalized_unit=normalized.normalized_unit,
        currency=currency,
        period=period,
        scope="visual_candidate",
        source_file="visual_candidate",
        physical_pages=(1,),
        excerpt="visual_candidate",
    )
    return NormalizedVisualNumeric(
        raw_value=validated.raw_value,
        raw_unit=validated.raw_unit,
        normalized_value=validated.normalized_value,
        normalized_unit=validated.normalized_unit,
        currency=validated.currency,
        period=validated.period,
        conversion_trace=normalized.conversion_trace,
    )
