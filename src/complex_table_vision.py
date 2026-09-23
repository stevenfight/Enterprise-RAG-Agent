# -*- coding: utf-8 -*-
"""复杂表格视觉分析：输出可审计候选，不直接写入已核验事实。"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from .vision_cache import VisionCallCache
from .vision_provider import BaseVisionProvider, VisionRequest, VisionUsage


@dataclass(frozen=True)
class ComplexTableVisionRequest:
    """复杂表格视觉请求与受控 manifest/区域身份。"""

    manifest_id: str
    visual_region_id: str
    image_bytes: bytes
    mime_type: str
    prompt: str
    model: str | None = None
    timeout: int = 60
    artifact_version: str = "v1"


@dataclass(frozen=True)
class ComplexTableVisionResult:
    """复杂表格视觉候选结果，任何成功结果仍须后续审核。"""

    manifest_id: str
    visual_region_id: str
    status: str
    structured_table: Mapping[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    model: str = ""
    usage: VisionUsage = field(default_factory=VisionUsage)
    error: str = ""
    review_required: bool = True


class ComplexTableVisionService:
    """调用已配置视觉 Provider，并把结果限制为候选或 incomplete。"""

    def __init__(self, vision_provider: BaseVisionProvider, vision_cache: VisionCallCache | None = None) -> None:
        self.vision_provider = vision_provider
        self.vision_cache = vision_cache

    def analyze(self, request: ComplexTableVisionRequest) -> ComplexTableVisionResult:
        """获取结构化表格、置信度、模型、用量和区域，不产生 verified 事实。"""
        vision_request = VisionRequest(
            image_bytes=request.image_bytes,
            mime_type=request.mime_type,
            prompt=request.prompt,
            capability="table_structure",
            model=request.model,
            timeout=request.timeout,
            cache_context={
                "manifest_id": request.manifest_id,
                "artifact_id": request.visual_region_id,
                "artifact_version": request.artifact_version,
                "prompt_version": "complex-table-v1",
            },
        )
        response = (
            self.vision_cache.analyze(self.vision_provider, vision_request)
            if self.vision_cache is not None
            else self.vision_provider.analyze(vision_request)
        )
        model = response.model or request.model or self.vision_provider.config.model
        if not response.success:
            return ComplexTableVisionResult(
                manifest_id=request.manifest_id,
                visual_region_id=request.visual_region_id,
                status="incomplete",
                model=model,
                usage=response.usage,
                error=response.error or "复杂表格视觉分析未完成",
            )
        structured_table = response.payload.get("structured_table")
        confidence = response.payload.get("confidence")
        if not isinstance(structured_table, Mapping):
            return self._incomplete(request, model, response.usage, "视觉响应缺少结构化表格")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            return self._incomplete(request, model, response.usage, "视觉响应置信度无效")
        return ComplexTableVisionResult(
            manifest_id=request.manifest_id,
            visual_region_id=request.visual_region_id,
            status="candidate",
            structured_table=dict(structured_table),
            confidence=float(confidence),
            model=model,
            usage=response.usage,
        )

    @staticmethod
    def _incomplete(
        request: ComplexTableVisionRequest,
        model: str,
        usage: VisionUsage,
        error: str,
    ) -> ComplexTableVisionResult:
        """响应缺失关键审计字段时保持 incomplete，不猜测表格内容。"""
        return ComplexTableVisionResult(
            manifest_id=request.manifest_id,
            visual_region_id=request.visual_region_id,
            status="incomplete",
            model=model,
            usage=usage,
            error=error,
        )
