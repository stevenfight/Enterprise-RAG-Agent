# -*- coding: utf-8 -*-
"""D-T09 研究工作流的预算暂停接线。"""

from __future__ import annotations

from typing import Iterable

from src.governance.budget import BudgetController, BudgetExceededError
from src.research_task_adapter import ResearchTaskAdapter, ResearchTaskSnapshot


class ResearchBudgetGuard:
    """预算未超限时返回状态；超限时保存检查点并暂停任务。"""

    def __init__(self, adapter: ResearchTaskAdapter, controller: BudgetController) -> None:
        self._adapter = adapter
        self._controller = controller

    def evaluate_or_pause(self, *, task_id: str, step_id: str, attempt_token: str, owner_token: str, expected_revision: int, command_id: str, dag_step_ids: Iterable[str], dependency_versions: dict[str, str], cost_estimate: float, actor: str, now: float) -> ResearchTaskSnapshot | None:
        try:
            self._controller.evaluate(cost_estimate)
        except BudgetExceededError as exc:
            return self._adapter.pause_for_budget(task_id, step_id, attempt_token, owner_token, expected_revision, command_id, dag_step_ids=dag_step_ids, dependency_versions=dependency_versions, budget={"cost_estimate": exc.cost_estimate, "hard_cost": exc.hard_cost}, actor=actor, now=now)
        return None
