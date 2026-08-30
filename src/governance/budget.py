"""D1.8 软预算预警与硬预算暂停。

设计依据：tasks.md D1.8 与 spec-governance-operations.md「成本与预算」——
接近软预算时发出预警（状态可见）；达到硬预算时抛出超限异常，
调用方捕获后安全暂停任务并保存检查点（配合 C 包可恢复执行内核）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetPolicy:
    """预算策略：软预算触发预警，硬预算触发暂停。"""

    soft_cost: float
    hard_cost: float


@dataclass(frozen=True)
class BudgetState:
    """预算检查结果：status 为 ok 或 soft_warning，携带当前成本估算。"""

    status: str
    cost_estimate: float


class BudgetExceededError(RuntimeError):
    """硬预算超限异常：携带成本估算与硬预算值，供保存检查点后安全暂停。"""

    def __init__(self, cost_estimate: float, hard_cost: float) -> None:
        self.cost_estimate = cost_estimate
        self.hard_cost = hard_cost
        super().__init__(
            f"成本估算 {cost_estimate} 达到硬预算 {hard_cost}，任务需安全暂停并保存检查点"
        )


class BudgetController:
    """预算控制器：按成本估算返回状态或抛出硬预算超限异常。"""

    def __init__(self, policy: BudgetPolicy) -> None:
        self._policy = policy

    def evaluate(self, cost_estimate: float) -> BudgetState:
        """评估当前成本：低于软预算 ok；达到软预算 soft_warning；达到硬预算抛异常。"""
        if cost_estimate >= self._policy.hard_cost:
            raise BudgetExceededError(cost_estimate=cost_estimate, hard_cost=self._policy.hard_cost)
        if cost_estimate >= self._policy.soft_cost:
            return BudgetState(status="soft_warning", cost_estimate=cost_estimate)
        return BudgetState(status="ok", cost_estimate=cost_estimate)
