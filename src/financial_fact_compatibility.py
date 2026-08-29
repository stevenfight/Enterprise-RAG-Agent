# -*- coding: utf-8 -*-
"""FinancialFact 的比较前置兼容性门禁。"""

from .financial_fact import FinancialFact


class IncompatibleFinancialFactsError(ValueError):
    """两个事实缺少可比性所需的共同口径。"""


class CurrencyConversionNotAllowedError(IncompatibleFinancialFactsError):
    """没有可审计汇率来源时禁止跨币种换算。"""


def ensure_same_currency(left: FinancialFact, right: FinancialFact) -> None:
    """只允许同币种事实比较；汇率换算必须由后续受证据约束的流程处理。"""
    if left.currency != right.currency:
        raise CurrencyConversionNotAllowedError(
            "事实币种不兼容，缺少可审计汇率来源，禁止换算: "
            f"{left.currency} != {right.currency}"
        )


def ensure_comparable(left: FinancialFact, right: FinancialFact) -> None:
    """仅允许同指标、币种、期间和口径的事实进入数值比较或计算。"""
    checks = (
        ("指标", left.metric_key, right.metric_key),
        ("期间", left.period, right.period),
        ("口径", left.scope, right.scope),
    )
    for label, left_value, right_value in checks:
        if left_value != right_value:
            raise IncompatibleFinancialFactsError(
                f"事实{label}不兼容: {left_value} != {right_value}"
            )
    ensure_same_currency(left, right)
