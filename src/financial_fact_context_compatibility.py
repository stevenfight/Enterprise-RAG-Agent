# -*- coding: utf-8 -*-
"""FinancialFact 上下文实体的显式可比性门禁。"""

from .financial_fact_context import FinancialPeriod, FinancialScope


class IncompatibleFactContextError(ValueError):
    """两个事实的期间或口径上下文不可比较。"""


def ensure_context_comparable(
    left_period: FinancialPeriod,
    right_period: FinancialPeriod,
    left_scope: FinancialScope,
    right_scope: FinancialScope,
) -> None:
    """拒绝不同时间边界和会计口径，禁止以标签相同替代事实可比性。"""
    period_fields = (
        ("期间类型", left_period.period_type, right_period.period_type),
        ("期间起始", left_period.period_start, right_period.period_start),
        ("期间结束", left_period.period_end, right_period.period_end),
        ("财年", left_period.fiscal_year, right_period.fiscal_year),
    )
    for label, left_value, right_value in period_fields:
        if left_value != right_value:
            raise IncompatibleFactContextError(
                f"事实期间不兼容（{label}）: {left_value} != {right_value}"
            )
    scope_fields = (
        ("合并范围", left_scope.consolidation, right_scope.consolidation),
        ("会计准则", left_scope.accounting_standard, right_scope.accounting_standard),
        ("审计状态", left_scope.audited, right_scope.audited),
    )
    for label, left_value, right_value in scope_fields:
        if left_value != right_value:
            raise IncompatibleFactContextError(
                f"事实口径不兼容（{label}）: {left_value} != {right_value}"
            )
