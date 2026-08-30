"""D1.7 任务用量统计：Token、调用次数、延迟与成本估算。

设计依据：tasks.md D1.7——按任务累计用量，并支持按模型拆分，
为 D1.8 预算控制与 D1.9 路由质量—成本曲线提供数据。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UsageRecord:
    """单次模型调用用量记录。"""

    task_id: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_estimate: float


@dataclass(frozen=True)
class TaskUsageStats:
    """任务级用量汇总。"""

    task_id: str
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    latency_ms: int = 0
    cost_estimate: float = 0.0


@dataclass(frozen=True)
class ModelUsageStats:
    """按模型拆分的用量汇总。"""

    model: str
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    cost_estimate: float = 0.0


class UsageTracker:
    """进程内用量追踪器：记录、按任务汇总与按模型拆分。"""

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []

    def record(self, record: UsageRecord) -> None:
        """记录一次模型调用用量。"""
        self._records.append(record)

    def task_summary(self, task_id: str) -> TaskUsageStats:
        """返回任务级用量汇总；未知任务返回全零统计。"""
        return _Aggregate(
            record for record in self._records if record.task_id == task_id
        ).to_task_stats(task_id)

    def model_breakdown(self, task_id: str) -> dict[str, ModelUsageStats]:
        """返回任务内按模型拆分的用量汇总。"""
        grouped: dict[str, list[UsageRecord]] = {}
        for record in self._records:
            if record.task_id != task_id:
                continue
            grouped.setdefault(record.model, []).append(record)
        return {
            model: _Aggregate(records).to_model_stats(model)
            for model, records in sorted(grouped.items())
        }


class _Aggregate:
    """用量累加的内部实现，汇总后转换为任务级或模型级统计。"""

    def __init__(self, records) -> None:
        self.tokens_in = 0
        self.tokens_out = 0
        self.calls = 0
        self.latency_ms = 0
        self.cost_estimate = 0.0
        for record in records:
            self.tokens_in += record.tokens_in
            self.tokens_out += record.tokens_out
            self.calls += 1
            self.latency_ms += record.latency_ms
            self.cost_estimate += record.cost_estimate

    def to_task_stats(self, task_id: str) -> TaskUsageStats:
        return TaskUsageStats(
            task_id=task_id,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            calls=self.calls,
            latency_ms=self.latency_ms,
            cost_estimate=self.cost_estimate,
        )

    def to_model_stats(self, model: str) -> ModelUsageStats:
        return ModelUsageStats(
            model=model,
            calls=self.calls,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            latency_ms=self.latency_ms,
            cost_estimate=self.cost_estimate,
        )
