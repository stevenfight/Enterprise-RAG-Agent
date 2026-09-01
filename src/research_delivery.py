# -*- coding: utf-8 -*-
"""E1.1 研究交付的不可变领域模型。

本模块只定义计划、声明、报告和审核状态的稳定数据边界。
审批编排、预算暂停、持久化、导出与局部失效分别由后续 E1.4–E1.7 实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Iterable, Mapping
import json
import math


class ClaimSupportKind(str, Enum):
    """声明的主要可审计依据类型。"""

    FACT = "fact"
    CALCULATION = "calculation"
    SOURCE = "source"
    ANALYSIS = "analysis"


class ReportReviewStatus(str, Enum):
    """报告审核状态；状态迁移和审批消费由后续工作流负责。"""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class ResearchStepBinding:
    """研究步骤对已注册 Agent 及工具白名单的不可变绑定。"""

    step_id: str
    agent_name: str
    tool_names: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        step_id: str,
        agent_name: str,
        tool_names: Iterable[str] = (),
    ) -> "ResearchStepBinding":
        _require_nonempty_strings({"step_id": step_id, "agent_name": agent_name})
        if isinstance(tool_names, (str, bytes)):
            raise ValueError("tool_names 必须是字符串集合")
        return cls(
            step_id=step_id,
            agent_name=agent_name,
            tool_names=_normalize_ids(tool_names, "tool_names"),
        )


@dataclass(frozen=True)
class ResearchStepInput:
    """经计划审批持久化的单步骤工具输入。"""
    step_id: str
    payload_json: str

    @classmethod
    def create(cls, *, step_id: str, payload: Mapping[str, object]) -> "ResearchStepInput":
        _require_nonempty_strings({"step_id": step_id})
        if not isinstance(payload, Mapping) or not payload:
            raise ValueError("步骤输入必须是非空对象")
        try:
            payload_json = json.dumps(
                dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("步骤输入必须是可 JSON 序列化对象") from exc
        return cls(step_id=step_id, payload_json=payload_json)


@dataclass(frozen=True)
class ResearchPlan:
    """研究计划快照，包含任务范围、步骤、预算估算和已知风险。"""

    plan_id: str
    task_id: str
    objective: str
    scope: tuple[str, ...]
    step_ids: tuple[str, ...]
    estimated_cost: Decimal
    risks: tuple[str, ...]
    plan_version: int
    step_bindings: tuple[ResearchStepBinding, ...] = ()
    step_inputs: tuple[ResearchStepInput, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        plan_id: str,
        task_id: str,
        objective: str,
        scope: tuple[str, ...] | list[str],
        step_ids: tuple[str, ...] | list[str],
        estimated_cost: str | int | float | Decimal,
        risks: tuple[str, ...] | list[str] = (),
        plan_version: int = 1,
        step_bindings: Mapping[str, Mapping[str, object]] | Iterable[ResearchStepBinding] | None = None,
        step_inputs: Mapping[str, Mapping[str, object]] | Iterable[ResearchStepInput] | None = None,
    ) -> "ResearchPlan":
        """创建经过边界校验的计划，不从空范围或空预算推测默认值。"""
        _require_nonempty_strings(
            {"plan_id": plan_id, "task_id": task_id, "objective": objective}
        )
        normalized_scope = _normalize_ids(scope, "scope", require_nonempty=True)
        normalized_steps = _normalize_ids(step_ids, "step_ids", require_nonempty=True)
        normalized_risks = _normalize_ids(risks, "risks")
        if type(plan_version) is not int or plan_version <= 0:
            raise ValueError("plan_version 必须是正整数")
        normalized_bindings = _normalize_step_bindings(step_bindings, normalized_steps)
        normalized_inputs = _normalize_step_inputs(step_inputs, normalized_steps)
        for item in normalized_inputs:
            if item.step_id == "calculate":
                _validate_calculator_step_input(json.loads(item.payload_json))
            if item.step_id == "compare":
                _validate_compare_step_input(json.loads(item.payload_json))
            if item.step_id == "chart":
                _validate_chart_step_input(json.loads(item.payload_json))
        return cls(
            plan_id=plan_id,
            task_id=task_id,
            objective=objective,
            scope=normalized_scope,
            step_ids=normalized_steps,
            estimated_cost=_to_nonnegative_decimal(estimated_cost, "estimated_cost"),
            risks=normalized_risks,
            plan_version=plan_version,
            step_bindings=normalized_bindings,
            step_inputs=normalized_inputs,
        )

    def binding_for(self, step_id: str) -> ResearchStepBinding | None:
        """返回步骤绑定；未绑定的历史计划保持兼容并返回 None。"""
        return next((item for item in self.step_bindings if item.step_id == step_id), None)

    def input_for(self, step_id: str) -> Mapping[str, object] | None:
        item = next((item for item in self.step_inputs if item.step_id == step_id), None)
        return json.loads(item.payload_json) if item is not None else None


@dataclass(frozen=True)
class ResearchPlanReplanResult:
    """范围调整后的不可变计划及本次实际重新计算的步骤。"""

    plan: ResearchPlan
    affected_step_ids: tuple[str, ...]
    unchanged_step_ids: tuple[str, ...]
    recalculated_step_costs: dict[str, Decimal]


class ResearchPlanReplanner:
    """E1.4 仅在执行前按范围依赖重规划受影响的研究计划步骤。"""

    @classmethod
    def replan(
        cls,
        *,
        plan: ResearchPlan,
        task_status: str,
        new_scope: tuple[str, ...] | list[str],
        step_scope_dependencies: Mapping[str, Iterable[str]],
        step_dependencies: Mapping[str, Iterable[str]],
        current_step_costs: Mapping[str, str | int | float | Decimal],
        recalculated_step_costs: Mapping[str, str | int | float | Decimal],
    ) -> ResearchPlanReplanResult:
        """创建新计划版本，只替换范围变化波及的步骤成本。

        ``step_dependencies`` 使用“步骤 -> 直接上游步骤”的 DAG 表达；范围直接
        命中的步骤及其全部下游步骤才允许出现在新的成本估算中。
        """
        if not isinstance(plan, ResearchPlan):
            raise ValueError("plan 必须是 ResearchPlan")
        if task_status != "pending":
            raise ValueError("仅 pending 任务允许在执行前调整范围")

        normalized_scope = _normalize_ids(new_scope, "new_scope", require_nonempty=True)
        if normalized_scope == plan.scope:
            raise ValueError("new_scope 未发生变化，无需重规划")

        step_ids = plan.step_ids
        scope_dependencies = cls._normalize_step_mapping(
            step_scope_dependencies, step_ids, "step_scope_dependencies"
        )
        dependencies = cls._normalize_step_mapping(
            step_dependencies, step_ids, "step_dependencies"
        )
        cls._validate_dependency_dag(dependencies)

        known_scope = set(plan.scope) | set(normalized_scope)
        for step_id, scope_ids in scope_dependencies.items():
            unknown_scope = set(scope_ids) - known_scope
            if unknown_scope:
                raise ValueError(f"步骤 {step_id} 关联了计划外范围: {sorted(unknown_scope)}")

        old_costs = cls._normalize_costs(current_step_costs, step_ids, "current_step_costs")
        if sum(old_costs.values(), Decimal("0")) != plan.estimated_cost:
            raise ValueError("current_step_costs 之和必须等于计划预算")

        changed_scope = set(plan.scope) ^ set(normalized_scope)
        directly_affected = {
            step_id
            for step_id in step_ids
            if set(scope_dependencies[step_id]) & changed_scope
        }
        affected = cls._downstream_closure(directly_affected, dependencies)
        affected_step_ids = tuple(step_id for step_id in step_ids if step_id in affected)
        unchanged_step_ids = tuple(step_id for step_id in step_ids if step_id not in affected)

        new_costs = cls._normalize_costs(
            recalculated_step_costs, affected_step_ids, "recalculated_step_costs"
        )
        revised_costs = dict(old_costs)
        revised_costs.update(new_costs)
        revised_plan = ResearchPlan.create(
            plan_id=plan.plan_id,
            task_id=plan.task_id,
            objective=plan.objective,
            scope=normalized_scope,
            step_ids=plan.step_ids,
            estimated_cost=sum(revised_costs.values(), Decimal("0")),
            risks=plan.risks,
            plan_version=plan.plan_version + 1,
            step_bindings=plan.step_bindings,
            step_inputs=plan.step_inputs,
        )
        return ResearchPlanReplanResult(
            plan=revised_plan,
            affected_step_ids=affected_step_ids,
            unchanged_step_ids=unchanged_step_ids,
            recalculated_step_costs=new_costs,
        )

    @staticmethod
    def _normalize_step_mapping(
        mapping: Mapping[str, Iterable[str]], step_ids: tuple[str, ...], field_name: str
    ) -> dict[str, tuple[str, ...]]:
        if not isinstance(mapping, Mapping) or set(mapping) != set(step_ids):
            raise ValueError(f"{field_name} 必须恰好覆盖计划全部步骤")
        normalized: dict[str, tuple[str, ...]] = {}
        for step_id in step_ids:
            values = mapping[step_id]
            if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
                raise ValueError(f"{field_name}[{step_id}] 必须是字符串集合")
            normalized[step_id] = _normalize_ids(tuple(values), f"{field_name}[{step_id}]")
        return normalized

    @staticmethod
    def _normalize_costs(
        costs: Mapping[str, str | int | float | Decimal],
        expected_step_ids: tuple[str, ...],
        field_name: str,
    ) -> dict[str, Decimal]:
        if not isinstance(costs, Mapping) or set(costs) != set(expected_step_ids):
            raise ValueError(f"{field_name} 必须恰好覆盖指定步骤")
        return {
            step_id: _to_nonnegative_decimal(costs[step_id], f"{field_name}[{step_id}]")
            for step_id in expected_step_ids
        }

    @staticmethod
    def _validate_dependency_dag(dependencies: Mapping[str, tuple[str, ...]]) -> None:
        step_ids = set(dependencies)
        for step_id, upstream_steps in dependencies.items():
            unknown_steps = set(upstream_steps) - step_ids
            if unknown_steps:
                raise ValueError(f"步骤 {step_id} 依赖了计划外步骤: {sorted(unknown_steps)}")
            if step_id in upstream_steps:
                raise ValueError(f"步骤 {step_id} 不能依赖自身")

        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError("步骤依赖必须是无环 DAG")
            if step_id in visited:
                return
            visiting.add(step_id)
            for upstream_step in dependencies[step_id]:
                visit(upstream_step)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in dependencies:
            visit(step_id)

    @staticmethod
    def _downstream_closure(
        directly_affected: set[str], dependencies: Mapping[str, tuple[str, ...]]
    ) -> set[str]:
        downstream_by_step = {step_id: set() for step_id in dependencies}
        for step_id, upstream_steps in dependencies.items():
            for upstream_step in upstream_steps:
                downstream_by_step[upstream_step].add(step_id)

        affected = set(directly_affected)
        pending = list(directly_affected)
        while pending:
            step_id = pending.pop()
            for downstream_step in downstream_by_step[step_id]:
                if downstream_step not in affected:
                    affected.add(downstream_step)
                    pending.append(downstream_step)
        return affected


@dataclass(frozen=True)
class Claim:
    """报告声明及其稳定事实、计算、来源或分析判断依据。"""

    claim_id: str
    text: str
    support_kind: ClaimSupportKind
    fact_ids: tuple[str, ...]
    calculation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    analysis_label: str | None

    @classmethod
    def create(
        cls,
        *,
        claim_id: str,
        text: str,
        support_kind: ClaimSupportKind | None = None,
        fact_ids: tuple[str, ...] | list[str] = (),
        calculation_ids: tuple[str, ...] | list[str] = (),
        source_ids: tuple[str, ...] | list[str] = (),
        analysis_label: str | None = None,
    ) -> "Claim":
        """创建有明确依据的声明，拒绝没有可审计支撑的结论。"""
        _require_nonempty_strings({"claim_id": claim_id, "text": text})
        if not isinstance(support_kind, ClaimSupportKind):
            raise ValueError("声明必须关联受支持的依据类型")
        normalized_facts = _normalize_ids(fact_ids, "fact_ids")
        normalized_calculations = _normalize_ids(calculation_ids, "calculation_ids")
        normalized_sources = _normalize_ids(source_ids, "source_ids")
        normalized_label = _normalize_optional_text(analysis_label, "analysis_label")

        if support_kind is ClaimSupportKind.FACT and not (normalized_facts or normalized_sources):
            raise ValueError("事实声明必须关联事实或来源")
        if support_kind is ClaimSupportKind.CALCULATION and not normalized_calculations:
            raise ValueError("计算声明必须关联计算")
        if support_kind is ClaimSupportKind.SOURCE and not normalized_sources:
            raise ValueError("来源声明必须关联来源")
        if support_kind is ClaimSupportKind.ANALYSIS and normalized_label is None:
            raise ValueError("分析声明必须关联分析判断标签")
        if not (normalized_facts or normalized_calculations or normalized_sources or normalized_label):
            raise ValueError("声明必须关联事实、计算、来源或分析判断标签")

        return cls(
            claim_id=claim_id,
            text=text,
            support_kind=support_kind,
            fact_ids=normalized_facts,
            calculation_ids=normalized_calculations,
            source_ids=normalized_sources,
            analysis_label=normalized_label,
        )


@dataclass(frozen=True)
class ResearchReport:
    """可审核研究报告快照，绑定计划、数据版本、生成时间和不可变声明。"""

    report_id: str
    task_id: str
    plan_id: str
    report_version: int
    data_version: str
    review_status: ReportReviewStatus
    claims: tuple[Claim, ...]
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        report_id: str,
        task_id: str,
        plan_id: str,
        report_version: int,
        data_version: str,
        review_status: ReportReviewStatus,
        claims: tuple[Claim, ...] | list[Claim],
        created_at: str | None = None,
    ) -> "ResearchReport":
        """创建报告快照；审核状态显式保存，后续流程不得隐式推断。"""
        _require_nonempty_strings(
            {
                "report_id": report_id,
                "task_id": task_id,
                "plan_id": plan_id,
                "data_version": data_version,
            }
        )
        if type(report_version) is not int or report_version <= 0:
            raise ValueError("report_version 必须是正整数")
        if not isinstance(review_status, ReportReviewStatus):
            raise ValueError("review_status 必须是受支持的报告审核状态")
        normalized_claims = _normalize_claims(claims)
        return cls(
            report_id=report_id,
            task_id=task_id,
            plan_id=plan_id,
            report_version=report_version,
            data_version=data_version,
            review_status=review_status,
            claims=normalized_claims,
            created_at=_normalize_created_at(created_at),
        )


def _require_nonempty_strings(values: dict[str, str]) -> None:
    for field_name, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} 不能为空")


def _normalize_ids(
    value: tuple[str, ...] | list[str], field_name: str, *, require_nonempty: bool = False
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise ValueError(f"{field_name} 必须是字符串元组或列表")
    if require_nonempty and not value:
        raise ValueError(f"{field_name} 不能为空")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} 中的值不能为空")
    if len(set(value)) != len(value):
        raise ValueError(f"{field_name} 中存在重复值")
    return tuple(value)


def _normalize_step_bindings(
    value: Mapping[str, Mapping[str, object]] | Iterable[ResearchStepBinding] | None,
    step_ids: tuple[str, ...],
) -> tuple[ResearchStepBinding, ...]:
    """规范化绑定并要求显式覆盖全部步骤；None 仅用于兼容历史计划。"""
    if value is None:
        return ()
    if isinstance(value, Mapping):
        if set(value) != set(step_ids):
            raise ValueError("step_bindings 必须恰好覆盖计划全部步骤")
        bindings: list[ResearchStepBinding] = []
        for step_id in step_ids:
            item = value[step_id]
            if not isinstance(item, Mapping):
                raise ValueError(f"step_bindings[{step_id}] 必须是对象")
            bindings.append(
                ResearchStepBinding.create(
                    step_id=step_id,
                    agent_name=item.get("agent_name"),
                    tool_names=item.get("tool_names", ()),
                )
            )
        return tuple(bindings)
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ValueError("step_bindings 必须是对象或绑定集合")
    bindings = tuple(value)
    if not bindings:
        return ()
    if any(not isinstance(item, ResearchStepBinding) for item in bindings):
        raise ValueError("step_bindings 只能包含 ResearchStepBinding")
    if tuple(item.step_id for item in bindings) != tuple(step_ids):
        raise ValueError("step_bindings 必须按计划步骤顺序且恰好覆盖全部步骤")
    return bindings


def _normalize_step_inputs(
    value: Mapping[str, Mapping[str, object]] | Iterable[ResearchStepInput] | None,
    step_ids: tuple[str, ...],
) -> tuple[ResearchStepInput, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        if not set(value).issubset(step_ids):
            raise ValueError("step_inputs 包含计划外步骤")
        return tuple(ResearchStepInput.create(step_id=step_id, payload=payload) for step_id, payload in value.items())
    items = tuple(value)
    if any(not isinstance(item, ResearchStepInput) for item in items):
        raise ValueError("step_inputs 只能包含 ResearchStepInput")
    if len({item.step_id for item in items}) != len(items) or not {item.step_id for item in items}.issubset(step_ids):
        raise ValueError("step_inputs 步骤无效或重复")
    return items


def _validate_calculator_step_input(payload: Mapping[str, object]) -> None:
    """校验审批后的计算参数，禁止向 calculator 传递自由字段。"""
    operation = payload.get("operation")
    contracts = {
        "yoy_growth": (("current", "previous"), ()),
        "cagr": (("start_value", "end_value", "years"), ()),
        "margin": (("numerator", "denominator"), ("margin_type",)),
        "pct_change": (("new_value", "old_value"), ("label",)),
    }
    if not isinstance(operation, str) or operation not in contracts:
        raise ValueError("不支持的计算操作")
    numeric_fields, text_fields = contracts[operation]
    allowed_fields = {"operation", *numeric_fields, *text_fields}
    unexpected = set(payload) - allowed_fields
    if unexpected:
        raise ValueError("计算步骤包含未批准字段")
    missing = set(numeric_fields + text_fields) - set(payload)
    if missing:
        raise ValueError("计算步骤缺少字段")
    for field_name in numeric_fields:
        value = payload[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"计算步骤字段 {field_name} 必须是有限数值")
    for field_name in text_fields:
        value = payload[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"计算步骤字段 {field_name} 必须是非空文本")


def _validate_compare_step_input(payload: Mapping[str, object]) -> None:
    """校验审批后的对比参数，禁止向 compare 传递自由字段。"""
    required_fields = {"companies", "metric", "year", "top_n"}
    unexpected = set(payload) - required_fields
    if unexpected:
        raise ValueError("对比步骤包含未批准字段")
    missing = required_fields - set(payload)
    if missing:
        raise ValueError("对比步骤缺少字段")
    companies = payload["companies"]
    if not isinstance(companies, list) or len(companies) < 2:
        raise ValueError("对比步骤至少需要两家公司")
    if any(not isinstance(company, str) or not company.strip() for company in companies):
        raise ValueError("对比步骤公司必须是非空文本")
    if len(set(companies)) != len(companies):
        raise ValueError("对比步骤公司不能重复")
    if not isinstance(payload["metric"], str) or not payload["metric"].strip():
        raise ValueError("对比步骤指标必须是非空文本")
    year = payload["year"]
    if not isinstance(year, str) or not year.isdigit() or len(year) != 4:
        raise ValueError("对比步骤年份必须是四位文本")
    top_n = payload["top_n"]
    if isinstance(top_n, bool) or not isinstance(top_n, int) or not 1 <= top_n <= 5:
        raise ValueError("对比步骤 top_n 必须是 1 到 5 的整数")


def _validate_chart_step_input(payload: Mapping[str, object]) -> None:
    """校验审批后的图表参数，禁止从自由文本推断图表数据。"""
    allowed_fields = {"data", "chart_type", "title", "xlabel", "ylabel"}
    unexpected = set(payload) - allowed_fields
    if unexpected:
        raise ValueError("图表步骤包含未批准字段")
    if not {"data", "chart_type"}.issubset(payload):
        raise ValueError("图表步骤缺少字段")
    data = payload["data"]
    if not isinstance(data, Mapping) or not data:
        raise ValueError("图表步骤 data 必须是非空对象")
    if any(not isinstance(label, str) or not label.strip() or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for label, value in data.items()):
        raise ValueError("图表步骤 data 必须是非空标签与有限数值")
    if payload["chart_type"] not in {"bar", "line", "pie", "hbar"}:
        raise ValueError("图表步骤 chart_type 不受支持")
    for field_name in ("title", "xlabel", "ylabel"):
        if field_name in payload and (not isinstance(payload[field_name], str) or not payload[field_name].strip()):
            raise ValueError(f"图表步骤字段 {field_name} 必须是非空文本")


def _to_nonnegative_decimal(value: str | int | float | Decimal, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是非负有限数值") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field_name} 必须是非负有限数值")
    return result


def _normalize_optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 不能为空")
    return value


def _normalize_claims(value: tuple[Claim, ...] | list[Claim]) -> tuple[Claim, ...]:
    if not isinstance(value, (tuple, list)) or not value:
        raise ValueError("claims 必须包含至少一条声明")
    if any(not isinstance(claim, Claim) for claim in value):
        raise ValueError("claims 只能包含 Claim")
    claim_ids = tuple(claim.claim_id for claim in value)
    if len(set(claim_ids)) != len(claim_ids):
        raise ValueError("claims 中存在重复声明 ID")
    return tuple(value)


def _normalize_created_at(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if not isinstance(value, str) or not value.strip():
        raise ValueError("created_at 不能为空")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("created_at 必须是 ISO 8601 时间") from exc
    return value
