# -*- coding: utf-8 -*-
"""FinancialFact 的保守数值冲突分类。"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .financial_fact import FinancialFact
from .financial_fact_compatibility import ensure_comparable
from .financial_fact_context import FinancialFactSource


@dataclass(frozen=True)
class FinancialFactConflictDecision:
    """同口径事实的数值一致性或待审核冲突。"""

    status: str
    conflict_type: str | None
    fact_ids: tuple[str, str]
    relative_difference: str
    preferred_fact_id: str | None = None


class FinancialFactConflictService:
    """按明确容差比较同口径事实，不自动裁决超阈值差异。"""

    def __init__(self, relative_tolerance: float | str | Decimal = "0.05") -> None:
        try:
            tolerance = Decimal(str(relative_tolerance))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("relative_tolerance 必须是非负有限数值") from exc
        if not tolerance.is_finite() or tolerance < 0:
            raise ValueError("relative_tolerance 必须是非负有限数值")
        self.relative_tolerance = tolerance

    def compare(
        self,
        reference: FinancialFact,
        candidate: FinancialFact,
        *,
        reference_source: FinancialFactSource | None = None,
        candidate_source: FinancialFactSource | None = None,
    ) -> FinancialFactConflictDecision:
        """比较同口径事实，差异超阈值时交给人工审核。"""
        ensure_comparable(reference, candidate)
        difference = abs(candidate.normalized_value - reference.normalized_value)
        if reference.normalized_value == 0:
            relative_difference = Decimal("0") if difference == 0 else Decimal("Infinity")
        else:
            relative_difference = difference / abs(reference.normalized_value)
        consistent = relative_difference <= self.relative_tolerance
        return FinancialFactConflictDecision(
            status="consistent" if consistent else "pending_review",
            conflict_type=None if consistent else "VALUE_CONFLICT",
            fact_ids=(reference.fact_id, candidate.fact_id),
            relative_difference=_format_decimal(relative_difference),
            preferred_fact_id=self._preferred_fact_id(
                reference, candidate, reference_source, candidate_source
            ),
        )

    @staticmethod
    def _preferred_fact_id(
        reference: FinancialFact,
        candidate: FinancialFact,
        reference_source: FinancialFactSource | None,
        candidate_source: FinancialFactSource | None,
    ) -> str | None:
        """只记录一手来源的复核优先级，不将其作为自动裁决。"""
        if reference_source is None or candidate_source is None:
            return None
        if reference_source.authority_level == candidate_source.authority_level:
            return None
        return reference.fact_id if reference_source.authority_level == "primary" else candidate.fact_id


def _format_decimal(value: Decimal) -> str:
    """保持冲突证据的 Decimal 文本，不隐藏无穷差异。"""
    if not value.is_finite():
        return "Infinity"
    return format(value.normalize(), "f")
