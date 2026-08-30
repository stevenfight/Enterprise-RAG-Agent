"""C2.3 研究任务的 Planner 与 DAG 持久化编排边界。"""

from __future__ import annotations

from typing import Any

from src.research_task_adapter import (
    ResearchRecoveryDecision,
    ResearchStepClaim,
    ResearchTaskAdapter,
    ResearchTaskSnapshot,
)


class ResearchTaskOrchestrator:
    """把既有 TaskPlan 的生命周期委托给 C0 研究任务适配层。"""

    def __init__(self, task_adapter: ResearchTaskAdapter) -> None:
        self.task_adapter = task_adapter

    def start_planned_task(
        self,
        task_id: str,
        plan: Any,
        *,
        command_id: str,
        actor: str,
    ) -> ResearchTaskSnapshot:
        """在 Planner 产出后创建并启动持久研究任务。"""
        dag_step_ids = self._dag_step_ids(plan)
        created = self.task_adapter.create_task(task_id, dag_step_ids)
        started = self.task_adapter.start_task(task_id, created.revision, command_id, actor=actor)
        return ResearchTaskSnapshot(
            started.task_id,
            started.run_id,
            started.status,
            started.revision,
            dag_step_ids,
        )

    def claim_dag_step(
        self,
        task_id: str,
        step_id: str,
        owner_token: str,
        *,
        now: float | None = None,
        ttl_seconds: float = 30,
    ) -> ResearchStepClaim:
        """在 DAG 步骤开始时领取 C0 租约。"""
        return self.task_adapter.claim_step(
            task_id, step_id, owner_token, now=now, ttl_seconds=ttl_seconds
        )

    def commit_dag_step(
        self,
        task_id: str,
        step_id: str,
        attempt_token: str,
        owner_token: str,
        expected_revision: int,
        plan: Any,
        dependency_versions: dict[str, str],
        invocation: dict[str, Any],
        *,
        artifact_ids: tuple[str, ...] = (),
        fact_ids: tuple[str, ...] = (),
        now: float | None = None,
    ) -> Any:
        """在 DAG 步骤完成时同事务写入 C0 检查点、调用账本和事件。"""
        return self.task_adapter.commit_step(
            task_id,
            step_id,
            attempt_token,
            owner_token,
            expected_revision,
            dag_step_ids=self._dag_step_ids(plan),
            dependency_versions=dependency_versions,
            invocation=invocation,
            artifact_ids=artifact_ids,
            fact_ids=fact_ids,
            now=now,
        )

    def mark_dag_step_timeout(self, attempt_token: str, owner_token: str) -> None:
        """记录等待超时，不把底层调用误判为已经停止。"""
        self.task_adapter.mark_step_timeout(attempt_token, owner_token)

    def handle_step_failure(
        self,
        task_id: str,
        failure_code: str,
        *,
        retry_count: int,
        max_retries: int,
        expected_revision: int,
        command_id: str,
        actor: str,
    ) -> ResearchTaskSnapshot:
        """Worker 异常时分类失败、持久记录，并按动作迁移任务状态。

        retry 动作不迁移状态（等待重新领取步骤）；failed 动作迁移为终态；
        waiting_approval 动作迁移为等待审批。失败记录只追加，不覆盖历史。
        """
        decision = self.task_adapter.failure_decision(
            failure_code, retry_count=retry_count, max_retries=max_retries
        )
        self.task_adapter.record_failure(task_id, decision, actor=actor)
        if decision.action == "failed":
            return self.task_adapter.fail_task(task_id, expected_revision, command_id, actor=actor)
        if decision.action == "waiting_approval":
            return self.task_adapter.wait_for_approval(task_id, expected_revision, command_id, actor=actor)
        return self.task_adapter.task_snapshot(task_id)

    def recover_interrupted_task(
        self,
        task_id: str,
        dependency_versions: dict[str, str],
        step_invocation_keys: dict[str, str],
    ) -> ResearchRecoveryDecision:
        """进程中断后按依赖版本与幂等键推导可复用步骤与成功调用。"""
        return self.task_adapter.recovery_decision(task_id, dependency_versions, step_invocation_keys)

    @staticmethod
    def _dag_step_ids(plan: Any) -> tuple[str, ...]:
        """从既有 Planner 输出提取稳定 DAG 步骤 ID。"""
        return tuple(item.task_id for item in plan.subtasks)
