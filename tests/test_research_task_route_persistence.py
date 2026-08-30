# -*- coding: utf-8 -*-
"""C2.7 路由决策持久化与重试守卫的 TDD 测试。

持久任务一旦选定 single/multi 执行路径，失败时必须保存选定路径与失败分类，
重试不得静默切换路径；重试以新建 C0 run 实现（failed 为终态，禁止状态回迁）。
"""

from pathlib import Path

import pytest


def _adapter(tmp_path: Path):
    from src.durable_execution import DurableExecutionStore
    from src.research_task_adapter import ResearchTaskAdapter
    from src.v7_metadata_store import V7MetadataStore

    store = DurableExecutionStore(V7MetadataStore(tmp_path / "v7_metadata.sqlite3"))
    return ResearchTaskAdapter(store), store


def test_route_selection_is_persisted_and_immutable(tmp_path: Path):
    adapter, _store = _adapter(tmp_path)

    selected = adapter.record_route_selection(
        "route-001", selected_path="multi", reason="planner 判定需要多步研究", actor="planner"
    )

    assert selected.selected_path == "multi"
    assert adapter.route_selection("route-001") == "multi"

    # 相同路径重复选择幂等返回，不新增记录
    again = adapter.record_route_selection(
        "route-001", selected_path="multi", reason="重复提交", actor="planner"
    )
    assert adapter.route_decisions("route-001") == (selected,) or again.decision_id == selected.decision_id


def test_route_selection_rejects_conflicting_path(tmp_path: Path):
    from src.research_task_adapter import RoutePathConflictError

    adapter, _store = _adapter(tmp_path)
    adapter.record_route_selection(
        "route-002", selected_path="multi", reason="初始选择", actor="planner"
    )

    with pytest.raises(RoutePathConflictError):
        adapter.record_route_selection(
            "route-002", selected_path="single", reason="试图改道", actor="planner"
        )


def test_route_selection_requires_known_path(tmp_path: Path):
    adapter, _store = _adapter(tmp_path)

    with pytest.raises(ValueError):
        adapter.record_route_selection(
            "route-003", selected_path="parallel", reason="未知路径", actor="planner"
        )


def test_failure_persists_selected_path_and_failure_category(tmp_path: Path):
    from src.research_task_adapter import ResearchFailureDecision

    adapter, _store = _adapter(tmp_path)
    adapter.record_route_selection(
        "route-004", selected_path="multi", reason="初始选择", actor="planner"
    )
    adapter.create_task("route-004", ["plan", "execute"])
    started = adapter.start_task("route-004", 0, "cmd-start", actor="worker")

    failure = ResearchFailureDecision(
        category="network_timeout", action="retry", retry_count=1, max_retries=3
    )
    recorded = adapter.fail_task(
        "route-004", started.revision, "cmd-fail-1", actor="worker"
    )
    persisted = adapter.record_failure("route-004", failure, actor="worker")

    assert recorded.status == "failed"
    assert persisted.decision_type == "failure"
    assert persisted.detail["category"] == "network_timeout"
    assert persisted.detail["action"] == "retry"
    assert persisted.detail["retry_count"] == 1
    assert persisted.detail["max_retries"] == 3
    # 失败后选定路径不变，不静默回退
    assert adapter.route_selection("route-004") == "multi"


def test_retry_rejects_silent_path_switch(tmp_path: Path):
    from src.research_task_adapter import RoutePathConflictError

    adapter, store = _adapter(tmp_path)
    adapter.record_route_selection(
        "route-005", selected_path="multi", reason="初始选择", actor="planner"
    )
    adapter.create_task("route-005", ["plan"])
    started = adapter.start_task("route-005", 0, "cmd-start", actor="worker")
    adapter.fail_task("route-005", started.revision, "cmd-fail-1", actor="worker")
    runs_before = len([name for name in store.table_names()])

    with pytest.raises(RoutePathConflictError):
        adapter.retry_task(
            "route-005",
            requested_path="single",
            dag_step_ids=["plan"],
            command_id="cmd-retry-1",
            actor="operator",
        )


def test_retry_creates_new_run_inheriting_selected_path(tmp_path: Path):
    adapter, _store = _adapter(tmp_path)
    adapter.record_route_selection(
        "route-006", selected_path="multi", reason="初始选择", actor="planner"
    )
    adapter.create_task("route-006", ["plan"])
    started = adapter.start_task("route-006", 0, "cmd-start", actor="worker")
    adapter.fail_task("route-006", started.revision, "cmd-fail-1", actor="worker")

    retried = adapter.retry_task(
        "route-006",
        requested_path="multi",
        dag_step_ids=["plan"],
        command_id="cmd-retry-1",
        actor="operator",
    )

    # failed 为终态，重试必须落在全新 run 上
    assert retried.task_id == "route-006-retry-1"
    assert retried.run_id == "research:route-006-retry-1"
    assert retried.status == "pending"
    assert _store.run("research:route-006").status == "failed"
    # 新任务继承选定路径，可继续走同一治理链
    assert adapter.route_selection("route-006-retry-1") == "multi"
    decisions = adapter.route_decisions("route-006")
    retry_records = [item for item in decisions if item.decision_type == "retry"]
    assert len(retry_records) == 1
    assert retry_records[0].selected_path == "multi"
    assert retry_records[0].detail["new_task_id"] == "route-006-retry-1"


def test_retry_requires_recorded_path_and_failed_run(tmp_path: Path):
    adapter, _store = _adapter(tmp_path)

    # 未记录选定路径
    with pytest.raises(ValueError):
        adapter.retry_task(
            "route-007",
            requested_path="multi",
            dag_step_ids=["plan"],
            command_id="cmd-retry-a",
            actor="operator",
        )

    # 已记录路径但任务尚未失败
    adapter.record_route_selection(
        "route-008", selected_path="multi", reason="初始选择", actor="planner"
    )
    adapter.create_task("route-008", ["plan"])
    with pytest.raises(ValueError):
        adapter.retry_task(
            "route-008",
            requested_path="multi",
            dag_step_ids=["plan"],
            command_id="cmd-retry-b",
            actor="operator",
        )
