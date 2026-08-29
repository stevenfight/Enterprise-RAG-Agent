# -*- coding: utf-8 -*-
"""基于 FinancialFact 的可追溯计算服务。"""

from dataclasses import dataclass
from typing import Any

from .financial_fact import FinancialFact
from .tools.calculator_tool import CalculatorTool


class FactCalculationError(ValueError):
    """事实输入不适用于指定计算。"""


@dataclass(frozen=True)
class FactCalculationResult:
    """计算结果及公式版本、输入事实证据。"""

    operation: str
    formula_version: str
    input_fact_ids: tuple[str, ...]
    details: dict[str, Any]


class FactCalculationService:
    """复用 CalculatorTool，并为事实输入补充可追溯边界。"""

    YOY_FORMULA_VERSION = "calculator-yoy-v1"
    CAGR_FORMULA_VERSION = "calculator-cagr-v1"

    def __init__(self, calculator: CalculatorTool | None = None) -> None:
        self.calculator = calculator or CalculatorTool()

    def calculate_yoy(
        self,
        *,
        current: FinancialFact,
        previous: FinancialFact,
    ) -> FactCalculationResult:
        """计算相邻财政年度同指标同比，拒绝跨币种或跨口径输入。"""
        self._ensure_yoy_compatible(current, previous)
        tool_result = self.calculator.run(
            operation="yoy_growth",
            current=float(current.normalized_value),
            previous=float(previous.normalized_value),
        )
        if not tool_result.success:
            raise FactCalculationError(tool_result.error)
        return FactCalculationResult(
            operation="yoy_growth",
            formula_version=self.YOY_FORMULA_VERSION,
            input_fact_ids=(current.fact_id, previous.fact_id),
            details=tool_result.data["details"],
        )

    def calculate_yoy_and_save(
        self,
        *,
        calculation_id: str,
        repository,
        current: FinancialFact,
        previous: FinancialFact,
    ) -> FactCalculationResult:
        """复用既有同比计算后持久化其公式与事实证据。"""
        result = self.calculate_yoy(current=current, previous=previous)
        repository.save(calculation_id, result)
        return result

    def calculate_cagr(
        self,
        *,
        start: FinancialFact,
        end: FinancialFact,
    ) -> FactCalculationResult:
        """以事实期间推导 CAGR 年数，拒绝调用方任意指定年数。"""
        self._ensure_cagr_compatible(start, end)
        years = int(end.period.removeprefix("FY")) - int(start.period.removeprefix("FY"))
        tool_result = self.calculator.run(
            operation="cagr",
            start_value=float(start.normalized_value),
            end_value=float(end.normalized_value),
            years=years,
        )
        if not tool_result.success:
            raise FactCalculationError(tool_result.error)
        return FactCalculationResult(
            operation="cagr",
            formula_version=self.CAGR_FORMULA_VERSION,
            input_fact_ids=(start.fact_id, end.fact_id),
            details=tool_result.data["details"],
        )

    @staticmethod
    def _ensure_yoy_compatible(current: FinancialFact, previous: FinancialFact) -> None:
        """同比仅允许同指标、币种、口径的相邻完整财政年度。"""
        checks = (
            ("指标", current.metric_key, previous.metric_key),
            ("币种", current.currency, previous.currency),
            ("口径", current.scope, previous.scope),
            ("归一单位", current.normalized_unit, previous.normalized_unit),
        )
        for label, current_value, previous_value in checks:
            if current_value != previous_value:
                raise FactCalculationError(
                    f"同比输入{label}不兼容: {current_value} != {previous_value}"
                )
        current_year = int(current.period.removeprefix("FY"))
        previous_year = int(previous.period.removeprefix("FY"))
        if current_year != previous_year + 1:
            raise FactCalculationError("同比输入必须是相邻财政年度")

    @staticmethod
    def _ensure_cagr_compatible(start: FinancialFact, end: FinancialFact) -> None:
        """CAGR 仅允许同指标、币种、口径且结束晚于起始的完整财政年度。"""
        checks = (
            ("指标", start.metric_key, end.metric_key),
            ("币种", start.currency, end.currency),
            ("口径", start.scope, end.scope),
            ("归一单位", start.normalized_unit, end.normalized_unit),
        )
        for label, start_value, end_value in checks:
            if start_value != end_value:
                raise FactCalculationError(
                    f"CAGR 输入{label}不兼容: {start_value} != {end_value}"
                )
        if int(end.period.removeprefix("FY")) <= int(start.period.removeprefix("FY")):
            raise FactCalculationError("CAGR 输入必须跨越至少一个财政年度")
