"""D1.9 路由质量—成本曲线比较与理由保存。

设计依据：tasks.md D1.9 与 spec-governance-operations.md「路由可解释」——
比较现有 single/multi 路由的质量、成本与延迟，决策理由（含复杂度、风险、成本依据）
通过只追加审计账本持久化，回放可还原。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.governance.audit import AuditEvent, AuditRecord, GovernanceAuditStore


@dataclass(frozen=True)
class RouteComparison:
    """单条候选路由的质量与成本数据。"""

    path: str
    quality_score: float
    cost_estimate: float
    latency_ms: int


@dataclass(frozen=True)
class RoutingRationale:
    """路由决策理由：选中路径、理由文本、复杂度风险上下文与候选集合。"""

    chosen_path: str
    reason: str
    complexity: str
    risk: str
    alternatives: tuple[RouteComparison, ...]


def compare_routes(
    *,
    single: RouteComparison,
    multi: RouteComparison,
    complexity: str,
    risk: str,
) -> RoutingRationale:
    """比较 single/multi 路由并给出可解释决策。

    规则：高复杂度或高风险时质量优先（取质量分更高者）；
    其余情况按质量成本比（quality/cost）选择，兼顾成本意识。
    """
    alternatives = (single, multi)
    if complexity == "high" or risk == "high":
        chosen = multi if multi.quality_score >= single.quality_score else single
        basis = "高复杂度或高风险，质量优先"
    else:
        chosen = max(alternatives, key=lambda route: route.quality_score / route.cost_estimate)
        basis = "按质量成本比选择"
    reason = (
        f"{basis}。复杂度：{complexity}；风险：{risk}。"
        f"候选 {single.path}：质量 {single.quality_score:.2f}，"
        f"成本 {single.cost_estimate:.4f}，延迟 {single.latency_ms}ms；"
        f"候选 {multi.path}：质量 {multi.quality_score:.2f}，"
        f"成本 {multi.cost_estimate:.4f}，延迟 {multi.latency_ms}ms。"
        f"最终选择 {chosen.path}。"
    )
    return RoutingRationale(
        chosen_path=chosen.path,
        reason=reason,
        complexity=complexity,
        risk=risk,
        alternatives=alternatives,
    )


def save_routing_rationale(
    audit: GovernanceAuditStore,
    rationale: RoutingRationale,
    *,
    task_id: str,
    run_id: str,
) -> AuditRecord:
    """将路由理由写入只追加审计账本，动作固定为 route_selected。"""
    return audit.append(
        AuditEvent(
            task_id=task_id,
            run_id=run_id,
            actor="router",
            action="route_selected",
            resource=f"task:{task_id}",
            result=rationale.chosen_path,
            detail={
                "chosen_path": rationale.chosen_path,
                "reason": rationale.reason,
                "complexity": rationale.complexity,
                "risk": rationale.risk,
                "alternatives": [asdict(route) for route in rationale.alternatives],
            },
            correlation_id=run_id,
        )
    )
