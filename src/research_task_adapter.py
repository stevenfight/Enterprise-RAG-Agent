"""C1 研究任务到 C0 可恢复执行内核的非侵入式适配。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from src.durable_execution import AttemptClaim, DurableExecutionStore, RunSnapshot


class RoutePathConflictError(RuntimeError):
    """同一研究任务的执行路径冲突：选定路径只追加，不允许静默改道。"""


@dataclass(frozen=True)
class ResearchTaskSnapshot:
    """研究任务的只读视图，状态与 revision 均来自 C0 运行。"""

    task_id: str
    run_id: str
    status: str
    revision: int
    dag_step_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchStepClaim:
    """DAG 步骤领取结果，底层租约仍由 C0 持久化。"""

    task_id: str
    run_id: str
    step_id: str
    attempt: AttemptClaim


@dataclass(frozen=True)
class ResearchTaskMemoryLink:
    """研究任务与既有会话记忆的运行时关联，不持久化或改写记忆。"""

    task_id: str
    memory: Any

    def get_full_context(self, conversation_history: str = "") -> str:
        """复用原 AgentMemory 的上下文生成语义。"""
        return self.memory.get_full_context(conversation_history)


@dataclass(frozen=True)
class ResearchRecoveryDecision:
    """研究任务恢复时允许复用的步骤与成功调用。"""

    task_id: str
    reusable_step_ids: tuple[str, ...]
    reusable_invocation_keys: tuple[str, ...]
    version_mismatch_step_ids: tuple[str, ...]


@dataclass(frozen=True)
class ResearchFailureDecision:
    """研究任务失败分类与下一步动作。"""

    category: str
    action: str
    retry_count: int
    max_retries: int


@dataclass(frozen=True)
class RouteDecision:
    """路由决策的只追加记录视图，来自 v7_task_route_decisions 表。"""

    decision_id: int
    decision_type: str
    selected_path: str | None
    detail: dict[str, Any]
    actor: str


class ResearchTaskAdapter:
    """将 task_id 与 DAG 节点映射为既有 C0 的 run_id 与 step_id。"""

    _RUN_PREFIX = "research:"
    _RETRYABLE_FAILURE_CODES = frozenset({"network_timeout", "provider_unavailable", "rate_limited"})
    _VALID_ROUTE_PATHS = frozenset({"single", "multi"})
    _RETRY_SUFFIX_PATTERN = re.compile(r"^(?P<base>.+)-retry-(?P<number>\d+)$")

    def __init__(self, execution_store: DurableExecutionStore) -> None:
        self.execution_store = execution_store

    def create_task(self, task_id: str, dag_step_ids: Iterable[str]) -> ResearchTaskSnapshot:
        """创建 C0 run；DAG 定义由调用方保存到后续 C1 检查点。"""
        normalized_task_id = self._task_id(task_id)
        normalized_steps = self._dag_steps(dag_step_ids)
        run = self.execution_store.create_run(self.run_id_for(normalized_task_id))
        return self._snapshot(normalized_task_id, run, normalized_steps)

    def start_task(self, task_id: str, expected_revision: int, command_id: str, *, actor: str) -> ResearchTaskSnapshot:
        """复用 C0 的 CAS 状态迁移启动研究任务。"""
        normalized_task_id = self._task_id(task_id)
        run = self.execution_store.transition(
            self.run_id_for(normalized_task_id), "running", expected_revision, command_id, actor=actor
        )
        return self._snapshot(normalized_task_id, run)

    def wait_for_approval(self, task_id: str, expected_revision: int, command_id: str, *, actor: str) -> ResearchTaskSnapshot:
        """将运行中研究任务迁移为 C0 waiting_approval。"""
        return self._transition_task(task_id, "waiting_approval", expected_revision, command_id, actor)

    def pause_task(self, task_id: str, expected_revision: int, command_id: str, *, actor: str) -> ResearchTaskSnapshot:
        """将运行中研究任务暂停，保留 C0 CAS 语义。"""
        return self._transition_task(task_id, "paused", expected_revision, command_id, actor)

    def pause_for_budget(self, task_id: str, step_id: str, attempt_token: str, owner_token: str, expected_revision: int, command_id: str, *, dag_step_ids: Iterable[str], dependency_versions: dict[str, str], budget: dict[str, float], actor: str, now: float) -> ResearchTaskSnapshot:
        """硬预算超限时原子保存研究检查点并暂停。"""
        normalized_task_id = self._task_id(task_id)
        checkpoint = self.build_checkpoint(normalized_task_id, dag_step_ids, dependency_versions=dependency_versions)
        checkpoint["budget"] = budget
        run = self.execution_store.pause_with_checkpoint(self.run_id_for(normalized_task_id), self._step_id(step_id), attempt_token, owner_token, expected_revision, command_id, checkpoint=checkpoint, actor=actor, now=now)
        return self._snapshot(normalized_task_id, run)

    def resume_task(self, task_id: str, expected_revision: int, command_id: str, *, actor: str) -> ResearchTaskSnapshot:
        """从暂停或等待审批恢复为 C0 running。"""
        return self._transition_task(task_id, "running", expected_revision, command_id, actor)

    def cancel_task(self, task_id: str, expected_revision: int, command_id: str, *, actor: str) -> ResearchTaskSnapshot:
        """取消研究任务，C0 会轮换 cancellation token 并拒绝晚到结果。"""
        return self._transition_task(task_id, "cancelled", expected_revision, command_id, actor)

    def fail_task(self, task_id: str, expected_revision: int, command_id: str, *, actor: str) -> ResearchTaskSnapshot:
        """将不可恢复的研究任务迁移为 C0 failed。"""
        return self._transition_task(task_id, "failed", expected_revision, command_id, actor)

    def complete_task(self, task_id: str, expected_revision: int, command_id: str, *, actor: str) -> ResearchTaskSnapshot:
        """仅在全部研究步骤已提交后将 C0 任务迁移为 completed。"""
        return self._transition_task(task_id, "completed", expected_revision, command_id, actor)

    def task_snapshot(self, task_id: str) -> ResearchTaskSnapshot:
        """读取 C0 run 的当前状态，不复制任务状态。"""
        normalized_task_id = self._task_id(task_id)
        return self._snapshot(normalized_task_id, self.execution_store.run(self.run_id_for(normalized_task_id)))

    def list_tasks(self) -> tuple[ResearchTaskSnapshot, ...]:
        """只读取 research 前缀运行，避免将其他 C0 业务运行暴露为研究任务。"""
        return tuple(
            self._snapshot(run.run_id.removeprefix(self._RUN_PREFIX), run)
            for run in self.execution_store.runs_with_prefix(self._RUN_PREFIX)
        )

    def record_route_selection(self, task_id: str, *, selected_path: str, reason: str, actor: str) -> RouteDecision:
        """持久记录 single/multi 路径选定；同路径幂等返回，异路径拒绝改道。"""
        normalized_task_id = self._task_id(task_id)
        normalized_path = self._selected_path(selected_path)
        existing = self._latest_selected_decision(normalized_task_id)
        if existing is not None:
            if existing.selected_path == normalized_path:
                # 相同路径重复选择幂等返回，不新增只追加记录
                return existing
            raise RoutePathConflictError(
                f"任务 {normalized_task_id} 已选定路径 {existing.selected_path}，拒绝改道为 {normalized_path}"
            )
        return self._insert_decision(
            normalized_task_id, "selected", selected_path=normalized_path, detail={"reason": reason}, actor=actor
        )

    def route_selection(self, task_id: str) -> str:
        """读取任务最近一次选定的执行路径；未记录时抛 ValueError。"""
        normalized_task_id = self._task_id(task_id)
        existing = self._latest_selected_decision(normalized_task_id)
        if existing is None or existing.selected_path is None:
            raise ValueError(f"任务 {normalized_task_id} 未记录选定执行路径")
        return existing.selected_path

    def route_decisions(self, task_id: str) -> tuple[RouteDecision, ...]:
        """按 decision_id 顺序返回任务全部路由决策，只追加不覆盖。"""
        normalized_task_id = self._task_id(task_id)
        rows = self._fetch_decisions(normalized_task_id)
        return tuple(self._decision_from_row(row) for row in rows)

    def record_failure(
        self,
        task_id: str,
        failure: ResearchFailureDecision,
        *,
        actor: str,
        reason: str | None = None,
    ) -> RouteDecision:
        """持久记录失败分类与下一步动作；选定路径保持不变，不静默回退。"""
        normalized_task_id = self._task_id(task_id)
        detail = {
            "category": failure.category,
            "action": failure.action,
            "retry_count": failure.retry_count,
            "max_retries": failure.max_retries,
        }
        if isinstance(reason, str) and reason.strip():
            detail["reason"] = reason.strip()
        return self._insert_decision(normalized_task_id, "failure", selected_path=None, detail=detail, actor=actor)

    def retry_task(
        self,
        task_id: str,
        *,
        requested_path: str,
        dag_step_ids: Iterable[str],
        command_id: str,
        actor: str,
    ) -> ResearchTaskSnapshot:
        """显式重试 failed 任务：新建 C0 run，继承选定路径，禁止静默改道。"""
        normalized_task_id = self._task_id(task_id)
        normalized_path = self._selected_path(requested_path)
        selected_path = self.route_selection(normalized_task_id)
        if normalized_path != selected_path:
            raise RoutePathConflictError(
                f"任务 {normalized_task_id} 已选定路径 {selected_path}，重试拒绝改道为 {normalized_path}"
            )
        current = self.execution_store.run(self.run_id_for(normalized_task_id))
        if current.status != "failed":
            raise ValueError(f"任务 {normalized_task_id} 当前状态为 {current.status}，仅 failed 任务可重试")

        new_task_id = self._next_retry_task_id(normalized_task_id)
        # failed 为终态，重试必须落在全新 run 上，不回迁原 run 状态
        snapshot = self.create_task(new_task_id, dag_step_ids)
        selector = self._latest_selected_decision(normalized_task_id)
        self.record_route_selection(
            new_task_id,
            selected_path=selected_path,
            reason=f"重试继承自任务 {normalized_task_id}",
            actor=selector.actor if selector is not None else actor,
        )
        self._insert_decision(
            normalized_task_id,
            "retry",
            selected_path=selected_path,
            detail={"new_task_id": new_task_id, "command_id": command_id},
            actor=actor,
        )
        return snapshot

    def claim_step(
        self,
        task_id: str,
        step_id: str,
        owner_token: str,
        *,
        now: float | None = None,
        ttl_seconds: float = 30,
    ) -> ResearchStepClaim:
        """以 DAG 节点 ID 直接领取 C0 step lease。"""
        normalized_task_id = self._task_id(task_id)
        normalized_step_id = self._step_id(step_id)
        run_id = self.run_id_for(normalized_task_id)
        attempt = self.execution_store.acquire_lease(
            run_id, normalized_step_id, owner_token, now=now, ttl_seconds=ttl_seconds
        )
        return ResearchStepClaim(normalized_task_id, run_id, normalized_step_id, attempt)

    def memory_link(self, task_id: str, _memory: Any) -> dict[str, str]:
        """仅提供 task_id 关联信息，不读取、替换或持久化 AgentMemory。"""
        return {"task_id": self._task_id(task_id)}

    def link_task_memory(self, task_id: str, memory: Any) -> ResearchTaskMemoryLink:
        """把研究任务关联到既有会话记忆实例，不改变其读写逻辑。"""
        return ResearchTaskMemoryLink(task_id=self._task_id(task_id), memory=memory)

    def build_checkpoint(
        self,
        task_id: str,
        dag_step_ids: Iterable[str],
        *,
        dependency_versions: dict[str, str],
        artifact_ids: Iterable[str] = (),
        fact_ids: Iterable[str] = (),
    ) -> dict[str, Any]:
        """构造可写入 C0 checkpoint 的稳定研究任务载荷。"""
        payload = {
            "schema_version": 1,
            "task_id": self._task_id(task_id),
            "run_id": self.run_id_for(task_id),
            "dag_step_ids": list(self._dag_steps(dag_step_ids)),
            "dependency_versions": dict(dependency_versions),
            "artifact_ids": [self._stable_id(value, "artifact") for value in artifact_ids],
            "fact_ids": [self._stable_id(value, "fact") for value in fact_ids],
        }
        try:
            return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        except (TypeError, ValueError) as exc:
            raise ValueError("研究检查点必须 JSON 可序列化") from exc

    def commit_step(self, task_id: str, step_id: str, attempt_token: str, owner_token: str, expected_revision: int, *, dag_step_ids: Iterable[str], dependency_versions: dict[str, str], invocation: dict[str, Any], artifact_ids: Iterable[str] = (), fact_ids: Iterable[str] = (), on_commit: Any | None = None, completion_command_id: str | None = None, completion_actor: str | None = None, now: float | None = None):
        """将研究步骤结果和版本化 checkpoint 委托给 C0 同一事务提交。"""
        normalized_task_id = self._task_id(task_id)
        checkpoint = self.build_checkpoint(normalized_task_id, dag_step_ids, dependency_versions=dependency_versions, artifact_ids=artifact_ids, fact_ids=fact_ids)
        return self.execution_store.commit_step(self.run_id_for(normalized_task_id), self._step_id(step_id), attempt_token, owner_token, expected_revision, checkpoint=checkpoint, invocation=invocation, on_commit=on_commit, completion_command_id=completion_command_id, completion_actor=completion_actor, now=now)

    def dispose_legacy_running_task(
        self,
        task_id: str,
        expected_revision: int,
        command_id: str,
        *,
        actor: str,
        reason: str,
    ) -> ResearchTaskSnapshot:
        """仅处置没有任何执行证据的遗留运行任务，禁止删除或重置。"""
        normalized_task_id = self._task_id(task_id)
        normalized_reason = reason.strip() if isinstance(reason, str) else ""
        if not normalized_reason:
            raise ValueError("遗留任务处置必须提供原因")
        run_id = self.run_id_for(normalized_task_id)
        with self.execution_store.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                command = connection.execute(
                    "SELECT result_status, result_revision FROM v7_execution_commands WHERE command_id=?",
                    (command_id,),
                ).fetchone()
                row = connection.execute(
                    "SELECT status, revision, cancellation_token FROM v7_execution_runs WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if row is None:
                    raise KeyError(run_id)
                if command is not None:
                    if row[0] != command[0] or row[1] < command[1]:
                        raise RuntimeError("重复命令的持久结果与运行状态不一致")
                    connection.rollback()
                    return self._snapshot(normalized_task_id, self.execution_store.run(run_id))
                if row[0] != "running":
                    raise ValueError(f"任务 {normalized_task_id} 当前状态为 {row[0]}，不能按遗留任务处置")
                if row[1] != expected_revision:
                    raise self.execution_store.RevisionConflictError(row[1])
                evidence = connection.execute(
                    "SELECT "
                    "(SELECT COUNT(*) FROM v7_step_attempts WHERE run_id=?) + "
                    "(SELECT COUNT(*) FROM v7_leases WHERE run_id=?) + "
                    "(SELECT COUNT(*) FROM v7_execution_checkpoints WHERE run_id=?) + "
                    "(SELECT COUNT(*) FROM v7_execution_invocations WHERE run_id=?)",
                    (run_id, run_id, run_id, run_id),
                ).fetchone()[0]
                if evidence:
                    raise ValueError("任务存在执行租约、步骤、检查点或调用记录，不能按遗留任务处置")
                next_revision = expected_revision + 1
                connection.execute(
                    "UPDATE v7_execution_runs SET status='failed', revision=?, updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND revision=?",
                    (next_revision, run_id, expected_revision),
                )
                connection.execute(
                    "INSERT INTO v7_execution_commands(command_id, run_id, target_status, expected_revision, result_revision, result_status, actor) VALUES (?, ?, 'failed', ?, ?, 'failed', ?)",
                    (command_id, run_id, expected_revision, next_revision, actor),
                )
                self.execution_store._append_event(
                    connection,
                    run_id,
                    next_revision,
                    "run_transitioned",
                    {"actor": actor, "status": "failed"},
                )
                failure = self.failure_decision("legacy_execution_unavailable", retry_count=0, max_retries=0)
                detail_json = json.dumps(
                    {
                        "category": failure.category,
                        "action": failure.action,
                        "retry_count": failure.retry_count,
                        "max_retries": failure.max_retries,
                        "reason": normalized_reason,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                connection.execute(
                    "INSERT INTO v7_task_route_decisions(task_id, run_id, decision_type, selected_path, detail_json, actor) VALUES (?, ?, 'failure', NULL, ?, ?)",
                    (normalized_task_id, run_id, detail_json, actor),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._snapshot(normalized_task_id, self.execution_store.run(run_id))

    def recovery_decision(
        self,
        task_id: str,
        dependency_versions: dict[str, str],
        step_invocation_keys: dict[str, str],
    ) -> ResearchRecoveryDecision:
        """仅复用依赖版本与当前幂等键均匹配的已完成步骤和成功调用。"""
        normalized_task_id = self._task_id(task_id)
        expected_versions = dict(dependency_versions)
        expected_keys = {
            self._step_id(step_id): self._stable_id(key, "调用幂等键")
            for step_id, key in step_invocation_keys.items()
        }
        recovery = self.execution_store.recovery_plan(self.run_id_for(normalized_task_id))
        latest_checkpoints = {}
        for checkpoint in recovery.checkpoint_records:
            latest_checkpoints[checkpoint.step_id] = checkpoint

        reusable_steps = []
        reusable_keys = []
        version_mismatches = []
        for step_id in sorted(expected_keys):
            checkpoint = latest_checkpoints.get(step_id)
            if checkpoint is None:
                continue
            if checkpoint.payload.get("dependency_versions") != expected_versions:
                version_mismatches.append(step_id)
                continue
            invocation_key = expected_keys[step_id]
            if recovery.reusable_invocation(invocation_key) is None:
                continue
            reusable_steps.append(step_id)
            reusable_keys.append(invocation_key)

        return ResearchRecoveryDecision(
            task_id=normalized_task_id,
            reusable_step_ids=tuple(reusable_steps),
            reusable_invocation_keys=tuple(reusable_keys),
            version_mismatch_step_ids=tuple(version_mismatches),
        )

    def failure_decision(
        self,
        failure_code: str,
        *,
        retry_count: int,
        max_retries: int,
    ) -> ResearchFailureDecision:
        """对已知失败分类；未知失败不重试，避免静默扩大执行。"""
        normalized_code = self._stable_id(failure_code, "失败代码")
        if retry_count < 0 or max_retries < 0:
            raise ValueError("重试次数不能为负数")
        if normalized_code == "approval_required":
            return ResearchFailureDecision("approval_required", "waiting_approval", retry_count, max_retries)
        if normalized_code in self._RETRYABLE_FAILURE_CODES:
            if retry_count < max_retries:
                return ResearchFailureDecision("retryable", "retry", retry_count, max_retries)
            return ResearchFailureDecision("retry_exhausted", "failed", retry_count, max_retries)
        return ResearchFailureDecision("terminal", "failed", retry_count, max_retries)

    def mark_step_timeout(self, attempt_token: str, owner_token: str) -> None:
        """记录等待超时；底层调用是否停止仍由 C0 的晚到结果门禁处理。"""
        self.execution_store.mark_attempt_timeout(attempt_token, owner_token)

    def _insert_decision(
        self,
        task_id: str,
        decision_type: str,
        *,
        selected_path: str | None,
        detail: dict[str, Any],
        actor: str,
    ) -> RouteDecision:
        """向只追加路由决策表写入一条记录，禁止更新或删除历史。"""
        detail_json = json.dumps(detail, ensure_ascii=False, sort_keys=True)
        with self.execution_store.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    "INSERT INTO v7_task_route_decisions(task_id, run_id, decision_type, selected_path, detail_json, actor) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (task_id, self.run_id_for(task_id), decision_type, selected_path, detail_json, actor),
                )
                decision_id = cursor.lastrowid
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return RouteDecision(decision_id, decision_type, selected_path, detail, actor)

    def _fetch_decisions(self, task_id: str) -> list[tuple[Any, ...]]:
        """读取指定任务的全部路由决策行，按 decision_id 升序。"""
        with self.execution_store.metadata_store.connect() as connection:
            return connection.execute(
                "SELECT decision_id, decision_type, selected_path, detail_json, actor "
                "FROM v7_task_route_decisions WHERE task_id = ? ORDER BY decision_id",
                (task_id,),
            ).fetchall()

    def _latest_selected_decision(self, task_id: str) -> RouteDecision | None:
        """读取任务最近一次 selected 决策；不存在时返回 None。"""
        with self.execution_store.metadata_store.connect() as connection:
            row = connection.execute(
                "SELECT decision_id, decision_type, selected_path, detail_json, actor "
                "FROM v7_task_route_decisions WHERE task_id = ? AND decision_type = 'selected' "
                "ORDER BY decision_id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        return self._decision_from_row(row) if row is not None else None

    def _next_retry_task_id(self, task_id: str) -> str:
        """按原始基线推导下一个重试任务 ID，重试链沿 base-retry-N 继续编号。"""
        suffix_match = self._RETRY_SUFFIX_PATTERN.fullmatch(task_id)
        base = suffix_match.group("base") if suffix_match else task_id
        with self.execution_store.metadata_store.connect() as connection:
            rows = connection.execute(
                "SELECT detail_json FROM v7_task_route_decisions WHERE decision_type = 'retry' "
                "AND (task_id = ? OR task_id LIKE ?)",
                (base, base + "-retry-%"),
            ).fetchall()
        highest = 0
        base_pattern = re.compile(re.escape(base) + r"-retry-(\d+)$")
        for (detail_json,) in rows:
            new_task_id = json.loads(detail_json).get("new_task_id", "")
            number_match = base_pattern.fullmatch(new_task_id)
            if number_match is not None:
                highest = max(highest, int(number_match.group(1)))
        return f"{base}-retry-{highest + 1}"

    @classmethod
    def _selected_path(cls, selected_path: str) -> str:
        """校验执行路径取值，仅允许 single 或 multi。"""
        if selected_path not in cls._VALID_ROUTE_PATHS:
            raise ValueError(f"未知执行路径 {selected_path!r}，仅支持 single 或 multi")
        return selected_path

    @staticmethod
    def _decision_from_row(row: tuple[Any, ...]) -> RouteDecision:
        """将路由决策表行转换为只读 RouteDecision 视图。"""
        return RouteDecision(row[0], row[1], row[2], json.loads(row[3]), row[4])

    def _transition_task(self, task_id: str, target_status: str, expected_revision: int, command_id: str, actor: str) -> ResearchTaskSnapshot:
        normalized_task_id = self._task_id(task_id)
        run = self.execution_store.transition(
            self.run_id_for(normalized_task_id), target_status, expected_revision, command_id, actor=actor
        )
        return self._snapshot(normalized_task_id, run)

    @classmethod
    def run_id_for(cls, task_id: str) -> str:
        """构造稳定 C0 run ID，避免与其他 C0 工作负载冲突。"""
        return f"{cls._RUN_PREFIX}{cls._task_id(task_id)}"

    @staticmethod
    def _task_id(task_id: str) -> str:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id 不能为空")
        return task_id.strip()

    @staticmethod
    def _step_id(step_id: str) -> str:
        if not isinstance(step_id, str) or not step_id.strip():
            raise ValueError("DAG 步骤 ID 不能为空")
        return step_id.strip()

    @staticmethod
    def _stable_id(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} ID 不能为空")
        return value.strip()

    @classmethod
    def _dag_steps(cls, dag_step_ids: Iterable[str]) -> tuple[str, ...]:
        steps = tuple(cls._step_id(step_id) for step_id in dag_step_ids)
        if not steps or len(set(steps)) != len(steps):
            raise ValueError("DAG 步骤必须非空且不重复")
        return steps

    @staticmethod
    def _snapshot(task_id: str, run: RunSnapshot, dag_step_ids: tuple[str, ...] = ()) -> ResearchTaskSnapshot:
        return ResearchTaskSnapshot(task_id, run.run_id, run.status, run.revision, dag_step_ids)
