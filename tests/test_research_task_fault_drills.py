"""C2.9 五类故障演练：Worker 异常、进程中断、并发控制命令、超时晚到结果、断线重连。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace


class _StubSubtask:
    """演练用 DAG 子任务桩，只提供 Planner 输出中的稳定步骤 ID。"""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id


class _StubPlan:
    """演练用计划桩，结构与 TaskPlanner 输出兼容。"""

    def __init__(self, step_ids: tuple[str, ...]) -> None:
        self.subtasks = [_StubSubtask(step_id) for step_id in step_ids]


def _harness(tmp_path: Path):
    from src.durable_execution import DurableExecutionStore
    from src.research_task_adapter import ResearchTaskAdapter
    from src.research_task_orchestrator import ResearchTaskOrchestrator
    from src.v7_metadata_store import V7MetadataStore

    db_path = tmp_path / "v7_metadata.sqlite3"
    store = DurableExecutionStore(V7MetadataStore(db_path))
    orchestrator = ResearchTaskOrchestrator(ResearchTaskAdapter(store))
    return store, orchestrator, db_path


def test_drill_worker_exception_persists_failure_and_rejects_late_result(tmp_path: Path):
    store, orchestrator, _db_path = _harness(tmp_path)
    adapter = orchestrator.task_adapter
    plan = _StubPlan(("fetch", "analyze"))

    started = orchestrator.start_planned_task("drill-worker", plan, command_id="cmd-start", actor="tester")
    adapter.record_route_selection("drill-worker", selected_path="single", reason="单文档问答", actor="tester")

    fetch_claim = orchestrator.claim_dag_step("drill-worker", "fetch", "worker-a", now=1000)
    orchestrator.commit_dag_step(
        "drill-worker", "fetch", fetch_claim.attempt.attempt_token, "worker-a", started.revision,
        plan, {"index_generation": "gen-1"},
        {"idempotency_key": "drill-fetch-1", "status": "succeeded"}, now=1001,
    )

    # Worker 在 analyze 步骤先领取租约，随后抛出不可恢复异常
    analyze_claim = orchestrator.claim_dag_step("drill-worker", "analyze", "worker-a", now=1002)

    # 重试型失败：分类为 retryable 时任务保持运行，等待编排器重新领取
    retryable = orchestrator.handle_step_failure(
        "drill-worker", "provider_unavailable",
        retry_count=0, max_retries=2, expected_revision=started.revision,
        command_id="cmd-retryable", actor="orchestrator",
    )
    assert retryable.status == "running"

    # 重试耗尽：分类为 retry_exhausted 且动作 failed，任务迁移为终态
    failed = orchestrator.handle_step_failure(
        "drill-worker", "provider_unavailable",
        retry_count=2, max_retries=2, expected_revision=retryable.revision,
        command_id="cmd-fail", actor="orchestrator",
    )
    assert failed.status == "failed"
    assert store.run("research:drill-worker").status == "failed"

    # 失败已持久记录且选定路径不变，不静默改道
    decisions = adapter.route_decisions("drill-worker")
    failure_records = [item for item in decisions if item.decision_type == "failure"]
    assert [item.detail["retry_count"] for item in failure_records] == [0, 2]
    assert all(item.detail["category"] in {"retryable", "retry_exhausted"} for item in failure_records)
    assert adapter.route_selection("drill-worker") == "single"

    # 崩溃前已领取的 analyze 晚到结果不能复活 failed 任务
    late = orchestrator.commit_dag_step(
        "drill-worker", "analyze", analyze_claim.attempt.attempt_token, "worker-a", failed.revision,
        plan, {"index_generation": "gen-1"},
        {"idempotency_key": "drill-analyze-1", "status": "succeeded"}, now=1003,
    )
    assert late.status == "discarded"
    assert [item.step_id for item in store.checkpoints("research:drill-worker")] == ["fetch"]

    # 显式重试新建全新 run 并继承选定路径，原 run 保持 failed
    retried = adapter.retry_task(
        "drill-worker", requested_path="single", dag_step_ids=("fetch", "analyze"),
        command_id="cmd-retry", actor="tester",
    )
    assert retried.task_id == "drill-worker-retry-1"
    assert retried.status == "pending"
    assert adapter.route_selection("drill-worker-retry-1") == "single"
    assert store.run("research:drill-worker").status == "failed"
    retry_decision = adapter.route_decisions("drill-worker")[-1]
    assert retry_decision.detail["new_task_id"] == "drill-worker-retry-1"

    # 重试不允许改道为 multi
    import pytest

    from src.research_task_adapter import RoutePathConflictError

    with pytest.raises(RoutePathConflictError):
        adapter.retry_task(
            "drill-worker", requested_path="multi", dag_step_ids=("fetch", "analyze"),
            command_id="cmd-retry-multi", actor="tester",
        )


def test_drill_process_interruption_resumes_without_duplicate_side_effects(tmp_path: Path):
    store, orchestrator, db_path = _harness(tmp_path)
    plan = _StubPlan(("fetch", "analyze"))

    started = orchestrator.start_planned_task("drill-crash", plan, command_id="cmd-start", actor="tester")
    fetch_claim = orchestrator.claim_dag_step("drill-crash", "fetch", "worker-a", now=1000)
    orchestrator.commit_dag_step(
        "drill-crash", "fetch", fetch_claim.attempt.attempt_token, "worker-a", started.revision,
        plan, {"index_generation": "gen-1"},
        {"idempotency_key": "drill-fetch-1", "status": "succeeded"}, now=1001,
    )

    # 模拟进程中断：不执行任何清理，直接基于同一数据库重建执行环境
    from src.durable_execution import DurableExecutionStore
    from src.research_task_adapter import ResearchTaskAdapter
    from src.research_task_orchestrator import ResearchTaskOrchestrator
    from src.v7_metadata_store import V7MetadataStore

    restarted = ResearchTaskOrchestrator(
        ResearchTaskAdapter(DurableExecutionStore(V7MetadataStore(db_path)))
    )
    snapshot = restarted.task_adapter.task_snapshot("drill-crash")
    assert snapshot.status == "running"

    # 依赖版本一致：已完成的 fetch 步骤与成功调用可复用
    recovery = restarted.recover_interrupted_task(
        "drill-crash",
        {"index_generation": "gen-1"},
        {"fetch": "drill-fetch-1", "analyze": "drill-analyze-1"},
    )
    assert recovery.reusable_step_ids == ("fetch",)
    assert recovery.reusable_invocation_keys == ("drill-fetch-1",)
    assert recovery.version_mismatch_step_ids == ()

    # 依赖版本变化时拒绝错误复用
    mismatched = restarted.recover_interrupted_task(
        "drill-crash",
        {"index_generation": "gen-2"},
        {"fetch": "drill-fetch-1", "analyze": "drill-analyze-1"},
    )
    assert mismatched.reusable_step_ids == ()
    assert mismatched.version_mismatch_step_ids == ("fetch",)

    # 崩溃 Worker 租约过期后新 attempt 接管；重复执行同一有副作用调用被调用账本唯一约束阻止
    takeover = restarted.claim_dag_step("drill-crash", "fetch", "worker-b", now=2000)
    with __import__("pytest").raises(sqlite3.IntegrityError):
        restarted.commit_dag_step(
            "drill-crash", "fetch", takeover.attempt.attempt_token, "worker-b", snapshot.revision,
            plan, {"index_generation": "gen-1"},
            {"idempotency_key": "drill-fetch-1", "status": "succeeded"}, now=2001,
        )
    assert [item.step_id for item in store.checkpoints("research:drill-crash")] == ["fetch"]

    # 恢复执行剩余步骤后整条链路完整
    analyze_claim = restarted.claim_dag_step("drill-crash", "analyze", "worker-b", now=2002)
    done = restarted.commit_dag_step(
        "drill-crash", "analyze", analyze_claim.attempt.attempt_token, "worker-b", snapshot.revision,
        plan, {"index_generation": "gen-1"},
        {"idempotency_key": "drill-analyze-1", "status": "succeeded"}, now=2003,
    )
    assert done.status == "completed"
    resumed = restarted.recover_interrupted_task(
        "drill-crash",
        {"index_generation": "gen-1"},
        {"fetch": "drill-fetch-1", "analyze": "drill-analyze-1"},
    )
    assert resumed.reusable_step_ids == ("analyze", "fetch")


def test_drill_concurrent_control_commands_cas_and_idempotent_replay(tmp_path: Path):
    store, orchestrator, _db_path = _harness(tmp_path)
    adapter = orchestrator.task_adapter

    started = orchestrator.start_planned_task(
        "drill-concurrent", _StubPlan(("plan",)), command_id="cmd-start", actor="tester"
    )

    # 两个控制命令基于同一 revision 竞争：串行化后只有一个 CAS 成功
    paused = adapter.pause_task("drill-concurrent", started.revision, "cmd-pause", actor="user-a")
    import pytest

    with pytest.raises(store.RevisionConflictError) as conflict:
        adapter.cancel_task("drill-concurrent", started.revision, "cmd-cancel", actor="user-b")
    assert conflict.value.current_revision == paused.revision

    # 胜出命令在状态未变前重放保持幂等，不追加新事件
    replayed = adapter.pause_task("drill-concurrent", started.revision, "cmd-pause", actor="user-a")
    assert replayed == paused

    # 竞争失败方用当前 revision 携同一 command_id 重试后成功
    cancelled = adapter.cancel_task("drill-concurrent", paused.revision, "cmd-cancel", actor="user-b")
    assert cancelled.status == "cancelled"

    # 全程只产生一条 run_created 与三条状态迁移事件，重放没有重复写入
    assert [event.event_type for event in store.events("research:drill-concurrent")] == [
        "run_created", "run_transitioned", "run_transitioned", "run_transitioned"
    ]
    assert store.run("research:drill-concurrent").revision == cancelled.revision


def test_drill_timeout_late_result_isolated_and_new_attempt_takes_over(tmp_path: Path):
    store, orchestrator, _db_path = _harness(tmp_path)
    plan = _StubPlan(("retrieve",))

    started = orchestrator.start_planned_task("drill-timeout", plan, command_id="cmd-start", actor="tester")
    claim = orchestrator.claim_dag_step("drill-timeout", "retrieve", "worker-a", now=1000)

    # 线程池等待超时：只记录 timed_out，不误判为底层调用已取消
    orchestrator.mark_dag_step_timeout(claim.attempt.attempt_token, "worker-a")
    assert store.attempt_status(claim.attempt.attempt_id) == "timed_out"

    # 晚到结果被隔离丢弃，不能写检查点、调用账本或改变 revision
    late = orchestrator.commit_dag_step(
        "drill-timeout", "retrieve", claim.attempt.attempt_token, "worker-a", started.revision,
        plan, {"index_generation": "gen-1"},
        {"idempotency_key": "drill-retrieve-1", "status": "succeeded"}, now=1005,
    )
    assert late.status == "discarded"
    assert [item.step_id for item in store.checkpoints("research:drill-timeout")] == []
    import pytest

    with pytest.raises(KeyError):
        store.invocation("drill-retrieve-1")
    assert store.run("research:drill-timeout").revision == started.revision

    # 新 attempt 接管后正常提交，原 attempt 保持 timed_out
    takeover = orchestrator.claim_dag_step("drill-timeout", "retrieve", "worker-b", now=1010)
    done = orchestrator.commit_dag_step(
        "drill-timeout", "retrieve", takeover.attempt.attempt_token, "worker-b", started.revision,
        plan, {"index_generation": "gen-1"},
        {"idempotency_key": "drill-retrieve-2", "status": "succeeded"}, now=1011,
    )
    assert done.status == "completed"
    assert store.attempt_status(claim.attempt.attempt_id) == "timed_out"
    assert store.invocation("drill-retrieve-2").status == "succeeded"


def test_drill_disconnect_reconnect_replays_from_cursor_and_flags_resync(tmp_path: Path):
    from src.research_task_events import ResearchTaskEventStream

    store, orchestrator, _db_path = _harness(tmp_path)
    adapter = orchestrator.task_adapter
    stream = ResearchTaskEventStream(store)

    started = orchestrator.start_planned_task(
        "drill-reconnect", _StubPlan(("plan",)), command_id="cmd-start", actor="tester"
    )
    adapter.pause_task("drill-reconnect", started.revision, "cmd-pause-1", actor="tester")
    adapter.resume_task("drill-reconnect", started.revision + 1, "cmd-resume-1", actor="tester")

    # 统一事件时间戳到演练时钟附近，保证保留期窗口判定确定性
    with store.metadata_store.connect() as connection:
        connection.execute(
            "UPDATE v7_task_events SET created_at='2030-01-01 00:00:00' WHERE run_id=?",
            ("research:drill-reconnect",),
        )
        connection.commit()

    # 首次连接读取全量事件并记住游标
    first_page = stream.read(
        "drill-reconnect", after_event_id=None, now="2030-01-01 00:00:30", retention_seconds=3600
    )
    cursor = first_page.next_event_id
    assert cursor is not None

    # 断线期间产生新事件（真实时间戳同样需要归一化到演练时钟）
    adapter.pause_task("drill-reconnect", started.revision + 2, "cmd-pause-2", actor="tester")
    adapter.resume_task("drill-reconnect", started.revision + 3, "cmd-resume-2", actor="tester")
    with store.metadata_store.connect() as connection:
        connection.execute(
            "UPDATE v7_task_events SET created_at='2030-01-01 00:00:00' WHERE run_id=?",
            ("research:drill-reconnect",),
        )
        connection.commit()

    # 重连：携带游标只补发新事件，不重复推送
    reconnect = stream.read(
        "drill-reconnect", after_event_id=cursor, now="2030-01-01 00:00:30", retention_seconds=3600
    )
    assert [event.event_type for event in reconnect.events] == ["run_transitioned", "run_transitioned"]
    assert [event.payload["status"] for event in reconnect.events] == ["paused", "running"]
    assert all(event.event_id > cursor for event in reconnect.events)
    assert reconnect.resync_required is False
    assert reconnect.next_event_id == reconnect.events[-1].event_id

    # 游标早于保留窗口：明确要求重同步而不是静默续接
    with store.metadata_store.connect() as connection:
        connection.execute(
            "UPDATE v7_task_events SET created_at='2029-12-31 21:00:00' WHERE run_id=? AND event_id<?",
            ("research:drill-reconnect", reconnect.next_event_id),
        )
        connection.commit()

    stale = stream.read(
        "drill-reconnect", after_event_id=1, now="2030-01-01 00:00:30", retention_seconds=3600
    )
    assert stale.resync_required is True
    assert stale.events == ()
    assert stale.oldest_event_id == reconnect.next_event_id
