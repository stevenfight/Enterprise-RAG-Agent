"""D1.5 敏感字段脱敏：日志、追踪和报告持久化前统一脱敏。

设计依据：spec-governance-operations.md「审计与脱敏」——
敏感字段（密钥、令牌、凭据等）在持久化前替换为统一掩码，返回新结构不改原始数据。
"""

from __future__ import annotations

from typing import Any

# 统一掩码值：审计与回放时可以明确识别"此处为脱敏字段"。
REDACTED_VALUE = "[REDACTED]"

# 敏感键识别标记：键名小写并将连字符/空格归一为下划线后做子串匹配。
SENSITIVE_KEY_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
)


def _is_sensitive_key(key: Any) -> bool:
    """判断键名是否命中敏感标记（大小写与连字符变体均覆盖）。"""
    normalized = str(key).lower().replace("-", "_").replace(" ", "_")
    return any(marker in normalized for marker in SENSITIVE_KEY_MARKERS)


def redact_sensitive_fields(value: Any) -> Any:
    """递归脱敏：字典敏感键替换掩码，列表/元组逐项处理，标量原样返回。"""
    if isinstance(value, dict):
        return {
            key: (REDACTED_VALUE if _is_sensitive_key(key) else redact_sensitive_fields(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_fields(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_fields(item) for item in value)
    return value
