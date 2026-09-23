# -*- coding: utf-8 -*-
"""M-T23 视觉内容哈希缓存、版本隔离和调用账本测试。"""

from pathlib import Path

from src.v7_metadata_store import V7MetadataStore
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


class _CountingVisionProvider(BaseVisionProvider):
    """记录具体 Provider 调用次数的确定性视觉替身。"""

    def __init__(self, responses: list[VisionResponse] | None = None) -> None:
        super().__init__(
            VisionProviderConfig(
                enabled=True,
                api_key="vision-test-key",
                model="vision-test-model",
                capabilities=frozenset({"chart_understanding", "table_structure", "scan_text"}),
            )
        )
        self.responses = list(responses or [])
        self.requests = []

    def _analyze(self, request):
        self.requests.append(request)
        if self.responses:
            return self.responses.pop(0)
        if request.capability == "chart_understanding":
            payload = {
                "title": "收入趋势",
                "legend": ["营业收入"],
                "axes": {"x": "年度", "y": "亿元"},
                "unit": "亿元",
                "period": "2024",
                "series": [{"name": "营业收入"}],
                "trends": ["上升"],
                "numeric_confidence": 0.9,
                "data_points": {"2024": 100},
            }
        elif request.capability == "table_structure":
            payload = {
                "structured_table": {"headers": ["项目"], "rows": [["营业收入"]]},
                "confidence": 0.9,
            }
        else:
            payload = {"extracted_text": "扫描页候选内容", "confidence": 0.9}
        return VisionResponse(
            success=True,
            status="complete",
            payload=payload,
            model="vision-test-model",
            usage=VisionUsage(input_tokens=11, output_tokens=7),
        )


def _chart_request(*, artifact_version: str = "artifact-v1"):
    from src.chart_understanding import ChartUnderstandingRequest

    return ChartUnderstandingRequest(
        manifest_id="manifest-1",
        visual_region_id="region-1",
        image_bytes=_ONE_PIXEL_PNG,
        mime_type="image/png",
        prompt="提取图表结构",
        artifact_version=artifact_version,
    )


def test_visual_cache_persists_success_and_records_provider_call_then_cache_hit(tmp_path: Path):
    """相同视觉区域重新创建缓存对象后也应复用成功响应。"""
    from src.chart_understanding import ChartUnderstandingService
    from src.vision_cache import VisionCallCache

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    provider = _CountingVisionProvider()
    first_cache = VisionCallCache(store)
    request = _chart_request()

    first = ChartUnderstandingService(provider, vision_cache=first_cache).analyze(request)
    second_cache = VisionCallCache(store)
    second = ChartUnderstandingService(provider, vision_cache=second_cache).analyze(request)

    assert first == second
    assert len(provider.requests) == 1
    assert second_cache.cache_entry_count() == 1
    assert [event.event_type for event in second_cache.list_ledger()] == [
        "provider_call",
        "cache_hit",
    ]
    assert second_cache.list_ledger()[1].status == "complete"


def test_visual_cache_is_used_by_chart_table_and_scan_services(tmp_path: Path):
    """三类视觉服务均复用同一缓存边界，不各自重复调用 Provider。"""
    from src.chart_understanding import ChartUnderstandingService
    from src.complex_table_vision import ComplexTableVisionRequest, ComplexTableVisionService
    from src.scan_page_vision import ScanPageVisionRequest, ScanPageVisionService
    from src.vision_cache import VisionCallCache

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    provider = _CountingVisionProvider()
    cache = VisionCallCache(store)

    chart = ChartUnderstandingService(provider, vision_cache=cache)
    table = ComplexTableVisionService(provider, vision_cache=cache)
    scan = ScanPageVisionService(provider, vision_cache=cache)
    chart_request = _chart_request()
    table_request = ComplexTableVisionRequest(
        manifest_id="manifest-1",
        visual_region_id="region-2",
        image_bytes=_ONE_PIXEL_PNG,
        mime_type="image/png",
        prompt="提取复杂表格",
    )
    scan_request = ScanPageVisionRequest(
        manifest_id="manifest-1",
        page_artifact_id="page-1",
        image_bytes=_ONE_PIXEL_PNG,
        mime_type="image/png",
        prompt="提取扫描页文本",
        text_layer_chars=0,
        parse_failed=False,
    )

    chart.analyze(chart_request)
    chart.analyze(chart_request)
    table.analyze(table_request)
    table.analyze(table_request)
    scan.analyze(scan_request)
    scan.analyze(scan_request)

    assert [request.capability for request in provider.requests] == [
        "chart_understanding",
        "table_structure",
        "scan_text",
    ]
    assert cache.cache_entry_count() == 3
    assert [event.event_type for event in cache.list_ledger()] == [
        "provider_call",
        "cache_hit",
        "provider_call",
        "cache_hit",
        "provider_call",
        "cache_hit",
    ]


def test_visual_cache_key_changes_with_artifact_version_and_does_not_cache_failure(tmp_path: Path):
    """制品版本变化必须失效；失败响应不能形成成功缓存。"""
    from src.chart_understanding import ChartUnderstandingService
    from src.vision_cache import VisionCallCache

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    failure = VisionResponse(success=False, status="incomplete", error="暂时不可用")
    provider = _CountingVisionProvider(responses=[failure])
    cache = VisionCallCache(store)
    service = ChartUnderstandingService(provider, vision_cache=cache)

    failed = service.analyze(_chart_request())
    succeeded = service.analyze(_chart_request())
    changed_version = service.analyze(_chart_request(artifact_version="artifact-v2"))

    assert failed.status == "incomplete"
    assert succeeded.status == "candidate"
    assert changed_version.status == "candidate"
    assert len(provider.requests) == 3
    assert cache.cache_entry_count() == 2
    assert [event.status for event in cache.list_ledger()] == [
        "incomplete",
        "complete",
        "complete",
    ]
