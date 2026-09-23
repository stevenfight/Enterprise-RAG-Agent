"""M2.4 类型化视觉 Provider 与纯文本 LLM 兼容边界测试。"""

import pytest


_ONE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
)


def _request():
    from src.vision_provider import VisionRequest

    return VisionRequest(
        image_bytes=_ONE_PIXEL_PNG,
        mime_type="image/png",
        prompt="提取表格结构",
        capability="table_structure",
    )


def test_unconfigured_or_unsupported_vision_returns_explicit_unavailable_without_text_fallback():
    """视觉能力未配置或不支持时必须显式 unavailable，不能调用文本 chat。"""
    from src.vision_provider import BaseVisionProvider, VisionProviderConfig

    disabled = BaseVisionProvider(VisionProviderConfig(enabled=False))
    missing_capability = BaseVisionProvider(
        VisionProviderConfig(enabled=True, api_key="vision-key", model="vision-model", capabilities=frozenset())
    )

    disabled_response = disabled.analyze(_request())
    capability_response = missing_capability.analyze(_request())

    assert disabled_response.status == "unavailable"
    assert disabled_response.success is False
    assert "未启用" in disabled_response.error
    assert capability_response.status == "unavailable"
    assert "不支持" in capability_response.error


def test_configured_base_provider_requires_subclass_implementation_and_preserves_typed_request():
    """已配置但无具体视觉实现时明确失败，类型化请求不接受文件路径。"""
    from src.vision_provider import BaseVisionProvider, VisionProviderConfig

    provider = BaseVisionProvider(
        VisionProviderConfig(
            enabled=True,
            api_key="vision-key",
            model="vision-model",
            capabilities=frozenset({"table_structure"}),
        )
    )

    with pytest.raises(NotImplementedError, match="视觉分析"):
        provider.analyze(_request())
    with pytest.raises(TypeError):
        _request().__class__(
            image_path="C:/private/report.png",
            mime_type="image/png",
            prompt="提取表格结构",
            capability="table_structure",
        )


def test_base_llm_chat_remains_text_only_contract():
    """新增视觉层不得改变既有 BaseLLMProvider.chat 的纯文本消息签名。"""
    from src.llm_provider import BaseLLMProvider

    with pytest.raises(NotImplementedError, match="chat"):
        BaseLLMProvider().chat([{"role": "user", "content": "文本问题"}])
