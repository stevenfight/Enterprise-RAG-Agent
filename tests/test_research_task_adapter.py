"""C1.1 研究任务到 C0 执行内核的映射测试。"""

from pathlib import Path


def _adapter(tmp_path: Path):
    from src.durable_execution import DurableExecutionStore
    from src.research_task_adapter import ResearchTaskAdapter
    from src.v7_metadata_store import V7MetadataStore

    store = DurableExecutionStore(V7MetadataStore(tmp_path / "v7_metadata.sqlite3"))
    return ResearchTaskAdapter(store), store


def test_task_id_and_dag_step_reuse_c0_run_and_step_without_new_tables(tmp_path: Path):
    adapter, store = _adapter(tmp_path)
    tables_before = store.table_names()

    task = adapter.create_task("research-001", ["plan", "retrieve"])
    started = adapter.start_task("research-001", task.revision, "cmd-start", actor="tester")
    claim = adapter.claim_step("research-001", "retrieve", "worker-a", now=1000)

    assert task.run_id == "research:research-001"
    assert started.status == "running"
    assert claim.step_id == "retrieve"
    assert store.run(task.run_id).status == "running"
    assert store.table_names() == tables_before


def test_task_snapshot_and_memory_link_are_nonintrusive(tmp_path: Path):
    adapter, _store = _adapter(tmp_path)
    task = adapter.create_task("research-002", ["plan"])

    snapshot = adapter.task_snapshot("research-002")
    memory_link = adapter.memory_link("research-002", object())

    assert snapshot.task_id == "research-002"
    assert snapshot.status == "pending"
    assert memory_link == {"task_id": "research-002"}
    assert task.dag_step_ids == ("plan",)


def test_task_rejects_empty_or_duplicate_dag_steps(tmp_path: Path):
    adapter, _store = _adapter(tmp_path)

    import pytest

    with pytest.raises(ValueError, match="task_id"):
        adapter.create_task("", ["plan"])
    with pytest.raises(ValueError, match="DAG"):
        adapter.create_task("research-003", ["plan", "plan"])


def test_task_commands_reuse_c0_wait_pause_resume_cancel_cas(tmp_path: Path):
    import pytest

    adapter, store = _adapter(tmp_path)
    created = adapter.create_task("research-004", ["plan"])
    running = adapter.start_task("research-004", created.revision, "cmd-start", actor="tester")
    waiting = adapter.wait_for_approval("research-004", running.revision, "cmd-wait", actor="tester")
    resumed = adapter.resume_task("research-004", waiting.revision, "cmd-resume", actor="tester")
    paused = adapter.pause_task("research-004", resumed.revision, "cmd-pause", actor="tester")
    cancelled = adapter.cancel_task("research-004", paused.revision, "cmd-cancel", actor="tester")

    assert [waiting.status, resumed.status, paused.status, cancelled.status] == [
        "waiting_approval", "running", "paused", "cancelled"
    ]
    assert adapter.cancel_task("research-004", paused.revision, "cmd-cancel", actor="tester") == cancelled
    with pytest.raises(store.RevisionConflictError):
        adapter.resume_task("research-004", paused.revision, "cmd-stale-resume", actor="tester")


def test_research_checkpoint_is_versioned_json_and_contains_only_stable_references(tmp_path: Path):
    import pytest

    adapter, _store = _adapter(tmp_path)
    checkpoint = adapter.build_checkpoint(
        "research-005", ["plan", "retrieve"],
        dependency_versions={"index_generation": "gen-1", "fact_version": "facts-2"},
        artifact_ids=["artifact-1"], fact_ids=["fact-1"],
    )

    assert checkpoint["schema_version"] == 1
    assert checkpoint["task_id"] == "research-005"
    assert checkpoint["dag_step_ids"] == ["plan", "retrieve"]
    assert checkpoint["artifact_ids"] == ["artifact-1"]
    with pytest.raises(ValueError, match="JSON"):
        adapter.build_checkpoint("research-005", ["plan"], dependency_versions={"bad": object()})


def test_research_step_commit_persists_versioned_checkpoint_via_c0_transaction(tmp_path: Path):
    adapter, store = _adapter(tmp_path)
    created = adapter.create_task("research-006", ["plan"])
    running = adapter.start_task("research-006", created.revision, "cmd-start", actor="tester")
    claim = adapter.claim_step("research-006", "plan", "worker-a", now=1000)

    result = adapter.commit_step(
        "research-006", "plan", claim.attempt.attempt_token, "worker-a", running.revision,
        dag_step_ids=["plan"], dependency_versions={"index_generation": "gen-1"},
        invocation={"idempotency_key": "research-plan-1", "status": "succeeded"}, now=1001,
    )

    assert result.status == "completed"
    assert store.checkpoints("research:research-006")[0].payload["task_id"] == "research-006"


def test_research_task_memory_session_link_reuses_existing_memory_without_mutation(tmp_path: Path):
    from src.agent_memory import AgentMemory

    adapter, _store = _adapter(tmp_path)
    memory = AgentMemory(working_memory_limit=3)
    memory.add("保留原有步骤", "retrieve", {"query": "营收"}, "已找到", 1)

    link = adapter.link_task_memory("research-007", memory)

    assert link.task_id == "research-007"
    assert link.memory is memory
    assert link.get_full_context("用户问：营收") == memory.get_full_context("用户问：营收")
    assert len(memory.working_memory) == 1


def test_recovery_reuses_only_completed_steps_and_calls_with_matching_dependency_versions(tmp_path: Path):
    adapter, _store = _adapter(tmp_path)
    created = adapter.create_task("research-008", ["plan"])
    running = adapter.start_task("research-008", created.revision, "cmd-start", actor="tester")
    claim = adapter.claim_step("research-008", "plan", "worker-a", now=1000)
    adapter.commit_step(
        "research-008", "plan", claim.attempt.attempt_token, "worker-a", running.revision,
        dag_step_ids=["plan"], dependency_versions={"index_generation": "gen-1"},
        invocation={"idempotency_key": "research-plan-gen-1", "status": "succeeded"}, now=1001,
    )

    reusable = adapter.recovery_decision(
        "research-008", {"index_generation": "gen-1"}, {"plan": "research-plan-gen-1"}
    )
    changed = adapter.recovery_decision(
        "research-008", {"index_generation": "gen-2"}, {"plan": "research-plan-gen-1"}
    )

    assert reusable.reusable_step_ids == ("plan",)
    assert reusable.reusable_invocation_keys == ("research-plan-gen-1",)
    assert changed.reusable_step_ids == ()
    assert changed.reusable_invocation_keys == ()
    assert changed.version_mismatch_step_ids == ("plan",)


def test_failure_policy_bounds_retries_and_timeout_does_not_claim_work_stopped(tmp_path: Path):
    adapter, store = _adapter(tmp_path)
    retry = adapter.failure_decision("provider_unavailable", retry_count=0, max_retries=2)
    exhausted = adapter.failure_decision("provider_unavailable", retry_count=2, max_retries=2)
    approval = adapter.failure_decision("approval_required", retry_count=0, max_retries=2)
    terminal = adapter.failure_decision("invalid_input", retry_count=0, max_retries=2)

    assert (retry.category, retry.action) == ("retryable", "retry")
    assert (exhausted.category, exhausted.action) == ("retry_exhausted", "failed")
    assert (approval.category, approval.action) == ("approval_required", "waiting_approval")
    assert (terminal.category, terminal.action) == ("terminal", "failed")

    created = adapter.create_task("research-009", ["plan"])
    running = adapter.start_task("research-009", created.revision, "cmd-start", actor="tester")
    claim = adapter.claim_step("research-009", "plan", "worker-a", now=1000)
    adapter.mark_step_timeout(claim.attempt.attempt_token, "worker-a")
    failed = adapter.fail_task("research-009", running.revision, "cmd-failed", actor="tester")

    assert store.attempt_status(claim.attempt.attempt_id) == "timed_out"
    assert store.run("research:research-009").status == "failed"
    assert failed.status == "failed"


def test_research_orchestrator_persists_planner_and_dag_boundaries_in_c0(tmp_path: Path):
    from src.planner import TaskPlanner
    from src.research_task_orchestrator import ResearchTaskOrchestrator

    adapter, store = _adapter(tmp_path)
    plan = TaskPlanner().plan("中国移动2024年营收")
    orchestrator = ResearchTaskOrchestrator(adapter)

    started = orchestrator.start_planned_task("research-010", plan, command_id="cmd-plan", actor="tester")
    first_step_id = plan.subtasks[0].task_id
    claim = orchestrator.claim_dag_step("research-010", first_step_id, "worker-a", now=1000)
    completed = orchestrator.commit_dag_step(
        "research-010", first_step_id, claim.attempt.attempt_token, "worker-a", started.revision,
        plan, {"index_generation": "gen-1"},
        {"idempotency_key": "research-010-first", "status": "succeeded"}, now=1001,
    )
    second_step_id = plan.subtasks[1].task_id
    timed_out = orchestrator.claim_dag_step("research-010", second_step_id, "worker-a", now=1002)
    orchestrator.mark_dag_step_timeout(timed_out.attempt.attempt_token, "worker-a")

    assert started.status == "running"
    assert started.dag_step_ids == tuple(item.task_id for item in plan.subtasks)
    assert completed.status == "completed"
    assert store.attempt_status(timed_out.attempt.attempt_id) == "timed_out"
    assert [event.event_type for event in store.events("research:research-010")] == [
        "run_created", "run_transitioned", "lease_acquired", "step_completed", "lease_acquired", "attempt_timed_out"
    ]
    assert store.run("research:research-010").status == "running"


def test_task_event_stream_returns_resync_when_cursor_precedes_retained_events(tmp_path: Path):
    from src.research_task_events import ResearchTaskEventStream

    adapter, store = _adapter(tmp_path)
    created = adapter.create_task("research-011", ["plan"])
    adapter.start_task("research-011", created.revision, "cmd-start", actor="tester")
    events = store.events("research:research-011")
    with store.metadata_store.connect() as connection:
        connection.execute(
            "UPDATE v7_task_events SET created_at='2020-01-01 00:00:00' WHERE event_id=?",
            (events[0].event_id,),
        )
        connection.execute(
            "UPDATE v7_task_events SET created_at='2030-01-01 00:00:00' WHERE event_id=?",
            (events[1].event_id,),
        )
        connection.commit()

    stream = ResearchTaskEventStream(store)
    stale = stream.read(
        "research-011", after_event_id=0, now="2030-01-01 00:00:30", retention_seconds=60
    )
    initial = stream.read(
        "research-011", after_event_id=None, now="2030-01-01 00:00:30", retention_seconds=60
    )

    assert stale.resync_required is True
    assert stale.oldest_event_id == events[1].event_id
    assert stale.events == ()
    assert initial.resync_required is False
    assert tuple(event.event_id for event in initial.events) == (events[1].event_id,)
