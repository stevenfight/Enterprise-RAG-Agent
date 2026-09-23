# -*- coding: utf-8 -*-
"""图表视觉理解：保留可审计结构，数值不可靠时只输出趋势候选。"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .vision_cache import VisionCallCache
from .vision_provider import BaseVisionProvider, VisionRequest, VisionUsage


@dataclass(frozen=True)
class ChartUnderstandingRequest:
    """图表视觉请求与受控 manifest/区域身份。"""

    manifest_id: str
    visual_region_id: str
    image_bytes: bytes
    mime_type: str
    prompt: str
    model: str | None = None
    timeout: int = 60
    artifact_version: str = "v1"


@dataclass(frozen=True)
class ChartUnderstandingResult:
    """图表理解候选结果；成功结果仍需审核，不构成已核验事实。"""

    manifest_id: str
    visual_region_id: str
    status: str
    title: str = ""
    legend: tuple[str, ...] = ()
    axes: Mapping[str, Any] = field(default_factory=dict)
    unit: str = ""
    period: str = ""
    series: tuple[Mapping[str, Any], ...] = ()
    data_points: Mapping[str, Any] = field(default_factory=dict)
    trends: tuple[str, ...] = ()
    numeric_confidence: float | None = None
    model: str = ""
    usage: VisionUsage = field(default_factory=VisionUsage)
    error: str = ""
    review_required: bool = True


class ChartUnderstandingService:
    """将视觉图表响应约束为候选；低数值置信度不输出数据点。"""

    def __init__(
        self,
        vision_provider: BaseVisionProvider,
        numeric_confidence_threshold: float = 0.85,
        vision_cache: VisionCallCache | None = None,
    ) -> None:
        if (
            not isinstance(numeric_confidence_threshold, (int, float))
            or isinstance(numeric_confidence_threshold, bool)
            or not 0 <= numeric_confidence_threshold <= 1
        ):
            raise ValueError("数值置信度阈值必须在 0 到 1 之间")
        self.vision_provider = vision_provider
        self.numeric_confidence_threshold = float(numeric_confidence_threshold)
        self.vision_cache = vision_cache

    def analyze(self, request: ChartUnderstandingRequest) -> ChartUnderstandingResult:
        """提取图表结构；不可靠的精确数值一律不透传。"""
        vision_request = VisionRequest(
            image_bytes=request.image_bytes,
            mime_type=request.mime_type,
            prompt=request.prompt,
            capability="chart_understanding",
            model=request.model,
            timeout=request.timeout,
            cache_context={
                "manifest_id": request.manifest_id,
                "artifact_id": request.visual_region_id,
                "artifact_version": request.artifact_version,
                "prompt_version": "chart-understanding-v1",
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
                model,
                response.usage,
                response.error or "图表视觉分析未完成",
            )

        payload = response.payload
        title = payload.get("title")
        legend = payload.get("legend")
        axes = payload.get("axes")
        unit = payload.get("unit")
        period = payload.get("period")
        series = payload.get("series")
        trends = payload.get("trends")
        confidence = payload.get("numeric_confidence")
        if not isinstance(title, str) or not title:
            return self._incomplete(request, model, response.usage, "视觉响应缺少图表标题")
        if not self._is_text_sequence(legend):
            return self._incomplete(request, model, response.usage, "视觉响应缺少图表图例")
        if not isinstance(axes, Mapping):
            return self._incomplete(request, model, response.usage, "视觉响应缺少图表坐标轴")
        if not isinstance(unit, str) or not isinstance(period, str):
            return self._incomplete(request, model, response.usage, "视觉响应缺少图表单位或期间")
        if not self._is_mapping_sequence(series):
            return self._incomplete(request, model, response.usage, "视觉响应缺少图表系列")
        if not self._is_text_sequence(trends):
            return self._incomplete(request, model, response.usage, "视觉响应缺少图表趋势")
        if not self._is_confidence(confidence):
            return self._incomplete(request, model, response.usage, "视觉响应数值置信度无效")

        data_points = payload.get("data_points", {})
        if confidence >= self.numeric_confidence_threshold:
            if not isinstance(data_points, Mapping):
                return self._incomplete(request, model, response.usage, "高置信图表响应缺少数据点")
            accepted_points: Mapping[str, Any] = dict(data_points)
        else:
            accepted_points = {}

        return ChartUnderstandingResult(
            manifest_id=request.manifest_id,
            visual_region_id=request.visual_region_id,
            status="candidate",
            title=title,
            legend=tuple(legend),
            axes=dict(axes),
            unit=unit,
            period=period,
            series=tuple(dict(item) for item in series),
            data_points=accepted_points,
            trends=tuple(trends),
            numeric_confidence=float(confidence),
            model=model,
            usage=response.usage,
        )

    @staticmethod
    def _is_text_sequence(value: object) -> bool:
        """校验图例和趋势为文本序列，避免字符串被视为字符序列。"""
        return (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes))
            and all(isinstance(item, str) for item in value)
        )

    @staticmethod
    def _is_mapping_sequence(value: object) -> bool:
        """校验系列列表中的每项均保持映射结构。"""
        return (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes))
            and all(isinstance(item, Mapping) for item in value)
        )

    @staticmethod
    def _is_confidence(value: object) -> bool:
        """置信度仅接受有限范围内的数值，不把布尔值当数值。"""
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1

    @staticmethod
    def _incomplete(
        request: ChartUnderstandingRequest,
        model: str,
        usage: VisionUsage,
        error: str,
    ) -> ChartUnderstandingResult:
        """关键结构不完整时显式返回 incomplete，不猜测图表内容。"""
        return ChartUnderstandingResult(
            manifest_id=request.manifest_id,
            visual_region_id=request.visual_region_id,
            status="incomplete",
            model=model,
            usage=usage,
            error=error,
        )
