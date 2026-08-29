# -*- coding: utf-8 -*-
"""v7 默认关闭的严格功能开关。"""

from dataclasses import dataclass
from typing import Any, Mapping


class FeatureFlagConfigurationError(ValueError):
    """v7 功能开关缺少依赖或配置格式无效。"""


@dataclass(frozen=True)
class V7FeatureFlags:
    """仅供 v7 新路径读取的功能开关，默认不影响 legacy 行为。"""

    financial_trust_enabled: bool = False
    durable_execution_enabled: bool = False
    multimodal_enabled: bool = False
    research_tasks_enabled: bool = False

    @classmethod
    def from_mapping(
        cls,
        raw_flags: Mapping[str, Any] | None,
    ) -> "V7FeatureFlags":
        """从配置映射构建开关，并对依赖关系 fail closed。"""
        if raw_flags is None:
            return cls()
        if not isinstance(raw_flags, Mapping):
            raise FeatureFlagConfigurationError("v7 功能开关必须是对象")

        supported = set(cls.__dataclass_fields__)
        unknown = sorted(set(raw_flags) - supported)
        if unknown:
            raise FeatureFlagConfigurationError(
                "v7 功能开关存在未知字段: " + ", ".join(unknown)
            )

        values: dict[str, bool] = {}
        for name in supported:
            value = raw_flags.get(name, False)
            if type(value) is not bool:
                raise FeatureFlagConfigurationError(
                    f"v7 功能开关 {name} 必须是布尔值"
                )
            values[name] = value

        dependent_enabled = (
            values["multimodal_enabled"] or values["research_tasks_enabled"]
        )
        if dependent_enabled and not values["financial_trust_enabled"]:
            raise FeatureFlagConfigurationError(
                "multimodal_enabled/research_tasks_enabled 依赖 financial_trust_enabled=true"
            )
        if dependent_enabled and not values["durable_execution_enabled"]:
            raise FeatureFlagConfigurationError(
                "multimodal_enabled/research_tasks_enabled 依赖 durable_execution_enabled=true"
            )
        return cls(**values)
