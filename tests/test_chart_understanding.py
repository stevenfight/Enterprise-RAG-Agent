# -*- coding: utf-8 -*-
"""图表理解服务的保守输出边界测试。"""

from src.chart_understanding import (
    ChartUnderstandingRequest,
    ChartUnderstandingService,
)
from src.vision_provider import (
    BaseVisionProvider,
    VisionProviderConfig,
    VisionResponse,
    VisionUsage,
)


_ONE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
)


class _StaticVisionProvider(BaseVisionProvider):
    """仅用于验证图表服务输出边界的稳定视觉替身。"""

    def __init__(self, response: VisionResponse) -> None:
        super().__init__(
            VisionProviderConfig(
                enabled=True,
                api_key="test-key",
                model="vision-test",
                capabilities=frozenset({"chart_understanding"}),
            )
        )
        self.response = response

    def _analyze(self, request):
        return self.response


def _request() -> ChartUnderstandingRequest:
    return ChartUnderstandingRequest(
        manifest_id="manifest-1",
        visual_region_id="region-chart-1",
        image_bytes=_ONE_PIXEL_PNG,
        mime_type="image/png",
        prompt="提取图表结构与趋势",
    )


def test_chart_understanding_preserves_auditable_structure_and_reliable_points():
    provider = _StaticVisionProvider(
        VisionResponse(
            success=True,
            status="success",
            payload={
                "title": "营业收入趋势",
                "legend": ["营业收入"],
                "axes": {
                    "x": {"label": "年度", "values": ["2023", "2024"]},
                    "y": {"label": "金额", "unit": "亿元"},
                },
                "unit": "亿元",
                "period": "2023-2024 年度",
                "series": [{"name": "营业收入"}],
                "data_points": {"营业收入": [100.0, 120.0]},
                "trends": ["营业收入上升"],
                "numeric_confidence": 0.95,
            },
            model="vision-test",
            usage=VisionUsage(input_tokens=11, output_tokens=7),
        )
    )

    result = ChartUnderstandingService(provider).analyze(_request())

    assert result.status == "candidate"
    assert result.review_required is True
    assert result.title == "营业收入趋势"
    assert result.legend == ("营业收入",)
    assert result.axes["y"]["unit"] == "亿元"
    assert result.unit == "亿元"
    assert result.period == "2023-2024 年度"
    assert result.series == ({"name": "营业收入"},)
    assert result.data_points == {"营业收入": [100.0, 120.0]}
    assert result.trends == ("营业收入上升",)
    assert result.numeric_confidence == 0.95
    assert result.usage == VisionUsage(input_tokens=11, output_tokens=7)


def test_chart_understanding_keeps_only_trends_when_numeric_points_are_unreliable():
    provider = _StaticVisionProvider(
        VisionResponse(
            success=True,
            status="success",
            payload={
                "title": "毛利率变化",
                "legend": ["毛利率"],
                "axes": {"x": {"label": "年度"}, "y": {"label": "百分比"}},
                "unit": "%",
                "period": "2023-2024 年度",
                "series": [{"name": "毛利率"}],
                "data_points": {"毛利率": [30.1, 32.4]},
                "trends": ["毛利率上升"],
                "numeric_confidence": 0.42,
            },
        )
    )

    result = ChartUnderstandingService(provider).analyze(_request())

    assert result.status == "candidate"
    assert result.data_points == {}
    assert result.trends == ("毛利率上升",)
    assert result.numeric_confidence == 0.42
    assert result.review_required is True


def test_chart_understanding_returns_incomplete_when_required_structure_is_missing():
    provider = _StaticVisionProvider(
        VisionResponse(
            success=True,
            status="success",
            payload={"title": "缺少图表结构", "numeric_confidence": 0.95},
        )
    )

    result = ChartUnderstandingService(provider).analyze(_request())

    assert result.status == "incomplete"
    assert result.data_points == {}
    assert "图表" in result.error
