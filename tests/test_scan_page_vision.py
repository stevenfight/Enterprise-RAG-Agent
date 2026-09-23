# -*- coding: utf-8 -*-
"""扫描页视觉处理的受控路由与不完整状态测试。"""

from src.scan_page_vision import ScanPageVisionRequest, ScanPageVisionService
from src.vision_provider import (
    BaseVisionProvider,
    VisionProviderConfig,
    VisionResponse,
)


_ONE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
)


class _StaticVisionProvider(BaseVisionProvider):
    """记录请求次数的稳定视觉替身。"""

    def __init__(self, response: VisionResponse) -> None:
        super().__init__(
            VisionProviderConfig(
                enabled=True,
                api_key="test-key",
                model="vision-test",
                capabilities=frozenset({"scan_text"}),
            )
        )
        self.response = response
        self.requests = []

    def _analyze(self, request):
        self.requests.append(request)
        return self.response


def _request(**overrides) -> ScanPageVisionRequest:
    values = {
        "manifest_id": "manifest-1",
        "page_artifact_id": "page-1",
        "image_bytes": _ONE_PIXEL_PNG,
        "mime_type": "image/png",
        "prompt": "提取扫描页文本",
        "text_layer_chars": 0,
        "parse_failed": False,
    }
    values.update(overrides)
    return ScanPageVisionRequest(**values)


def test_scan_page_calls_vision_only_when_text_layer_is_unavailable():
    provider = _StaticVisionProvider(
        VisionResponse(
            success=True,
            status="success",
            payload={"extracted_text": "扫描页候选内容", "confidence": 0.91},
        )
    )

    result = ScanPageVisionService(provider).analyze(_request())

    assert result.status == "candidate"
    assert result.review_required is True
    assert result.extracted_text == "扫描页候选内容"
    assert result.confidence == 0.91
    assert len(provider.requests) == 1
    assert provider.requests[0].capability == "scan_text"


def test_scan_page_calls_vision_when_existing_parse_has_failed():
    provider = _StaticVisionProvider(
        VisionResponse(
            success=True,
            status="success",
            payload={"extracted_text": "解析失败后的候选内容", "confidence": 0.87},
        )
    )

    result = ScanPageVisionService(provider).analyze(
        _request(text_layer_chars=120, parse_failed=True)
    )

    assert result.status == "candidate"
    assert result.reason == "既有解析失败"
    assert len(provider.requests) == 1


def test_normal_text_page_is_skipped_without_a_vision_request():
    provider = _StaticVisionProvider(
        VisionResponse(success=True, status="success", payload={})
    )

    result = ScanPageVisionService(provider).analyze(_request(text_layer_chars=120))

    assert result.status == "skipped"
    assert result.reason == "已有可用文本层且解析未失败"
    assert provider.requests == []


def test_unavailable_or_incomplete_scan_response_returns_incomplete_without_guessing():
    unavailable_provider = BaseVisionProvider()
    unavailable = ScanPageVisionService(unavailable_provider).analyze(_request())

    malformed_provider = _StaticVisionProvider(
        VisionResponse(success=True, status="success", payload={"confidence": 0.9})
    )
    malformed = ScanPageVisionService(malformed_provider).analyze(_request())

    assert unavailable.status == "incomplete"
    assert unavailable.extracted_text == ""
    assert malformed.status == "incomplete"
    assert malformed.extracted_text == ""
