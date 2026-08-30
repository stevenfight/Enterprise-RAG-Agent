"""D1.7 任务用量统计测试（D-T10）。

规格依据：tasks.md D1.7——统计任务 Token、调用次数、延迟和成本估算。
"""

from __future__ import annotations

import pytest

from src.governance.metrics import UsageRecord, UsageTracker


def test_tracker_accumulates_tokens_calls_latency_and_cost() -> None:
    """同一任务的用量按维度累加：Token、调用次数、延迟与成本估算。"""
    tracker = UsageTracker()
    tracker.record(
        UsageRecord(task_id="t1", model="qwen-max", tokens_in=100, tokens_out=50, latency_ms=800, cost_estimate=0.02)
    )
    tracker.record(
        UsageRecord(task_id="t1", model="qwen-plus", tokens_in=200, tokens_out=100, latency_ms=400, cost_estimate=0.01)
    )
    stats = tracker.task_summary("t1")
    assert stats.tokens_in == 300
    assert stats.tokens_out == 150
    assert stats.calls == 2
    assert stats.latency_ms == 1200
    assert stats.cost_estimate == pytest.approx(0.03)


def test_tracker_isolated_per_task() -> None:
    """不同任务统计互相隔离，未知任务返回全零。"""
    tracker = UsageTracker()
    tracker.record(UsageRecord(task_id="t1", model="m", tokens_in=10, tokens_out=5, latency_ms=100, cost_estimate=0.001))
    empty = tracker.task_summary("task-unknown")
    assert empty.tokens_in == 0
    assert empty.calls == 0
    assert empty.cost_estimate == 0.0


def test_model_breakdown_per_task() -> None:
    """按模型维度拆分用量，供路由质量—成本曲线比较（D1.9）。"""
    tracker = UsageTracker()
    tracker.record(UsageRecord(task_id="t1", model="qwen-max", tokens_in=100, tokens_out=50, latency_ms=800, cost_estimate=0.02))
    tracker.record(UsageRecord(task_id="t1", model="qwen-max", tokens_in=60, tokens_out=30, latency_ms=200, cost_estimate=0.01))
    tracker.record(UsageRecord(task_id="t1", model="qwen-plus", tokens_in=200, tokens_out=100, latency_ms=400, cost_estimate=0.01))
    breakdown = tracker.model_breakdown("t1")
    assert breakdown["qwen-max"].calls == 2
    assert breakdown["qwen-max"].tokens_in == 160
    assert breakdown["qwen-plus"].calls == 1
