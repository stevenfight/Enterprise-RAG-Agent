# -*- coding: utf-8 -*-
"""E-T01 研究计划快照的 SQLite 持久化边界。"""

from __future__ import annotations

import json
from decimal import Decimal

from src.research_delivery import ResearchPlan
from src.v7_metadata_store import V7MetadataStore


class ResearchPlanRepository:
    """只追加保存研究计划版本，不复制 C0 的任务状态。"""

    def __init__(self, metadata_store: V7MetadataStore) -> None:
        self._metadata_store = metadata_store
        self._metadata_store.initialize()

    def append(self, plan: ResearchPlan) -> None:
        """保存一个不可变计划版本；重复版本必须显式失败。"""
        with self._metadata_store.connect() as connection:
            connection.execute(
                """
                INSERT INTO v7_research_plans (
                    plan_id, task_id, plan_version, objective, scope_json,
                    step_ids_json, estimated_cost, risks_json, step_bindings_json, step_inputs_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.plan_id,
                    plan.task_id,
                    plan.plan_version,
                    plan.objective,
                    json.dumps(plan.scope, ensure_ascii=False),
                    json.dumps(plan.step_ids, ensure_ascii=False),
                    str(plan.estimated_cost),
                    json.dumps(plan.risks, ensure_ascii=False),
                    json.dumps([
                        {
                            "step_id": binding.step_id,
                            "agent_name": binding.agent_name,
                            "tool_names": list(binding.tool_names),
                        }
                        for binding in plan.step_bindings
                    ], ensure_ascii=False),
                    json.dumps([{ "step_id": item.step_id, "payload": json.loads(item.payload_json)} for item in plan.step_inputs], ensure_ascii=False),
                ),
            )
            connection.commit()

    def current_for_task(self, task_id: str) -> ResearchPlan | None:
        """读取任务最新计划版本；没有显式计划的兼容旧任务返回 None。"""
        with self._metadata_store.connect() as connection:
            row = connection.execute(
                """
                SELECT plan_id, task_id, objective, scope_json, step_ids_json,
                       estimated_cost, risks_json, plan_version
                       , step_bindings_json, step_inputs_json
                FROM v7_research_plans
                WHERE task_id=?
                ORDER BY plan_version DESC
                LIMIT 1
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return ResearchPlan.create(
            plan_id=row[0],
            task_id=row[1],
            objective=row[2],
            scope=tuple(json.loads(row[3])),
            step_ids=tuple(json.loads(row[4])),
            estimated_cost=Decimal(row[5]),
            risks=tuple(json.loads(row[6])),
            plan_version=row[7],
            step_bindings=(
                {
                    item["step_id"]: {
                        "agent_name": item["agent_name"],
                        "tool_names": item.get("tool_names", []),
                    }
                    for item in json.loads(row[8] or "[]")
                }
                if row[8] and json.loads(row[8] or "[]")
                else None
            ),
            step_inputs=({item["step_id"]: item["payload"] for item in json.loads(row[9] or "[]")} if row[9] else None),
        )
