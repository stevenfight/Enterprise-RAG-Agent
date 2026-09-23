# -*- coding: utf-8 -*-
"""类型化视觉 Provider 边界：视觉能力独立于既有纯文本 LLM Provider。"""

from dataclasses import dataclass, field
from typing import Any, FrozenSet, Mapping

from .vision_security import VisionSafetyError, VisionSafetyGuard


@dataclass(frozen=True)
class VisionProviderConfig:
    """视觉 Provider 的显式启用状态、凭据、模型与能力声明。"""

    enabled: bool = False
    api_key: str = ""
    model: str = ""
    capabilities: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class VisionRequest:
    """视觉请求只携带内存图像字节，不接受调用方文件路径。"""

    image_bytes: bytes
    mime_type: str
    prompt: str
    capability: str
    model: str | None = None
    timeout: int = 60
    untrusted_content: str = ""
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    cache_context: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class VisionUsage:
    """视觉调用的可审计用量。"""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class VisionResponse:
    """视觉响应的统一结果；不可用与失败均有显式状态。"""

    success: bool
    status: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    error: str = ""
    model: str = ""
    usage: VisionUsage = field(default_factory=VisionUsage)


@dataclass(frozen=True)
class VisionCapabilityStatus:
    """单项视觉能力的配置检查结果。"""

    available: bool
    reason: str = ""


class BaseVisionProvider:
    """视觉能力抽象基类；不调用或包装 BaseLLMProvider.chat。"""

    def __init__(
        self,
        config: VisionProviderConfig | None = None,
        safety_guard: VisionSafetyGuard | None = None,
    ) -> None:
        self.config = config or VisionProviderConfig()
        self.safety_guard = safety_guard or VisionSafetyGuard()

    def check_capability(self, capability: str) -> VisionCapabilityStatus:
        """先检查启用状态、凭据、模型与声明能力，避免隐式文本回退。"""
        if not self.config.enabled:
            return VisionCapabilityStatus(False, "视觉能力未启用")
        if not self.config.api_key:
            return VisionCapabilityStatus(False, "视觉 Provider 缺少 API key")
        if not self.config.model:
            return VisionCapabilityStatus(False, "视觉 Provider 缺少模型配置")
        if capability not in self.config.capabilities:
            return VisionCapabilityStatus(False, f"视觉 Provider 不支持能力: {capability}")
        return VisionCapabilityStatus(True)

    def analyze(self, request: VisionRequest) -> VisionResponse:
        """执行视觉分析；不可用时返回 unavailable，绝不回退到文本聊天。"""
        status = self.check_capability(request.capability)
        if not status.available:
            return VisionResponse(success=False, status="unavailable", error=status.reason)
        try:
            safe_request = self.safety_guard.authorize(request)
        except VisionSafetyError as exc:
            return VisionResponse(success=False, status="incomplete", error=str(exc))
        return self._analyze(safe_request)

    def _analyze(self, request: VisionRequest) -> VisionResponse:
        """由具体视觉 Provider 实现实际远程调用。"""
        raise NotImplementedError("具体视觉 Provider 必须实现视觉分析")
