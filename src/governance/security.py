"""D1.6 安全攻击集：文档注入隔离、工具参数注入校验与跨 Agent 结构化约束。

设计依据：spec-governance-operations.md「提示词注入隔离」与「跨 Agent 数据」——
- 检索到的文档内容是不可信数据，以隔离块呈现并转义结束标记，无法伪装成系统指令；
- 工具参数注入（未声明键或保留控制键）直接拒绝；
- 跨 Agent 只消费结构化数据载荷，纯文本指令载荷拒绝；
- 越权调用由 ToolPolicy 默认拒绝边界覆盖（D1.1）。
"""

from __future__ import annotations

from typing import Any

# 不可信内容隔离块标记：开始标记唯一，结束标记在内容中出现时必须被转义。
UNTRUSTED_BEGIN_MARKER = "<<<BEGIN_UNTRUSTED>>>"
UNTRUSTED_END_MARKER = "<<<END_UNTRUSTED>>>"
# 内容中结束标记的转义形式：保留可读性但不再匹配真实结束标记。
_ESCAPED_END_MARKER = "<<<ESCAPED_END_UNTRUSTED>>>"

# 工具参数保留控制键：出现即视为参数注入尝试。
_RESERVED_CONTROL_KEYS = frozenset(
    {"system", "system_prompt", "instructions", "developer", "role", "messages"}
)


class ToolParamInjectionError(ValueError):
    """工具参数包含未声明键或保留控制键时抛出。"""


class CrossAgentPayloadError(ValueError):
    """跨 Agent 载荷不是结构化数据（字典或列表）时抛出。"""


def wrap_untrusted_content(content: str) -> str:
    """将检索内容包进不可信隔离块，并转义内容中的结束标记防止越块。"""
    escaped = content.replace(UNTRUSTED_END_MARKER, _ESCAPED_END_MARKER)
    return f"{UNTRUSTED_BEGIN_MARKER}\n{escaped}\n{UNTRUSTED_END_MARKER}"


def validate_tool_params(params: dict[str, Any], *, allowed_keys: set[str]) -> dict[str, Any]:
    """校验工具参数：顶层键必须在声明清单内，且任意深度不得出现保留控制键。"""
    if not isinstance(params, dict):
        raise ToolParamInjectionError("工具参数必须是字典结构")
    unexpected = set(params) - set(allowed_keys)
    if unexpected:
        raise ToolParamInjectionError(f"工具参数包含未声明键: {sorted(unexpected)}")
    _check_reserved_keys(params)
    return params


def _check_reserved_keys(value: Any) -> None:
    """递归检查保留控制键：任意深度的字典键命中即拒绝。"""
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _RESERVED_CONTROL_KEYS:
                raise ToolParamInjectionError(f"工具参数键 {key} 是保留控制键，疑似参数注入")
            _check_reserved_keys(item)
    elif isinstance(value, list):
        for item in value:
            _check_reserved_keys(item)


def ensure_structured_payload(payload: Any) -> Any:
    """跨 Agent 数据约束：只接受字典或列表结构化载荷，纯文本载荷拒绝。"""
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return payload
    raise CrossAgentPayloadError("跨 Agent 数据只允许结构化载荷（字典或列表），拒绝纯文本指令")
