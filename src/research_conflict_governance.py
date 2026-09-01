# -*- coding: utf-8 -*-
"""E-T16 冲突裁决的可信服务端上下文与审批授予边界。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime

from src.durable_execution import DurableExecutionStore
from src.financial_fact_conflict_repository import FinancialFactConflictRepository
from src.governance.approval import (
    ApprovalBinding,
    ApprovalRecord,
    ApprovalRequest,
    GovernanceApprovalStore,
    SUBJECT_CONFLICT_RESOLUTION,
)
from src.research_conflict_review import ConflictReviewAction
from src.research_delivery import ResearchPlan
from src.research_plan_repository import ResearchPlanRepository
from src.research_task_adapter import ResearchTaskAdapter
from src.v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class ResearchConflictContext:
    """由可信后端工作流登记的冲突依赖版本，不接受浏览器提供。"""

    task_id: str
    run_id: str
    conflict_id: str
    fact_version: str
    artifact_version: str
    index_generation: str
    context_version: int = 0

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        run_id: str,
        conflict_id: str,
        fact_version: str,
        artifact_version: str,
        index_generation: str,
    ) -> "ResearchConflictContext":
        values = {
            "task_id": task_id,
            "run_id": run_id,
            "conflict_id": conflict_id,
            "fact_version": fact_version,
            "artifact_version": artifact_version,
            "index_generation": index_generation,
        }
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ValueError("冲突上下文字段不能为空")
        return cls(**values)

    def with_versions(
        self, *, fact_version: str, artifact_version: str, index_generation: str
    ) -> "ResearchConflictContext":
        """创建新的待追加上下文，不覆盖历史版本。"""
        return self.create(
            task_id=self.task_id,
            run_id=self.run_id,
            conflict_id=self.conflict_id,
            fact_version=fact_version,
            artifact_version=artifact_version,
            index_generation=index_generation,
        )


class ResearchConflictContextRepository:
    """冲突上下文只追加仓储，当前值按 context_version 读取。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self._store = store
        self._store.initialize()

    def append(self, context: ResearchConflictContext) -> ResearchConflictContext:
        if not isinstance(context, ResearchConflictContext):
            raise ValueError("context 必须是 ResearchConflictContext")
        with self._store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT COALESCE(MAX(context_version), 0)
                    FROM v7_research_conflict_contexts
                    WHERE task_id=? AND conflict_id=?
                    """,
                    (context.task_id, context.conflict_id),
                ).fetchone()
                stored = replace(context, context_version=int(row[0]) + 1)
                connection.execute(
                    """
                    INSERT INTO v7_research_conflict_contexts (
                        task_id, conflict_id, context_version, run_id, fact_version,
                        artifact_version, index_generation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stored.task_id,
                        stored.conflict_id,
                        stored.context_version,
                        stored.run_id,
                        stored.fact_version,
                        stored.artifact_version,
                        stored.index_generation,
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return stored

    def history(self, task_id: str, conflict_id: str) -> tuple[ResearchConflictContext, ...]:
        with self._store.connect() as connection:
            rows = connection.execute(
                """
                SELECT task_id, run_id, conflict_id, fact_version, artifact_version,
                       index_generation, context_version
                FROM v7_research_conflict_contexts
                WHERE task_id=? AND conflict_id=?
                ORDER BY context_version
                """,
                (task_id, conflict_id),
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def current_for(self, task_id: str, conflict_id: str) -> ResearchConflictContext | None:
        history = self.history(task_id, conflict_id)
        return history[-1] if history else None

    def current_for_task(self, task_id: str) -> tuple[ResearchConflictContext, ...]:
        """读取任务登记的各冲突当前上下文，避免按全局冲突表越权列举。"""
        with self._store.connect() as connection:
            rows = connection.execute(
                """
                SELECT task_id, run_id, conflict_id, fact_version, artifact_version,
                       index_generation, context_version
                FROM v7_research_conflict_contexts
                WHERE task_id=?
                ORDER BY conflict_id, context_version DESC
                """,
                (task_id,),
            ).fetchall()
        current: list[ResearchConflictContext] = []
        seen: set[str] = set()
        for row in rows:
            context = self._from_row(row)
            if context.conflict_id not in seen:
                current.append(context)
                seen.add(context.conflict_id)
        return tuple(current)

    @staticmethod
    def _from_row(row) -> ResearchConflictContext:
        return ResearchConflictContext(
            task_id=row[0],
            run_id=row[1],
            conflict_id=row[2],
            fact_version=row[3],
            artifact_version=row[4],
            index_generation=row[5],
            context_version=row[6],
        )


@dataclass(frozen=True)
class GrantedConflictApproval:
    """服务端授予的审批及其实际使用的不可伪造绑定。"""

    approval: ApprovalRecord
    binding: ApprovalBinding


class ResearchConflictApprovalService:
    """从可信当前状态生成冲突审批，禁止调用方传入 ApprovalBinding。"""

    def __init__(
        self,
        execution_store: DurableExecutionStore,
        contexts: ResearchConflictContextRepository,
        *,
        clock,
    ) -> None:
        self._execution_store = execution_store
        self._contexts = contexts
        self._clock = clock
        self._tasks = ResearchTaskAdapter(execution_store)
        self._plans = ResearchPlanRepository(execution_store.metadata_store)
        self._conflicts = FinancialFactConflictRepository(execution_store.metadata_store)
        self._approvals = GovernanceApprovalStore(execution_store.metadata_store, clock=clock)

    def grant(
        self,
        *,
        task_id: str,
        conflict_id: str,
        action: str,
        selected_fact_id: str | None,
        approver: str,
        expires_at: datetime,
    ) -> GrantedConflictApproval:
        """为批准或驳回创建审批；所有依赖版本均由服务端读取。"""
        try:
            review_action = ConflictReviewAction(action)
        except ValueError as exc:
            raise ValueError("action 必须是受支持的冲突裁决动作") from exc
        if review_action is ConflictReviewAction.KEEP_PENDING:
            raise ValueError("保持未决不需要审批")
        if not isinstance(approver, str) or not approver.strip():
            raise ValueError("审批人不能为空")
        if not isinstance(expires_at, datetime) or expires_at <= self._clock():
            raise ValueError("审批有效期必须晚于当前时间")

        run_id, binding, conflict = self.current_binding(task_id, conflict_id)
        if review_action is ConflictReviewAction.APPROVE:
            if selected_fact_id not in conflict.fact_ids:
                raise ValueError("批准时必须选择冲突双方之一")
        elif selected_fact_id is not None:
            raise ValueError("驳回时不得选择事实")

        params = {"action": review_action.value, "selected_fact_id": selected_fact_id}
        approval = self._approvals.grant(
            ApprovalRequest(
                task_id=task_id,
                run_id=run_id,
                subject=SUBJECT_CONFLICT_RESOLUTION,
                subject_id=conflict_id,
                params=params,
                binding=binding,
                approver=approver,
                expires_at=expires_at,
            )
        )
        return GrantedConflictApproval(approval=approval, binding=binding)

    def current_binding(self, task_id: str, conflict_id: str):
        """读取当前可信依赖并构造裁决/审批共用绑定。"""
        try:
            snapshot = self._tasks.task_snapshot(task_id)
        except KeyError as exc:
            raise ValueError("任务不存在") from exc
        plan = self._plans.current_for_task(task_id)
        if plan is None:
            raise ValueError("任务尚未持久化研究计划")
        context = self._contexts.current_for(task_id, conflict_id)
        if context is None or context.run_id != snapshot.run_id:
            raise ValueError("冲突上下文不存在或与当前任务运行不一致")
        conflict = self._conflicts.get(conflict_id)
        if conflict is None or conflict.status != "pending_review":
            raise ValueError("仅可操作存在的待审核冲突")
        return snapshot.run_id, ApprovalBinding(snapshot.revision, _plan_hash(plan), context.fact_version, context.artifact_version, context.index_generation), conflict


def _plan_hash(plan: ResearchPlan) -> str:
    """对完整计划快照计算稳定哈希，任何计划字段变化都会使审批绑定改变。"""
    payload = {
        "plan_id": plan.plan_id,
        "task_id": plan.task_id,
        "objective": plan.objective,
        "scope": plan.scope,
        "step_ids": plan.step_ids,
        "estimated_cost": str(plan.estimated_cost),
        "risks": plan.risks,
        "plan_version": plan.plan_version,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
