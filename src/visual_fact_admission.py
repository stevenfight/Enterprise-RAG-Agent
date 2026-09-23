# -*- coding: utf-8 -*-
"""视觉候选写入财务事实前的审核与置信度门禁。"""

from dataclasses import dataclass

from .financial_fact import FinancialFact
from .financial_fact_repository import FinancialFactRepository
from .visual_fact_candidate_repository import VisualFactCandidate


@dataclass(frozen=True)
class VisualFactAdmission:
    """待准入的视觉来源事实及其不可省略的审核上下文。"""

    fact: FinancialFact
    confidence: float
    review_status: str
    manifest_id: str
    visual_region_id: str


@dataclass(frozen=True)
class VisualFactAdmissionResult:
    """事实准入结果；拒绝时不会调用事实仓储写入。"""

    fact_id: str
    admitted: bool
    created: bool = False
    reason: str = ""


class VisualFactAdmissionService:
    """视觉数值只有高置信且审核通过时才能写入 FinancialFact 仓储。"""

    def __init__(
        self,
        financial_fact_repository: FinancialFactRepository,
        confidence_threshold: float = 0.85,
    ) -> None:
        if (
            not isinstance(confidence_threshold, (int, float))
            or isinstance(confidence_threshold, bool)
            or not 0 <= confidence_threshold <= 1
        ):
            raise ValueError("视觉事实置信度阈值必须在 0 到 1 之间")
        self.financial_fact_repository = financial_fact_repository
        self.confidence_threshold = float(confidence_threshold)

    def admit(self, admission: VisualFactAdmission) -> VisualFactAdmissionResult:
        """拒绝低置信或未审核候选；准入后才调用既有事实不可变写入。"""
        self._validate_admission(admission)
        if admission.confidence < self.confidence_threshold:
            return VisualFactAdmissionResult(
                fact_id=admission.fact.fact_id,
                admitted=False,
                reason="视觉事实置信度不足，禁止写入 verified 事实",
            )
        if admission.review_status != "verified":
            return VisualFactAdmissionResult(
                fact_id=admission.fact.fact_id,
                admitted=False,
                reason="视觉事实未经审核通过，禁止写入 verified 事实",
            )
        saved = self.financial_fact_repository.save(admission.fact)
        return VisualFactAdmissionResult(
            fact_id=saved.fact_id,
            admitted=True,
            created=saved.created,
        )

    def admit_candidate(self, candidate: VisualFactCandidate, fact: FinancialFact) -> VisualFactAdmissionResult:
        """将已持久化候选转换为准入请求，审核状态由候选仓储提供。"""
        return self.admit(VisualFactAdmission(fact, candidate.confidence, candidate.review_status, candidate.manifest_id, candidate.page_artifact_id))

    @staticmethod
    def _validate_admission(admission: VisualFactAdmission) -> None:
        """拒绝不完整视觉身份、非法状态与非法置信度。"""
        if not isinstance(admission, VisualFactAdmission):
            raise ValueError("admission 必须是 VisualFactAdmission")
        if not isinstance(admission.fact, FinancialFact):
            raise ValueError("视觉事实必须是 FinancialFact")
        if (
            not isinstance(admission.confidence, (int, float))
            or isinstance(admission.confidence, bool)
            or not 0 <= admission.confidence <= 1
        ):
            raise ValueError("视觉事实置信度无效")
        if admission.review_status not in {"candidate", "pending_review", "verified"}:
            raise ValueError("视觉事实审核状态无效")
        if not isinstance(admission.manifest_id, str) or not admission.manifest_id.strip():
            raise ValueError("manifest_id 不能为空")
        if not isinstance(admission.visual_region_id, str) or not admission.visual_region_id.strip():
            raise ValueError("visual_region_id 不能为空")
