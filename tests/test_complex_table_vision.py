"""M2.5 复杂表格视觉分析结果与低置信拦截测试。"""

from src.vision_provider import BaseVisionProvider, VisionProviderConfig, VisionResponse, VisionUsage


_ONE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
)


class _StaticVisionProvider(BaseVisionProvider):
    """仅用于验证服务边界的受控视觉 Provider。"""

    def __init__(self, response: VisionResponse) -> None:
        super().__init__(
            VisionProviderConfig(
                enabled=True,
                api_key="vision-key",
                model="vision-model-v1",
                capabilities=frozenset({"table_structure"}),
            )
        )
        self.response = response

    def _analyze(self, request):
        return self.response


def _request():
    from src.complex_table_vision import ComplexTableVisionRequest

    return ComplexTableVisionRequest(
        manifest_id="manifest-1",
        visual_region_id="region-1",
        image_bytes=_ONE_PIXEL_PNG,
        mime_type="image/png",
        prompt="提取复杂财务表格的结构",
    )


def test_complex_table_result_keeps_structure_confidence_model_usage_and_region_as_candidate():
    """高置信视觉结果仍是候选，不绕过后续统一事实审核。"""
    from src.complex_table_vision import ComplexTableVisionService

    provider = _StaticVisionProvider(
        VisionResponse(
            success=True,
            status="complete",
            payload={"structured_table": {"headers": ["项目", "2024年度"], "rows": [["营业收入", "123"]]}, "confidence": 0.92},
            model="vision-model-v1",
            usage=VisionUsage(input_tokens=12, output_tokens=34),
        )
    )

    result = ComplexTableVisionService(provider).analyze(_request())

    assert result.status == "candidate"
    assert result.confidence == 0.92
    assert result.model == "vision-model-v1"
    assert result.usage == VisionUsage(input_tokens=12, output_tokens=34)
    assert result.visual_region_id == "region-1"
    assert result.structured_table["headers"] == ["项目", "2024年度"]
    assert result.review_required is True


def test_low_confidence_or_unavailable_complex_table_never_becomes_complete_or_verified():
    """低置信保持 candidate；视觉能力不可用明确为 incomplete。"""
    from src.complex_table_vision import ComplexTableVisionService

    low_confidence = _StaticVisionProvider(
        VisionResponse(
            success=True,
            status="complete",
            payload={"structured_table": {"headers": ["项目"], "rows": []}, "confidence": 0.20},
        )
    )
    unavailable = BaseVisionProvider(VisionProviderConfig(enabled=False))

    low_result = ComplexTableVisionService(low_confidence).analyze(_request())
    unavailable_result = ComplexTableVisionService(unavailable).analyze(_request())

    assert low_result.status == "candidate"
    assert low_result.confidence == 0.20
    assert low_result.review_required is True
    assert unavailable_result.status == "incomplete"
    assert unavailable_result.structured_table == {}
    assert unavailable_result.review_required is True
