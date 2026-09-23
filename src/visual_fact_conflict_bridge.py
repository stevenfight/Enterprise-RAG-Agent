# -*- coding: utf-8 -*-
"""将已审核视觉事实接入既有 FinancialFact 冲突引擎。"""

from .financial_fact_conflict_repository import FinancialFactConflictRepository
from .financial_fact_conflict_service import FinancialFactConflictDecision, FinancialFactConflictService
from .financial_fact_repository import FinancialFactRepository
from .visual_fact_candidate_repository import VisualFactCandidate


class VisualFactConflictBridge:
    """视觉事实不单独裁决，与正文事实共用同一兼容性和容差规则。"""

    def __init__(
        self,
        financial_fact_repository: FinancialFactRepository,
        conflict_repository: FinancialFactConflictRepository,
        conflict_service: FinancialFactConflictService | None = None,
    ) -> None:
        if financial_fact_repository.store is not conflict_repository.store:
            raise ValueError("视觉冲突桥接的仓储必须使用同一个 metadata store")
        self.financial_fact_repository = financial_fact_repository
        self.conflict_repository = conflict_repository
        self.conflict_service = conflict_service or FinancialFactConflictService()

    def compare_and_save(
        self,
        *,
        conflict_id: str,
        reference_fact_id: str,
        visual_candidate: VisualFactCandidate,
    ) -> FinancialFactConflictDecision:
        """仅已审核且已关联事实的视觉候选可参与同口径冲突判断。"""
        if visual_candidate.review_status != "verified" or not visual_candidate.fact_id:
            raise ValueError("视觉候选尚未审核或未关联事实")
        reference = self.financial_fact_repository.get(reference_fact_id)
        visual_fact = self.financial_fact_repository.get(visual_candidate.fact_id)
        if reference is None or visual_fact is None:
            raise ValueError("冲突比较事实不存在")
        decision = self.conflict_service.compare(reference, visual_fact)
        if decision.status == "pending_review":
            self.conflict_repository.save(conflict_id, decision)
        return decision
