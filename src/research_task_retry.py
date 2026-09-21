# -*- coding: utf-8 -*-
"""E-T38：从已失败研究任务创建可审计的重新提交任务。"""

from __future__ import annotations

import json
import re
import uuid

from src.durable_execution import RevisionConflictError
from src.research_task_adapter import ResearchTaskAdapter, ResearchTaskSnapshot


class ResearchTaskRetryService:
    """保留原失败任务，仅复制计划到新的 pending 重试任务。"""

    _RETRY_SUFFIX = re.compile(r"^(?P<base>.+)-retry-(?P<number>\d+)$")

    def __init__(self, adapter: ResearchTaskAdapter) -> None:
        self._adapter = adapter

    def create_retry(
        self,
        task_id: str,
        expected_revision: int,
        command_id: str,
        *,
        actor: str,
    ) -> ResearchTaskSnapshot:
        """以单一事务复制最新计划并登记新的 submitted 任务。"""
        source_task_id = self._task_id(task_id)
        if not isinstance(command_id, str) or not command_id.strip():
            raise ValueError("重试命令 ID 不能为空")
        run_id = self._adapter.run_id_for(source_task_id)
        store = self._adapter.execution_store
        with store.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                source_run = connection.execute(
                    "SELECT status, revision FROM v7_execution_runs WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if source_run is None:
                    raise KeyError(source_task_id)
                command = connection.execute(
                    "SELECT run_id, target_status FROM v7_execution_commands WHERE command_id=?",
                    (command_id,),
                ).fetchone()
                if command is not None:
                    if command[0] != run_id or command[1] != "retry_created":
                        raise ValueError("重试命令 ID 已用于其他操作")
                    retry_task_id = self._retry_task_id_for_command(connection, source_task_id, command_id)
                    connection.rollback()
                    return self._adapter.task_snapshot(retry_task_id)
                if source_run[0] != "failed":
                    raise ValueError("仅 failed 任务可以创建重试任务")
                if source_run[1] != expected_revision:
                    raise RevisionConflictError(source_run[1])
                plan = connection.execute(
                    "SELECT objective, scope_json, step_ids_json, estimated_cost, risks_json, step_bindings_json FROM v7_research_plans WHERE task_id=? ORDER BY plan_version DESC LIMIT 1",
                    (source_task_id,),
                ).fetchone()
                if plan is None:
                    raise ValueError("原任务没有持久化计划，不能创建重试任务")
                submission = connection.execute(
                    "SELECT requester FROM v7_research_task_submissions WHERE task_id=? ORDER BY submission_version DESC LIMIT 1",
                    (source_task_id,),
                ).fetchone()
                if submission is None:
                    raise ValueError("原任务没有提交审计，不能创建重试任务")

                retry_task_id = self._next_retry_task_id(connection, source_task_id)
                retry_run_id = self._adapter.run_id_for(retry_task_id)
                connection.execute(
                    "INSERT INTO v7_execution_runs(run_id, status, revision, cancellation_token) VALUES (?, 'pending', 0, ?)",
                    (retry_run_id, uuid.uuid4().hex),
                )
                store._append_event(connection, retry_run_id, 0, "run_created", {})
                connection.execute(
                    "INSERT INTO v7_research_plans(plan_id, task_id, plan_version, objective, scope_json, step_ids_json, estimated_cost, risks_json, step_bindings_json) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)",
                    (
                        f"research-plan:{retry_task_id}:1",
                        retry_task_id,
                        plan[0],
                        plan[1],
                        plan[2],
                        plan[3],
                        plan[4],
                        plan[5],
                    ),
                )
                connection.execute(
                    "INSERT INTO v7_research_task_submissions(task_id, submission_version, status, requester, reviewer) VALUES (?, 1, 'submitted', ?, NULL)",
                    (retry_task_id, submission[0]),
                )
                connection.execute(
                    "INSERT INTO v7_execution_commands(command_id, run_id, target_status, expected_revision, result_revision, result_status, actor) VALUES (?, ?, 'retry_created', ?, ?, 'failed', ?)",
                    (command_id, run_id, expected_revision, source_run[1], actor),
                )
                detail_json = json.dumps(
                    {"new_task_id": retry_task_id, "command_id": command_id},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                connection.execute(
                    "INSERT INTO v7_task_route_decisions(task_id, run_id, decision_type, selected_path, detail_json, actor) VALUES (?, ?, 'retry', NULL, ?, ?)",
                    (source_task_id, run_id, detail_json, actor),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._adapter.task_snapshot(retry_task_id)

    def _next_retry_task_id(self, connection, task_id: str) -> str:
        suffix_match = self._RETRY_SUFFIX.fullmatch(task_id)
        base = suffix_match.group("base") if suffix_match is not None else task_id
        rows = connection.execute(
            "SELECT run_id FROM v7_execution_runs WHERE run_id LIKE ?",
            (self._adapter.run_id_for(base) + "-retry-%",),
        ).fetchall()
        highest = 0
        pattern = re.compile(re.escape(base) + r"-retry-(\d+)$")
        for (run_id,) in rows:
            match = pattern.fullmatch(str(run_id).removeprefix("research:"))
            if match is not None:
                highest = max(highest, int(match.group(1)))
        return f"{base}-retry-{highest + 1}"

    @staticmethod
    def _retry_task_id_for_command(connection, source_task_id: str, command_id: str) -> str:
        rows = connection.execute(
            "SELECT detail_json FROM v7_task_route_decisions WHERE task_id=? AND decision_type='retry' ORDER BY decision_id DESC",
            (source_task_id,),
        ).fetchall()
        for (detail_json,) in rows:
            detail = json.loads(detail_json)
            if detail.get("command_id") == command_id and isinstance(detail.get("new_task_id"), str):
                return detail["new_task_id"]
        raise RuntimeError("重试命令缺少对应的新任务审计记录")

    @staticmethod
    def _task_id(task_id: str) -> str:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id 不能为空")
        return task_id.strip()
