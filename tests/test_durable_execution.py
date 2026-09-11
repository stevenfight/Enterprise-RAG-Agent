"""C0 可恢复执行基础的租约、原子提交与恢复测试。"""

from __future__ import annotations

from pathlib import Path

import pytest


def _store(tmp_path: Path):
    from src.durable_execution import DurableExecutionStore
    from src.v7_metadata_store import V7MetadataStore

    return DurableExecutionStore(V7MetadataStore(tmp_path / "v7_metadata.sqlite3"))


def _running_store(tmp_path: Path):
    store = _store(tmp_path)
    created = store.create_run("run-1")
    store.transition("run-1", "running", created.revision, "cmd-start", actor="system")
    return store


def test_same_step_has_only_one_active_lease_holder(tmp_path: Path):
    store = _running_store(tmp_path)

    first = store.acquire_lease("run-1", "parse", "worker-a", now=1000, ttl_seconds=30)
    with pytest.raises(store.LeaseUnavailableError):
        store.acquire_lease("run-1", "parse", "worker-b", now=1001, ttl_seconds=30)

    assert first.owner_token == "worker-a"


def test_expired_lease_can_be_taken_over_and_old_attempt_is_not_active(tmp_path: Path):
    store = _running_store(tmp_path)
    first = store.acquire_lease("run-1", "parse", "worker-a", now=1000, ttl_seconds=10)

    second = store.acquire_lease("run-1", "parse", "worker-b", now=1011, ttl_seconds=10)

    assert second.attempt_id != first.attempt_id
    assert store.attempt_status(first.attempt_id) == "superseded"


def test_lease_renewal_keeps_current_attempt_exclusive(tmp_path: Path):
    store = _running_store(tmp_path)
    attempt = store.acquire_lease("run-1", "parse", "worker-a", now=1000, ttl_seconds=10)

    store.renew_lease(attempt.attempt_token, "worker-a", now=1005, ttl_seconds=10)

    with pytest.raises(store.LeaseUnavailableError):
        store.acquire_lease("run-1", "parse", "worker-b", now=1011, ttl_seconds=10)


def test_abandon_lease_releases_current_attempt_and_keeps_audit_event(tmp_path: Path):
    store = _running_store(tmp_path)
    attempt = store.acquire_lease("run-1", "parse", "worker-a", now=1000, ttl_seconds=10)

    store.abandon_lease(attempt.attempt_token, "worker-a", reason="计算失败")

    assert store.attempt_status(attempt.attempt_id) == "abandoned"
    replacement = store.acquire_lease("run-1", "parse", "worker-b", now=1001, ttl_seconds=10)
    assert replacement.owner_token == "worker-b"
    assert store.events("run-1")[-2].event_type == "step_abandoned"


def test_late_result_from_superseded_attempt_is_discarded_without_checkpoint(tmp_path: Path):
    store = _running_store(tmp_path)
    first = store.acquire_lease("run-1", "parse", "worker-a", now=1000, ttl_seconds=10)
    store.acquire_lease("run-1", "parse", "worker-b", now=1011, ttl_seconds=10)

    result = store.commit_step(
        "run-1",
        "parse",
        first.attempt_token,
        "worker-a",
        expected_revision=1,
        checkpoint={"page": 1},
        invocation={"idempotency_key": "parse-v1", "status": "succeeded"},
        now=1011,
    )

    assert result.status == "discarded"
    assert store.checkpoints("run-1") == []
    assert store.events("run-1")[-1].event_type == "late_result_discarded"


def test_status_transition_uses_revision_cas_and_replays_same_command(tmp_path: Path):
    store = _store(tmp_path)
    created = store.create_run("run-1")
    running = store.transition("run-1", "running", created.revision, "cmd-start", actor="system")
    paused = store.transition("run-1", "paused", running.revision, "cmd-pause", actor="u1")
    replayed = store.transition("run-1", "paused", running.revision, "cmd-pause", actor="u1")

    assert paused == replayed
    with pytest.raises(store.RevisionConflictError) as exc_info:
        store.transition("run-1", "cancelled", running.revision, "cmd-cancel", actor="u2")
    assert exc_info.value.current_revision == paused.revision


def test_events_have_monotonic_ids_and_atomic_step_commit(tmp_path: Path):
    store = _running_store(tmp_path)
    attempt = store.acquire_lease("run-1", "parse", "worker-a", now=1000, ttl_seconds=30)

    result = store.commit_step(
        "run-1",
        "parse",
        attempt.attempt_token,
        "worker-a",
        expected_revision=1,
        checkpoint={"page": 2, "schema_version": 1},
        invocation={"idempotency_key": "parse-v1", "status": "succeeded"},
        now=1001,
    )

    event_ids = [event.event_id for event in store.events("run-1")]
    assert result.status == "completed"
    assert event_ids == sorted(event_ids)
    assert len(event_ids) == len(set(event_ids))
    assert store.checkpoints("run-1")[0].payload == {"page": 2, "schema_version": 1}
    assert store.invocation("parse-v1").status == "succeeded"


def test_idempotency_key_includes_all_versioned_dependencies(tmp_path: Path):
    store = _store(tmp_path)
    base = dict(
        run_id="run-1",
        step_id="parse",
        tool_name="mineru",
        normalized_input={"pages": [1, 2]},
        code_version="c1",
        model_provider="provider-a",
        model_name="model-a",
        prompt_version="p1",
        fact_version="facts-1",
        artifact_version="assets-1",
        index_generation="index-1",
    )

    stable = store.idempotency_key(**base)
    assert stable == store.idempotency_key(**base)
    assert stable != store.idempotency_key(**(base | {"prompt_version": "p2"}))
    assert stable != store.idempotency_key(**(base | {"index_generation": "index-2"}))


def test_cancellation_blocks_late_completion_and_records_discarded(tmp_path: Path):
    store = _store(tmp_path)
    created = store.create_run("run-1")
    running = store.transition("run-1", "running", created.revision, "cmd-start", actor="system")
    attempt = store.acquire_lease("run-1", "parse", "worker-a", now=1000, ttl_seconds=30)
    cancelled = store.transition("run-1", "cancelled", running.revision, "cmd-cancel", actor="u1")

    result = store.commit_step(
        "run-1", "parse", attempt.attempt_token, "worker-a", cancelled.revision,
        checkpoint={"page": 1}, invocation={"idempotency_key": "parse-v1", "status": "succeeded"}, now=1001,
    )

    assert result.status == "discarded"
    assert store.run("run-1").status == "cancelled"
    assert store.checkpoints("run-1") == []


def test_cancellation_rotates_run_token_before_late_results_can_commit(tmp_path: Path):
    store = _store(tmp_path)
    created = store.create_run("run-1")
    running = store.transition("run-1", "running", created.revision, "cmd-start", actor="system")

    cancelled = store.transition("run-1", "cancelled", running.revision, "cmd-cancel", actor="u1")

    assert cancelled.cancellation_token != created.cancellation_token


def test_timeout_marks_attempt_without_claiming_that_underlying_work_was_cancelled(tmp_path: Path):
    store = _running_store(tmp_path)
    attempt = store.acquire_lease("run-1", "parse", "worker-a", now=1000, ttl_seconds=30)

    store.mark_attempt_timeout(attempt.attempt_token, "worker-a")
    result = store.commit_step(
        "run-1", "parse", attempt.attempt_token, "worker-a", 1,
        checkpoint={"page": 1}, invocation={"idempotency_key": "parse-v1", "status": "succeeded"}, now=1001,
    )

    assert store.run("run-1").status == "running"
    assert store.attempt_status(attempt.attempt_id) == "timed_out"
    assert result.status == "discarded"
    assert store.events("run-1")[-1].event_type == "late_result_discarded"


def test_resume_uses_checkpoint_and_reuses_only_matching_successful_invocation(tmp_path: Path):
    store = _running_store(tmp_path)
    attempt = store.acquire_lease("run-1", "parse", "worker-a", now=1000, ttl_seconds=30)
    store.commit_step(
        "run-1", "parse", attempt.attempt_token, "worker-a", 1,
        checkpoint={"page": 3}, invocation={"idempotency_key": "parse-v1", "status": "succeeded"}, now=1001,
    )

    recovery = store.recovery_plan("run-1")
    assert recovery.latest_checkpoint("parse").payload == {"page": 3}
    assert recovery.reusable_invocation("parse-v1") is not None
    assert recovery.reusable_invocation("different-key") is None


def test_c0_tables_are_migrated_by_shared_v7_metadata_store(tmp_path: Path):
    store = _store(tmp_path)

    assert store.metadata_store.schema_version() >= 11
    assert set(store.C0_TABLES).issubset(store.table_names())


def test_multimodal_coordinator_reuses_same_c0_execution_store(tmp_path: Path):
    from src.v7_document_processing_coordinator import V7DocumentProcessingCoordinator

    execution_store = _running_store(tmp_path)

    class Repository:
        store = execution_store.metadata_store

    coordinator = V7DocumentProcessingCoordinator(
        manifest_repository=Repository(),
        parse_batch_repository=Repository(),
        page_image_renderer=object(),
        page_artifact_repository=Repository(),
        durable_execution_store=execution_store,
    )

    attempt = coordinator.claim_processing_attempt("run-1", "doc-v1", "worker-a", now=1000)
    assert attempt.owner_token == "worker-a"
    assert coordinator.execution_store is execution_store
