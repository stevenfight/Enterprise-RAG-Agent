# -*- coding: utf-8 -*-
"""C0 可恢复执行的 SQLite 仓储。

本模块只提供通用运行状态、租约和恢复账本；C1 的 API 与 M 的业务步骤都通过
此边界接入，避免各自维护第二套任务状态机。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from src.v7_metadata_store import V7MetadataStore


class RevisionConflictError(RuntimeError):
    """调用方基于过期 revision 修改运行状态。"""

    def __init__(self, current_revision: int) -> None:
        super().__init__(f"运行状态已更新，当前 revision={current_revision}")
        self.current_revision = current_revision


class LeaseUnavailableError(RuntimeError):
    """同一运行步骤仍由有效租约持有。"""


class InvalidRunTransitionError(ValueError):
    """运行状态迁移不符合批准状态图。"""


@dataclass(frozen=True)
class RunSnapshot:
    run_id: str
    status: str
    revision: int
    cancellation_token: str


@dataclass(frozen=True)
class AttemptClaim:
    attempt_id: str
    attempt_token: str
    owner_token: str


@dataclass(frozen=True)
class CommitResult:
    status: str


@dataclass(frozen=True)
class EventRecord:
    event_id: int
    event_type: str
    revision: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class EventWindow:
    """按持久事件 ID 读取的窗口，以及客户端是否需要重同步。"""

    events: tuple[EventRecord, ...]
    oldest_event_id: int | None
    next_event_id: int | None
    resync_required: bool


@dataclass(frozen=True)
class CheckpointRecord:
    step_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class InvocationRecord:
    idempotency_key: str
    status: str
    details: dict[str, Any]


@dataclass(frozen=True)
class RecoveryPlan:
    checkpoint_records: tuple[CheckpointRecord, ...]
    invocation_records: tuple[InvocationRecord, ...]

    def latest_checkpoint(self, step_id: str) -> CheckpointRecord | None:
        return next((item for item in reversed(self.checkpoint_records) if item.step_id == step_id), None)

    def reusable_invocation(self, idempotency_key: str) -> InvocationRecord | None:
        return next(
            (item for item in self.invocation_records if item.idempotency_key == idempotency_key and item.status == "succeeded"),
            None,
        )


class DurableExecutionStore:
    """以 V7MetadataStore 为唯一持久化边界的 C0 执行仓储。"""

    C0_TABLES = (
        "v7_execution_runs",
        "v7_step_attempts",
        "v7_leases",
        "v7_execution_checkpoints",
        "v7_execution_invocations",
        "v7_task_events",
        "v7_execution_commands",
    )
    LeaseUnavailableError = LeaseUnavailableError
    RevisionConflictError = RevisionConflictError
    InvalidRunTransitionError = InvalidRunTransitionError
    _ALLOWED_TRANSITIONS = {
        "pending": {"running", "cancelled"},
        "running": {"waiting_approval", "paused", "completed", "failed", "cancelled"},
        "waiting_approval": {"running", "cancelled"},
        "paused": {"running", "cancelled"},
        "completed": set(),
        "failed": set(),
        "cancelled": set(),
    }

    def __init__(self, metadata_store: V7MetadataStore) -> None:
        self.metadata_store = metadata_store
        self.metadata_store.initialize()

    def create_run(self, run_id: str) -> RunSnapshot:
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cancellation_token = uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO v7_execution_runs(run_id, status, revision, cancellation_token) VALUES (?, 'pending', 0, ?)",
                    (run_id, cancellation_token),
                )
                self._append_event(connection, run_id, 0, "run_created", {})
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return RunSnapshot(run_id, "pending", 0, cancellation_token)

    def run(self, run_id: str) -> RunSnapshot:
        with self.metadata_store.connect() as connection:
            row = connection.execute(
                "SELECT run_id, status, revision, cancellation_token FROM v7_execution_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return RunSnapshot(*row)

    def runs_with_prefix(self, prefix: str) -> tuple[RunSnapshot, ...]:
        """按运行 ID 前缀读取快照，供业务适配层隔离各自的 C0 运行视图。"""
        if not isinstance(prefix, str) or not prefix:
            raise ValueError("prefix 不能为空")
        with self.metadata_store.connect() as connection:
            rows = connection.execute(
                "SELECT run_id, status, revision, cancellation_token FROM v7_execution_runs "
                "WHERE run_id LIKE ? ORDER BY run_id ASC",
                (f"{prefix}%",),
            ).fetchall()
        return tuple(RunSnapshot(*row) for row in rows)

    def transition(self, run_id: str, target_status: str, expected_revision: int, command_id: str, *, actor: str) -> RunSnapshot:
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                command = connection.execute(
                    "SELECT result_status, result_revision FROM v7_execution_commands WHERE command_id = ?", (command_id,)
                ).fetchone()
                if command is not None:
                    snapshot = self.run(run_id)
                    if snapshot.status != command[0] or snapshot.revision < command[1]:
                        raise RuntimeError("重复命令的持久结果与运行状态不一致")
                    connection.rollback()
                    return RunSnapshot(run_id, command[0], command[1], snapshot.cancellation_token)

                row = connection.execute(
                    "SELECT status, revision, cancellation_token FROM v7_execution_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if row is None:
                    raise KeyError(run_id)
                current_status, current_revision, cancellation_token = row
                if current_revision != expected_revision:
                    raise RevisionConflictError(current_revision)
                if target_status not in self._ALLOWED_TRANSITIONS[current_status]:
                    raise InvalidRunTransitionError(f"不允许 {current_status} → {target_status}")
                next_revision = current_revision + 1
                next_cancellation_token = (
                    uuid.uuid4().hex if target_status == "cancelled" else cancellation_token
                )
                connection.execute(
                    "UPDATE v7_execution_runs SET status=?, revision=?, cancellation_token=?, updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND revision=?",
                    (target_status, next_revision, next_cancellation_token, run_id, current_revision),
                )
                connection.execute(
                    "INSERT INTO v7_execution_commands(command_id, run_id, target_status, expected_revision, result_revision, result_status, actor) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (command_id, run_id, target_status, expected_revision, next_revision, target_status, actor),
                )
                self._append_event(connection, run_id, next_revision, "run_transitioned", {"actor": actor, "status": target_status})
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return RunSnapshot(run_id, target_status, next_revision, next_cancellation_token)

    def pause_with_checkpoint(self, run_id: str, step_id: str, attempt_token: str, owner_token: str, expected_revision: int, command_id: str, *, checkpoint: Mapping[str, Any], actor: str, now: float) -> RunSnapshot:
        """在同一事务保存检查点、释放租约并将运行暂停。"""
        payload = self._json_object(checkpoint)
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                run = connection.execute("SELECT status, revision, cancellation_token FROM v7_execution_runs WHERE run_id=?", (run_id,)).fetchone()
                attempt = connection.execute("SELECT attempt_id FROM v7_step_attempts WHERE attempt_token=? AND run_id=? AND step_id=? AND owner_token=?", (attempt_token, run_id, step_id, owner_token)).fetchone()
                lease = connection.execute("SELECT attempt_id, expires_at FROM v7_leases WHERE run_id=? AND step_id=? AND owner_token=?", (run_id, step_id, owner_token)).fetchone()
                if run is None:
                    raise KeyError(run_id)
                if run[1] != expected_revision:
                    raise RevisionConflictError(run[1])
                if run[0] != "running" or attempt is None or lease is None or lease[0] != attempt[0] or lease[1] <= now:
                    raise InvalidRunTransitionError("仅有效运行中步骤可以因预算暂停")
                next_revision = expected_revision + 1
                connection.execute("INSERT INTO v7_execution_checkpoints(checkpoint_id, run_id, step_id, attempt_id, schema_version, payload_json) VALUES (?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, run_id, step_id, attempt[0], int(payload.get("schema_version", 1)), json.dumps(payload, sort_keys=True)))
                connection.execute("UPDATE v7_step_attempts SET status='paused' WHERE attempt_id=?", (attempt[0],))
                connection.execute("DELETE FROM v7_leases WHERE run_id=? AND step_id=?", (run_id, step_id))
                connection.execute("UPDATE v7_execution_runs SET status='paused', revision=?, updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND revision=?", (next_revision, run_id, expected_revision))
                connection.execute("INSERT INTO v7_execution_commands(command_id, run_id, target_status, expected_revision, result_revision, result_status, actor) VALUES (?, ?, 'paused', ?, ?, 'paused', ?)", (command_id, run_id, expected_revision, next_revision, actor))
                self._append_event(connection, run_id, next_revision, "budget_exceeded", {"actor": actor, "step_id": step_id})
                self._append_event(connection, run_id, next_revision, "run_transitioned", {"actor": actor, "status": "paused"})
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return RunSnapshot(run_id, "paused", next_revision, run[2])

    def acquire_lease(self, run_id: str, step_id: str, owner_token: str, *, now: float | None = None, ttl_seconds: float = 30) -> AttemptClaim:
        now = time.time() if now is None else now
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = connection.execute(
                    "SELECT attempt_id, expires_at FROM v7_leases WHERE run_id=? AND step_id=?", (run_id, step_id)
                ).fetchone()
                if current is not None and current[1] > now:
                    raise LeaseUnavailableError(f"步骤 {step_id} 仍有有效租约")
                if current is not None:
                    connection.execute("UPDATE v7_step_attempts SET status='superseded' WHERE attempt_id=?", (current[0],))
                    connection.execute("DELETE FROM v7_leases WHERE run_id=? AND step_id=?", (run_id, step_id))
                attempt_id, attempt_token = uuid.uuid4().hex, uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO v7_step_attempts(attempt_id, run_id, step_id, attempt_token, owner_token, status) VALUES (?, ?, ?, ?, ?, 'running')",
                    (attempt_id, run_id, step_id, attempt_token, owner_token),
                )
                connection.execute(
                    "INSERT INTO v7_leases(run_id, step_id, attempt_id, owner_token, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (run_id, step_id, attempt_id, owner_token, now + ttl_seconds),
                )
                revision = self._revision(connection, run_id)
                self._append_event(connection, run_id, revision, "lease_acquired", {"step_id": step_id, "attempt_id": attempt_id})
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return AttemptClaim(attempt_id, attempt_token, owner_token)

    def attempt_status(self, attempt_id: str) -> str:
        with self.metadata_store.connect() as connection:
            row = connection.execute("SELECT status FROM v7_step_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return row[0]

    def renew_lease(
        self,
        attempt_token: str,
        owner_token: str,
        *,
        now: float | None = None,
        ttl_seconds: float = 30,
    ) -> None:
        """仅允许当前租约持有者在未过期前续租。"""
        now = time.time() if now is None else now
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT leases.run_id, leases.step_id, leases.expires_at
                    FROM v7_leases AS leases
                    JOIN v7_step_attempts AS attempts
                      ON attempts.attempt_id = leases.attempt_id
                    WHERE attempts.attempt_token=? AND leases.owner_token=?
                    """,
                    (attempt_token, owner_token),
                ).fetchone()
                if row is None or row[2] <= now:
                    raise LeaseUnavailableError("租约已失效，不能续租")
                connection.execute(
                    "UPDATE v7_leases SET expires_at=? WHERE run_id=? AND step_id=?",
                    (now + ttl_seconds, row[0], row[1]),
                )
                self._append_event(connection, row[0], self._revision(connection, row[0]), "lease_renewed", {"step_id": row[1]})
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def mark_attempt_timeout(self, attempt_token: str, owner_token: str) -> None:
        """记录等待超时；不把底层线程或远端调用误写为已取消。"""
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT attempt_id, run_id, step_id FROM v7_step_attempts WHERE attempt_token=? AND owner_token=?",
                    (attempt_token, owner_token),
                ).fetchone()
                if row is None:
                    raise KeyError(attempt_token)
                connection.execute("UPDATE v7_step_attempts SET status='timed_out' WHERE attempt_id=?", (row[0],))
                connection.execute("DELETE FROM v7_leases WHERE run_id=? AND step_id=? AND attempt_id=?", (row[1], row[2], row[0]))
                self._append_event(connection, row[1], self._revision(connection, row[1]), "attempt_timed_out", {"step_id": row[2], "attempt_id": row[0]})
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def commit_step(
        self,
        run_id: str,
        step_id: str,
        attempt_token: str,
        owner_token: str,
        expected_revision: int,
        *,
        checkpoint: Mapping[str, Any],
        invocation: Mapping[str, Any],
        on_commit: Callable[[sqlite3.Connection], None] | None = None,
        completion_command_id: str | None = None,
        completion_actor: str | None = None,
        now: float | None = None,
    ) -> CommitResult:
        now = time.time() if now is None else now
        payload = self._json_object(checkpoint)
        invocation_payload = self._json_object(invocation)
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                run = connection.execute("SELECT status, revision FROM v7_execution_runs WHERE run_id=?", (run_id,)).fetchone()
                attempt = connection.execute("SELECT attempt_id FROM v7_step_attempts WHERE attempt_token=? AND run_id=? AND step_id=? AND owner_token=?", (attempt_token, run_id, step_id, owner_token)).fetchone()
                lease = connection.execute("SELECT attempt_id, expires_at FROM v7_leases WHERE run_id=? AND step_id=? AND owner_token=?", (run_id, step_id, owner_token)).fetchone()
                valid = run is not None and run[0] == "running" and run[1] == expected_revision and attempt is not None and lease is not None and lease[0] == attempt[0] and lease[1] > now
                if not valid:
                    revision = run[1] if run is not None else -1
                    self._append_event(connection, run_id, revision, "late_result_discarded", {"step_id": step_id, "attempt_token": attempt_token})
                    connection.commit()
                    return CommitResult("discarded")
                key = str(invocation_payload["idempotency_key"])
                status = str(invocation_payload.get("status", "succeeded"))
                connection.execute(
                    "INSERT INTO v7_execution_invocations(idempotency_key, run_id, step_id, attempt_id, status, details_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (key, run_id, step_id, attempt[0], status, json.dumps(invocation_payload, sort_keys=True)),
                )
                connection.execute(
                    "INSERT INTO v7_execution_checkpoints(checkpoint_id, run_id, step_id, attempt_id, schema_version, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (uuid.uuid4().hex, run_id, step_id, attempt[0], int(payload.get("schema_version", 1)), json.dumps(payload, sort_keys=True)),
                )
                if on_commit is not None:
                    on_commit(connection)
                connection.execute("UPDATE v7_step_attempts SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE attempt_id=?", (attempt[0],))
                connection.execute("DELETE FROM v7_leases WHERE run_id=? AND step_id=?", (run_id, step_id))
                self._append_event(connection, run_id, expected_revision, "step_completed", {"step_id": step_id, "idempotency_key": key})
                if completion_command_id is not None:
                    if not isinstance(completion_actor, str) or not completion_actor.strip():
                        raise ValueError("完成任务必须提供执行者")
                    next_revision = expected_revision + 1
                    update_cursor = connection.execute(
                        "UPDATE v7_execution_runs SET status='completed', revision=?, updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND revision=?",
                        (next_revision, run_id, expected_revision),
                    )
                    if update_cursor.rowcount != 1:
                        raise RevisionConflictError(expected_revision)
                    connection.execute(
                        "INSERT INTO v7_execution_commands(command_id, run_id, target_status, expected_revision, result_revision, result_status, actor) VALUES (?, ?, 'completed', ?, ?, 'completed', ?)",
                        (completion_command_id, run_id, expected_revision, next_revision, completion_actor),
                    )
                    self._append_event(connection, run_id, next_revision, "run_transitioned", {"actor": completion_actor, "status": "completed"})
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return CommitResult("completed")

    def events(self, run_id: str) -> list[EventRecord]:
        with self.metadata_store.connect() as connection:
            rows = connection.execute("SELECT event_id, event_type, revision, payload_json FROM v7_task_events WHERE run_id=? ORDER BY event_id", (run_id,)).fetchall()
        return [EventRecord(row[0], row[1], row[2], json.loads(row[3])) for row in rows]

    def event_window(
        self,
        run_id: str,
        after_event_id: int | None,
        *,
        now: str,
        retention_seconds: int,
    ) -> EventWindow:
        """裁剪过期事件并读取窗口；过旧游标明确要求客户端重同步。"""
        if retention_seconds <= 0:
            raise ValueError("事件保留期限必须为正数")
        if after_event_id is not None and after_event_id < 0:
            raise ValueError("事件游标不能为负数")
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "DELETE FROM v7_task_events WHERE run_id=? AND julianday(created_at) < julianday(?) - ? / 86400.0",
                    (run_id, now, retention_seconds),
                )
                oldest_row = connection.execute(
                    "SELECT MIN(event_id) FROM v7_task_events WHERE run_id=?", (run_id,)
                ).fetchone()
                oldest_event_id = oldest_row[0] if oldest_row is not None else None
                resync_required = (
                    after_event_id is not None
                    and oldest_event_id is not None
                    and after_event_id < oldest_event_id - 1
                )
                if resync_required:
                    rows = []
                elif after_event_id is None:
                    rows = connection.execute(
                        "SELECT event_id, event_type, revision, payload_json FROM v7_task_events WHERE run_id=? ORDER BY event_id",
                        (run_id,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT event_id, event_type, revision, payload_json FROM v7_task_events WHERE run_id=? AND event_id>? ORDER BY event_id",
                        (run_id, after_event_id),
                    ).fetchall()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        events = tuple(EventRecord(row[0], row[1], row[2], json.loads(row[3])) for row in rows)
        next_event_id = events[-1].event_id if events else after_event_id
        return EventWindow(events, oldest_event_id, next_event_id, resync_required)

    def checkpoints(self, run_id: str) -> list[CheckpointRecord]:
        with self.metadata_store.connect() as connection:
            rows = connection.execute("SELECT step_id, payload_json FROM v7_execution_checkpoints WHERE run_id=? ORDER BY created_at, checkpoint_id", (run_id,)).fetchall()
        return [CheckpointRecord(row[0], json.loads(row[1])) for row in rows]

    def invocation(self, idempotency_key: str) -> InvocationRecord:
        with self.metadata_store.connect() as connection:
            row = connection.execute("SELECT idempotency_key, status, details_json FROM v7_execution_invocations WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if row is None:
            raise KeyError(idempotency_key)
        return InvocationRecord(row[0], row[1], json.loads(row[2]))

    def recovery_plan(self, run_id: str) -> RecoveryPlan:
        with self.metadata_store.connect() as connection:
            checkpoints = connection.execute("SELECT step_id, payload_json FROM v7_execution_checkpoints WHERE run_id=? ORDER BY created_at, checkpoint_id", (run_id,)).fetchall()
            invocations = connection.execute("SELECT idempotency_key, status, details_json FROM v7_execution_invocations WHERE run_id=? ORDER BY created_at", (run_id,)).fetchall()
        return RecoveryPlan(tuple(CheckpointRecord(row[0], json.loads(row[1])) for row in checkpoints), tuple(InvocationRecord(row[0], row[1], json.loads(row[2])) for row in invocations))

    def table_names(self) -> set[str]:
        with self.metadata_store.connect() as connection:
            rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {row[0] for row in rows}

    @staticmethod
    def idempotency_key(*, run_id: str, step_id: str, tool_name: str, normalized_input: Mapping[str, Any], code_version: str, model_provider: str, model_name: str, prompt_version: str, fact_version: str, artifact_version: str, index_generation: str) -> str:
        payload = {"run_id": run_id, "step_id": step_id, "tool_name": tool_name, "normalized_input": normalized_input, "code_version": code_version, "model_provider": model_provider, "model_name": model_name, "prompt_version": prompt_version, "fact_version": fact_version, "artifact_version": artifact_version, "index_generation": index_generation}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()

    @staticmethod
    def _json_object(value: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError("检查点和调用账本必须是 JSON 对象")
        try:
            encoded = json.dumps(value, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("检查点和调用账本必须 JSON 可序列化") from exc
        return json.loads(encoded)

    @staticmethod
    def _append_event(connection: Any, run_id: str, revision: int, event_type: str, payload: Mapping[str, Any]) -> None:
        connection.execute("INSERT INTO v7_task_events(run_id, revision, event_type, payload_json) VALUES (?, ?, ?, ?)", (run_id, revision, event_type, json.dumps(dict(payload), sort_keys=True)))

    @staticmethod
    def _revision(connection: Any, run_id: str) -> int:
        row = connection.execute("SELECT revision FROM v7_execution_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return int(row[0])
