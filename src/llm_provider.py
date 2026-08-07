# -*- coding: utf-8 -*-
"""
LLM Provider 抽象层

将 LLM 调用从 ReActAgent 中解耦，支持：
  - DashScope（qwen-max/qwen-plus/qwen-turbo）
  - OpenAI 兼容协议（未来扩展）

对应方案：多Agent升级方案 步骤 0.1 改动 A
对应 SDD: openspec/changes/multi-agent-step01/specs/spec-step01-upgrade.md
"""

import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dashscope import Generation

logger = logging.getLogger("llm_provider")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


@dataclass
class LLMUsage:
    """单次 LLM 调用的 Token 用量"""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResponse:
    """LLM 调用返回的标准化结果

    保留 Token 用量，方便成本监控和聚合
    """
    content: str
    success: bool
    error: str = ""
    usage: LLMUsage = field(default_factory=LLMUsage)


class BaseLLMProvider:
    """LLM Provider 抽象基类

    所有 LLM Provider 必须实现 chat 方法。
    """

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-max",
        temperature: float = 0.3,
        timeout: int = 60,
    ) -> LLMResponse:
        """调用 LLM 并返回标准化响应

        Args:
            messages: 完整消息列表
            model: 模型名称
            temperature: 温度参数
            timeout: 超时秒数

        Returns:
            LLMResponse: 含 content + success + error + usage
        """
        raise NotImplementedError("子类必须实现 chat 方法")


class DashScopeProvider(BaseLLMProvider):
    """DashScope（通义千问）LLM Provider

    Usage:
        provider = DashScopeProvider(api_key="sk-xxx")
        resp = provider.chat(messages, model="qwen-turbo")
        if resp.success:
            print(resp.content)
            print(f"Tokens: {resp.usage.input_tokens} + {resp.usage.output_tokens}")
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._last_call_ts: float = 0.0
        self._call_count: int = 0
        logger.info("[DashScopeProvider] 初始化完成")

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-max",
        temperature: float = 0.3,
        timeout: int = 60,
    ) -> LLMResponse:
        start = time.time()
        self._call_count += 1
        logger.info(
            "[DashScopeProvider] 第 %d 次调用: model=%s, messages=%d, temperature=%.2f",
            self._call_count, model, len(messages), temperature,
        )

        try:
            resp = Generation.call(
                model=model,
                messages=messages,
                api_key=self.api_key,
                temperature=temperature,
                result_format="message",
                timeout=timeout,
            )

            elapsed = time.time() - start

            if resp.status_code == 200:
                content = resp.output.choices[0].message.content

                # 提取 Token 用量
                usage = getattr(resp, "usage", None)
                input_tokens = usage.input_tokens if usage else 0
                output_tokens = usage.output_tokens if usage else 0

                logger.info(
                    "[DashScopeProvider] 调用成功: %d 字符, "
                    "input_tokens=%d, output_tokens=%d, 耗时=%.2fs",
                    len(content), input_tokens, output_tokens, elapsed,
                )
                return LLMResponse(
                    content=content,
                    success=True,
                    usage=LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens),
                )
            else:
                logger.error(
                    "[DashScopeProvider] 调用失败: status=%s, message=%s, 耗时=%.2fs",
                    resp.status_code, resp.message, elapsed,
                )
                return LLMResponse(
                    content="",
                    success=False,
                    error=f"DashScope 调用失败: status={resp.status_code}, message={resp.message}",
                )

        except TimeoutError:
            logger.error("[DashScopeProvider] 调用超时: %.2fs", time.time() - start)
            return LLMResponse(content="", success=False, error=f"LLM 调用超时 ({timeout}s)")
        except Exception as e:
            logger.error("[DashScopeProvider] 调用异常: %s", str(e))
            return LLMResponse(content="", success=False, error=f"LLM 调用异常: {str(e)}")


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI 兼容协议 Provider（未来扩展，暂不实现）

    用于支持 DeepSeek、OpenAI 等兼容 API。
    """

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        # 未来实现：import openai; self.client = openai.OpenAI(...)

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        temperature: float = 0.3,
        timeout: int = 60,
    ) -> LLMResponse:
        raise NotImplementedError("OpenAICompatibleProvider 暂未实现")
