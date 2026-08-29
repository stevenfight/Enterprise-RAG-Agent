# -*- coding: utf-8 -*-
"""金融指标的严格 canonical key 与已批准别名词典。"""

from dataclasses import dataclass


class UnknownFinancialMetricError(ValueError):
    """输入标签不在批准指标词典中。"""


@dataclass(frozen=True)
class FinancialMetricDefinition:
    """一个 canonical 指标及其可证明等价的别名。"""

    metric_key: str
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.metric_key, str) or not self.metric_key.strip():
            raise ValueError("metric_key 不能为空")
        if not isinstance(self.aliases, tuple) or not self.aliases:
            raise ValueError("aliases 必须是非空元组")


class FinancialMetricDictionary:
    """只解析白名单别名，禁止将相近收入指标自动合并。"""

    def __init__(self, definitions: list[FinancialMetricDefinition]) -> None:
        self._aliases: dict[str, str] = {}
        for definition in definitions:
            if not isinstance(definition, FinancialMetricDefinition):
                raise TypeError("definitions 必须包含 FinancialMetricDefinition")
            for label in (definition.metric_key, *definition.aliases):
                normalized = self._normalize(label)
                existing = self._aliases.get(normalized)
                if existing is not None and existing != definition.metric_key:
                    raise ValueError(f"别名 {label} 同时指向多个指标")
                self._aliases[normalized] = definition.metric_key

    @classmethod
    def default(cls) -> "FinancialMetricDictionary":
        """返回当前唯一已核验的营业收入词典项。"""
        return cls([
            FinancialMetricDefinition(
                "operating_revenue",
                ("营业收入", "营收"),
            )
        ])

    def resolve(self, label: str) -> str:
        """精确解析已批准标签；未知或模糊词汇必须显式拒绝。"""
        try:
            return self._aliases[self._normalize(label)]
        except KeyError as exc:
            raise UnknownFinancialMetricError(f"未批准或含义不明确的财务指标: {label}") from exc

    @staticmethod
    def _normalize(label: str) -> str:
        if not isinstance(label, str) or not label.strip():
            raise UnknownFinancialMetricError("财务指标标签不能为空")
        return "".join(label.split()).casefold()
