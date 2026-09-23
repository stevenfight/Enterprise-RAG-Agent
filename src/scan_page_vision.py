# -*- coding: utf-8 -*-
"""扫描页视觉处理：仅在无文本层或既有解析失败时产生候选内容。"""

from dataclasses import dataclass, field

from .vision_cache import VisionCallCache
from .vision_provider import BaseVisionProvider, VisionRequest, VisionUsage


@dataclass(frozen=True)
class ScanPageVisionRequest:
    """扫描页处理请求，明确文本层与既有解析状态。"""

    manifest_id: str
    page_artifact_id: str
    image_bytes: bytes
    mime_type: str
    prompt: str
    text_layer_chars: int
    parse_failed: bool
    model: str | None = None
    timeout: int = 60
    artifact_version: str = "v1"


@dataclass(frozen=True)
class ScanPageVisionResult:
    """扫描页候选结果，不携带可直接进入 verified 事实的数值字段。"""

    manifest_id: str
    page_artifact_id: str
    status: str
    extracted_text: str = ""
    confidence: float | None = None
    reason: str = ""
    model: str = ""
    usage: VisionUsage = field(default_factory=VisionUsage)
    error: str = ""
    review_required: bool = True


class ScanPageVisionService:
    """受控扫描页视觉入口，避免为已有文本的页面产生隐式视觉调用。"""

    def __init__(self, vision_provider: BaseVisionProvider, vision_cache: VisionCallCache | None = None) -> None:
        self.vision_provider = vision_provider
        self.vision_cache = vision_cache

    def analyze(self, request: ScanPageVisionRequest) -> ScanPageVisionResult:
        """仅在无文本层或解析失败时调用视觉能力，其他页面显式跳过。"""
        reason = self._eligible_reason(request)
        if reason is None:
            return ScanPageVisionResult(
                manifest_id=request.manifest_id,
                page_artifact_id=request.page_artifact_id,
                status="skipped",
                reason="已有可用文本层且解析未失败",
                review_required=False,
            )

        vision_request = VisionRequest(
            image_bytes=request.image_bytes,
            mime_type=request.mime_type,
            prompt=request.prompt,
            capability="scan_text",
            model=request.model,
            timeout=request.timeout,
            cache_context={
                "manifest_id": request.manifest_id,
                "artifact_id": request.page_artifact_id,
                "artifact_version": request.artifact_version,
                "prompt_version": "scan-page-v1",
            },
        )
        response = (
            self.vision_cache.analyze(self.vision_provider, vision_request)
            if self.vision_cache is not None
            else self.vision_provider.analyze(vision_request)
        )
        model = response.model or request.model or self.vision_provider.config.model
        if not response.success:
            return self._incomplete(
                request,
                reason,
                model,
                response.usage,
                response.error or "扫描页视觉分析未完成",
            )

        extracted_text = response.payload.get("extracted_text")
        confidence = response.payload.get("confidence")
        if not isinstance(extracted_text, str) or not extracted_text.strip():
            return self._incomplete(request, reason, model, response.usage, "视觉响应缺少扫描页文本")
        if not self._is_confidence(confidence):
            return self._incomplete(request, reason, model, response.usage, "视觉响应置信度无效")
        return ScanPageVisionResult(
            manifest_id=request.manifest_id,
            page_artifact_id=request.page_artifact_id,
            status="candidate",
            extracted_text=extracted_text,
            confidence=float(confidence),
            reason=reason,
            model=model,
            usage=response.usage,
        )

    @staticmethod
    def _eligible_reason(request: ScanPageVisionRequest) -> str | None:
        """给出可审计调用原因；解析失败优先于文本层判断。"""
        if request.parse_failed:
            return "既有解析失败"
        if int(request.text_layer_chars) <= 0:
            return "无可用文本层"
        return None

    @staticmethod
    def _is_confidence(value: object) -> bool:
        """只接受 0 到 1 的真实数值，避免布尔值混入置信度。"""
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1

    @staticmethod
    def _incomplete(
        request: ScanPageVisionRequest,
        reason: str,
        model: str,
        usage: VisionUsage,
        error: str,
    ) -> ScanPageVisionResult:
        """能力不可用或响应不完整时返回 incomplete，不静默猜测。"""
        return ScanPageVisionResult(
            manifest_id=request.manifest_id,
            page_artifact_id=request.page_artifact_id,
            status="incomplete",
            reason=reason,
            model=model,
            usage=usage,
            error=error,
        )
