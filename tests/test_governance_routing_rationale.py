"""D1.9 路由质量—成本曲线与理由保存测试。

规格依据：tasks.md D1.9 与 spec-governance-operations.md「路由可解释」——
比较现有 single/multi 路由的质量与成本，并保存包含复杂度、风险、成本依据的理由。
"""

from __future__ import annotations

import pytest

from src.governance.audit import GovernanceAuditStore
from src.governance.routing_rationale import (
    RouteComparison,
    compare_routes,
    save_routing_rationale,
)
from src.v7_metadata_store import V7MetadataStore


@pytest.fixture()
def metadata_store(tmp_path):
    """每个用例独立初始化的 V7 元数据库。"""
    store = V7MetadataStore(tmp_path / "governance.db")
    store.initialize()
    return store


SINGLE = RouteComparison(path="single", quality_score=0.72, cost_estimate=0.010, latency_ms=3000)
MULTI = RouteComparison(path="multi", quality_score=0.86, cost_estimate=0.040, latency_ms=12000)


def test_compare_routes_prefers_better_quality_per_cost() -> None:
    """中等复杂度与风险下，质量成本比更高的 single 路由胜出。"""
    rationale = compare_routes(single=SINGLE, multi=MULTI, complexity="medium", risk="medium")
    assert rationale.chosen_path == "single"
    assert "single" in rationale.reason
    assert "multi" in rationale.reason
    assert rationale.complexity == "medium"
    assert rationale.risk == "medium"


def test_high_complexity_or_risk_prefers_quality() -> None:
    """高复杂度或高风险时优先质量，选择 multi 路由。"""
    rationale = compare_routes(single=SINGLE, multi=MULTI, complexity="high", risk="medium")
    assert rationale.chosen_path == "multi"
    assert rationale.reason


def test_save_routing_rationale_persists_via_audit(metadata_store) -> None:
    """路由理由通过只追加审计账本持久化，回放可还原比较依据。"""
    audit = GovernanceAuditStore(metadata_store)
    rationale = compare_routes(single=SINGLE, multi=MULTI, complexity="medium", risk="medium")
    save_routing_rationale(audit, rationale, task_id="task-1", run_id="run-1")
    events = audit.replay_task("task-1")
    assert [event.action for event in events] == ["route_selected"]
    detail = events[-1].event.detail
    assert detail["chosen_path"] == rationale.chosen_path
    assert detail["reason"] == rationale.reason
    assert detail["complexity"] == "medium"
    assert detail["risk"] == "medium"
    paths = {alternative["path"] for alternative in detail["alternatives"]}
    assert paths == {"single", "multi"}
    for alternative in detail["alternatives"]:
        assert alternative["quality_score"] > 0
        assert alternative["cost_estimate"] > 0
