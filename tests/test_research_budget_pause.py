# -*- coding: utf-8 -*-
"""D-T09：研究工作流在硬预算超限时原子保存检查点并暂停。"""

from pathlib import Path


def test_hard_budget_pause_persists_checkpoint_and_pauses_atomically(tmp_path: Path):
    from src.durable_execution import DurableExecutionStore
    from src.governance.budget import BudgetController, BudgetPolicy
    from src.research_budget_guard import ResearchBudgetGuard
    from src.research_task_adapter import ResearchTaskAdapter
    from src.v7_metadata_store import V7MetadataStore

    store = DurableExecutionStore(V7MetadataStore(tmp_path / "v7_metadata.sqlite3"))
    adapter = ResearchTaskAdapter(store)
    created = adapter.create_task("budget-001", ["retrieve"])
    running = adapter.start_task("budget-001", created.revision, "cmd-start", actor="worker")
    claim = adapter.claim_step("budget-001", "retrieve", "worker-a", now=1000)

    guard = ResearchBudgetGuard(adapter, BudgetController(BudgetPolicy(soft_cost=1, hard_cost=2)))
    paused = guard.evaluate_or_pause(
        task_id="budget-001", step_id="retrieve", attempt_token=claim.attempt.attempt_token,
        owner_token="worker-a", expected_revision=running.revision, command_id="cmd-budget",
        dag_step_ids=["retrieve"], dependency_versions={"index_generation": "gen-1"},
        cost_estimate=2.5, actor="worker", now=1001,
    )

    assert paused.status == "paused"
    assert store.run("research:budget-001").status == "paused"
    assert store.checkpoints("research:budget-001")[0].payload["budget"] == {
        "cost_estimate": 2.5, "hard_cost": 2,
    }
