# -*- coding: utf-8 -*-
"""V7 文档索引完成后的受控版本提升编排。"""

from dataclasses import dataclass
from typing import Callable, Mapping

from .v7_document_repository import V7DocumentRepository


@dataclass(frozen=True)
class DocumentIndexPromotionResult:
    """索引提升结果；未提升时旧 active 版本不受影响。"""

    document_version_id: str
    promoted: bool
    generation_id: str | None = None
    reason: str = ""


class V7DocumentIndexPromotionCoordinator:
    """只在索引回调明确成功且返回 generation 身份后提升文档版本。"""

    def __init__(self, document_repository: V7DocumentRepository) -> None:
        self.document_repository = document_repository

    def complete_index_and_promote(
        self,
        document_version_id: str,
        indexer: Callable[[str], Mapping[str, object]],
    ) -> DocumentIndexPromotionResult:
        """运行受控索引回调，拒绝不完整或缺 generation 的结果。"""
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise ValueError("document_version_id 不能为空")
        result = indexer(document_version_id)
        if not isinstance(result, Mapping):
            raise ValueError("索引回调必须返回对象")
        success = result.get("success")
        generation_id = result.get("generation_id")
        if success is not True or not isinstance(generation_id, str) or not generation_id.strip():
            return DocumentIndexPromotionResult(
                document_version_id=document_version_id,
                promoted=False,
                reason="索引未完成或未生成 generation",
            )
        self.document_repository.promote_document_version_to_active(document_version_id)
        return DocumentIndexPromotionResult(
            document_version_id=document_version_id,
            promoted=True,
            generation_id=generation_id,
        )
