"""D1.8 软预算预警与硬预算暂停测试（D-GATE-4）。

规格依据：tasks.md D1.8 与 spec-governance-operations.md「成本与预算」——
接近软预算发出预警；超过硬预算抛出预算超限异常，调用方安全暂停并保存检查点。
"""

from __future__ import annotations

import pytest

from src.governance.budget import BudgetController, BudgetExceededError, BudgetPolicy


def test_under_soft_budget_is_ok() -> None:
    """成本低于软预算时状态为 ok。"""
    controller = BudgetController(BudgetPolicy(soft_cost=0.05, hard_cost=0.10))
    state = controller.evaluate(cost_estimate=0.01)
    assert state.status == "ok"


def test_between_soft_and_hard_warns() -> None:
    """成本达到或超过软预算且低于硬预算时发出 soft_warning。"""
    controller = BudgetController(BudgetPolicy(soft_cost=0.05, hard_cost=0.10))
    state = controller.evaluate(cost_estimate=0.07)
    assert state.status == "soft_warning"


def test_over_hard_budget_raises_with_cost() -> None:
    """成本达到或超过硬预算时抛出超限异常，携带成本供保存检查点。"""
    controller = BudgetController(BudgetPolicy(soft_cost=0.05, hard_cost=0.10))
    with pytest.raises(BudgetExceededError) as excinfo:
        controller.evaluate(cost_estimate=0.12)
    assert excinfo.value.cost_estimate == pytest.approx(0.12)


def test_budget_state_carries_cost() -> None:
    """预算状态携带当前成本估算，供审计与告警记录。"""
    controller = BudgetController(BudgetPolicy(soft_cost=0.05, hard_cost=0.10))
    state = controller.evaluate(cost_estimate=0.03)
    assert state.cost_estimate == pytest.approx(0.03)
