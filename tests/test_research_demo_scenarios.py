# -*- coding: utf-8 -*-
"""E1.9 离线演示数据完整性契约。"""

import json
from pathlib import Path


def test_demo_scenarios_cover_main_conflict_recovery_and_budget_pause() -> None:
    path = Path("evals/demos/research_workflow_demo.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert {item["scenario_id"] for item in payload["scenarios"]} == {"main-flow", "conflict-review", "recovery", "budget-pause"}
    assert all(item["expected_outcome"] for item in payload["scenarios"])
