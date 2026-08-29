# -*- coding: utf-8 -*-
"""B 阶段最小 FinancialFact 领域模型。"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class FinancialFact:
    """保留原始值、归一值及可定位来源的不可变财务事实。"""

    fact_id: str
    metric_key: str
    company_name: str
    raw_value: Decimal
    raw_unit: str
    normalized_value: Decimal
    normalized_unit: str
    currency: str
    period: str
    scope: str
    source_file: str
    physical_pages: tuple[int, ...]
    excerpt: str

    @classmethod
    def create(
        cls,
        *,
        fact_id: str,
        metric_key: str,
        company_name: str,
        raw_value: str | int | float | Decimal,
        raw_unit: str,
        normalized_value: str | int | float | Decimal,
        normalized_unit: str,
        currency: str,
        period: str,
        scope: str,
        source_file: str,
        physical_pages: tuple[int, ...],
        excerpt: str,
    ) -> "FinancialFact":
        """创建经输入边界校验的事实，不从缺失字段推测证据。"""
        for field_name, value in {
            "fact_id": fact_id,
            "metric_key": metric_key,
            "company_name": company_name,
            "raw_unit": raw_unit,
            "normalized_unit": normalized_unit,
            "scope": scope,
            "source_file": source_file,
            "excerpt": excerpt,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} 不能为空")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency 必须是三位大写货币代码")
        if not isinstance(period, str) or not re.fullmatch(r"FY\d{4}", period):
            raise ValueError("period 必须为 FY 加四位年份")
        if (
            not isinstance(physical_pages, tuple)
            or not physical_pages
            or any(type(page) is not int or page <= 0 for page in physical_pages)
            or len(set(physical_pages)) != len(physical_pages)
        ):
            raise ValueError("physical_pages 必须是唯一的正整数元组")
        return cls(
            fact_id=fact_id,
            metric_key=metric_key,
            company_name=company_name,
            raw_value=cls._to_decimal(raw_value, "raw_value"),
            raw_unit=raw_unit,
            normalized_value=cls._to_decimal(normalized_value, "normalized_value"),
            normalized_unit=normalized_unit,
            currency=currency,
            period=period,
            scope=scope,
            source_file=source_file,
            physical_pages=physical_pages,
            excerpt=excerpt,
        )

    @staticmethod
    def _to_decimal(value: str | int | float | Decimal, field_name: str) -> Decimal:
        """将数值转换为有限 Decimal，拒绝 NaN、无穷和无效文本。"""
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{field_name} 必须是有限数值") from exc
        if not result.is_finite():
            raise ValueError(f"{field_name} 必须是有限数值")
        return result
