# -*- coding: utf-8 -*-
"""E-T33：批准后研究任务的最小可审计执行服务。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

from src.agent_registry import AgentRegistry
from src.research_delivery import Claim, ClaimSupportKind, ReportReviewStatus, ResearchReport
from src.research_plan_repository import ResearchPlanRepository
from src.research_report_repository import ResearchReportRepository
from src.research_task_adapter import ResearchTaskAdapter, ResearchTaskSnapshot
from src.tools import BaseTool, ToolRegistry


class ResearchTaskExecutor:
    """顺序执行已批准计划，拒绝把无来源的结果写成报告。"""

    def __init__(
        self,
        task_adapter: ResearchTaskAdapter,
        plan_repository: ResearchPlanRepository,
        report_repository: ResearchReportRepository,
        *,
        query: Callable[[str], Mapping[str, Any]],
        agent_registry: AgentRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        llm_provider: Any | None = None,
    ) -> None:
        self._adapter = task_adapter
        self._plans = plan_repository
        self._reports = report_repository
        self._query = query
        self._agent_registry = agent_registry
        self._tool_registry = tool_registry
        self._llm_provider = llm_provider

    def execute(self, task_id: str, *, actor: str) -> ResearchTaskSnapshot:
        """执行当前计划；任一步骤异常均留下失败决策并终止任务。"""
        snapshot = self._adapter.task_snapshot(task_id)
        if snapshot.status != "running":
            raise ValueError("仅运行中的研究任务可以执行")
        plan = self._plans.current_for_task(task_id)
        if plan is None:
            return self._fail(task_id, snapshot.revision, actor)

        dependency_versions = {
            "plan_id": plan.plan_id,
            "plan_version": str(plan.plan_version),
        }
        query_result: Mapping[str, Any] | None = None
        review_result: Mapping[str, Any] | None = None
        calculation_result: Mapping[str, Any] | None = None
        comparison_result: Mapping[str, Any] | None = None
        chart_result: Mapping[str, Any] | None = None
        plan_result: Mapping[str, Any] | None = None
        report_result: Mapping[str, Any] | None = None
        try:
            self._validate_bindings(plan)
            for step_id in plan.step_ids:
                artifact_ids: tuple[str, ...] = ()
                tool_calls: tuple[dict[str, Any], ...] = ()
                worker_call: dict[str, Any] | None = None
                if step_id == "plan" and (binding := plan.binding_for("plan")) is not None and binding.agent_name == "PlanAgent":
                    tool_calls, worker_call, plan_result = self._plan(plan)
                elif step_id == "retrieve":
                    query_result, tool_calls, worker_call = self._retrieve(plan)
                    sources = self._source_ids(query_result)
                    if not sources:
                        raise ValueError("检索未返回可审计来源，不能生成研究报告")
                    artifact_ids = sources
                elif step_id == "calculate":
                    tool_calls, worker_call, calculation_result = self._calculate(plan)
                elif step_id == "compare":
                    tool_calls, worker_call, comparison_result = self._compare(plan)
                elif step_id == "chart":
                    tool_calls, worker_call, chart_result = self._chart(plan)
                elif step_id == "review":
                    if query_result is None or not self._source_ids(query_result):
                        raise ValueError("审核前缺少可审计检索来源")
                    review_result, tool_calls, worker_call = self._review(plan, query_result)
                    if review_result is not None and review_result.get("valid") is not True:
                        raise ValueError("VerifyAgent 审核未通过或未形成有效结论")
                elif step_id == "report":
                    if query_result is None:
                        raise ValueError("生成报告前缺少检索结果")
                    report = self._append_report(task_id, plan.plan_id, query_result)
                    if (binding := plan.binding_for("report")) is not None and binding.agent_name == "ReportAgent":
                        tool_calls, worker_call, report_result = self._report(plan, report)
                    artifact_ids = (report.report_id, *self._source_ids(query_result))
                step_trace = self._step_trace(
                    plan,
                    step_id,
                    query_result=query_result,
                    calculation_result=calculation_result if step_id == "calculate" else None,
                    comparison_result=comparison_result if step_id == "compare" else None,
                    chart_result=chart_result if step_id == "chart" else None,
                    plan_result=plan_result if step_id == "plan" else None,
                    review_result=review_result if step_id == "review" else None,
                    report=report if step_id == "report" else None,
                    report_result=report_result if step_id == "report" else None,
                )
                self._commit_step(
                    task_id,
                    step_id,
                    plan.step_ids,
                    dependency_versions,
                    actor,
                    artifact_ids=artifact_ids,
                    step_trace=step_trace,
                    tool_calls=tool_calls,
                    worker_call=worker_call,
                    report=report if step_id == "report" else None,
                )
        except ValueError as exc:
            current = self._adapter.task_snapshot(task_id)
            if current.status == "running":
                return self._fail(task_id, current.revision, actor, reason=str(exc))
            return current
        except Exception:
            current = self._adapter.task_snapshot(task_id)
            if current.status == "running":
                return self._fail(task_id, current.revision, actor, reason="执行器发生未分类错误")
            return current

        return self._adapter.task_snapshot(task_id)

    def _plan(
        self, plan
    ) -> tuple[tuple[dict[str, Any], ...], dict[str, Any], Mapping[str, Any]]:
        """运行只确认审批快照的无工具 PlanAgent。"""
        binding = plan.binding_for("plan")
        if binding is None or binding.agent_name != "PlanAgent" or binding.tool_names:
            raise ValueError("plan 步骤必须精确绑定 PlanAgent 且不允许工具")
        if self._llm_provider is None:
            raise ValueError("PlanAgent 缺少 LLMProvider")
        from src.worker_agents.plan_agent import PlanAgent

        approved_snapshot = {
            "plan_id": plan.plan_id,
            "plan_version": plan.plan_version,
            "objective": plan.objective,
            "scope": list(plan.scope),
            "step_ids": list(plan.step_ids),
            "estimated_cost": str(plan.estimated_cost),
            "risks": list(plan.risks),
            "step_bindings": [
                {"step_id": item.step_id, "agent_name": item.agent_name, "tool_names": list(item.tool_names)}
                for item in plan.step_bindings
            ],
        }
        result = PlanAgent(llm_provider=self._llm_provider).run(
            "仅确认以下已审批计划快照，不得改写：" + json.dumps(approved_snapshot, ensure_ascii=False)
        )
        if not result.success or not isinstance(result.answer, str) or not result.answer.strip():
            raise ValueError("PlanAgent 未确认已审批计划快照")
        summary = {
            "plan_version": plan.plan_version,
            "scope_count": len(plan.scope),
            "step_count": len(plan.step_ids),
            "acknowledged": True,
        }
        return (
            (),
            {
                "agent_name": "PlanAgent",
                "status": "succeeded",
                "result_summary": {"total_steps": result.total_steps, **summary},
            },
            summary,
        )

    def _report(
        self, plan, report: ResearchReport
    ) -> tuple[tuple[dict[str, Any], ...], dict[str, Any], Mapping[str, Any]]:
        """运行只确认已构造报告草稿的无工具 ReportAgent。"""
        binding = plan.binding_for("report")
        if binding is None or binding.agent_name != "ReportAgent" or binding.tool_names:
            raise ValueError("report 步骤必须精确绑定 ReportAgent 且不允许工具")
        if self._llm_provider is None:
            raise ValueError("ReportAgent 缺少 LLMProvider")
        from src.worker_agents.report_agent import ReportAgent

        draft = {
            "report_id": report.report_id,
            "report_version": report.report_version,
            "review_status": report.review_status.value,
            "claims": [
                {"claim_id": claim.claim_id, "text": claim.text, "support_kind": claim.support_kind.value, "source_ids": list(claim.source_ids)}
                for claim in report.claims
            ],
        }
        result = ReportAgent(llm_provider=self._llm_provider).run("仅确认以下不可变报告草稿，不得改写：" + json.dumps(draft, ensure_ascii=False))
        if not result.success or not isinstance(result.answer, str) or not result.answer.strip():
            raise ValueError("ReportAgent 未确认不可变报告草稿")
        summary = {"report_version": report.report_version, "claim_count": len(report.claims), "review_status": report.review_status.value, "acknowledged": True}
        return (), {"agent_name": "ReportAgent", "status": "succeeded", "result_summary": {"total_steps": result.total_steps, **summary}}, summary

    def _calculate(
        self, plan
    ) -> tuple[tuple[dict[str, Any], ...], dict[str, Any], Mapping[str, Any]]:
        """只使用计划中已批准的 calculator 参数运行 CalcAgent。"""
        binding = plan.binding_for("calculate")
        params = plan.input_for("calculate")
        if binding is None or binding.agent_name != "CalcAgent" or tuple(binding.tool_names) != ("calculator",):
            raise ValueError("calculate 步骤必须精确绑定 CalcAgent + calculator")
        if self._llm_provider is None or self._tool_registry is None or not isinstance(params, Mapping):
            raise ValueError("CalcAgent 缺少已批准输入或运行依赖")
        calculator = self._tool_registry.get("calculator")
        if calculator is None:
            raise ValueError("CalcAgent 缺少 calculator 工具")
        from src.worker_agents.calc_agent import CalcAgent
        result = CalcAgent(calculator_tool=calculator, llm_provider=self._llm_provider, allow_retrieve=False).run(
            "仅调用 calculator 工具，并严格使用以下已批准参数：" + json.dumps(params, ensure_ascii=False)
        )
        calculation_step = next(
            (item for item in result.reasoning_chain if item.get("action") == "calculator"),
            None,
        )
        observation = calculation_step.get("observation") if isinstance(calculation_step, Mapping) else None
        if not result.success or not isinstance(observation, str):
            raise ValueError("CalcAgent 未实际调用 calculator")
        if calculation_step.get("action_input") != dict(params):
            raise ValueError("CalcAgent 使用了未批准的计算参数")
        try:
            data = json.loads(observation)
        except json.JSONDecodeError as exc:
            raise ValueError("CalcAgent 计算结果不是结构化数据") from exc
        if not isinstance(data, Mapping) or "error" in data:
            raise ValueError("CalcAgent 计算失败")
        summary = {"operation": params.get("operation"), "result_present": True}
        return (
            ({"tool_name": "calculator", "status": "succeeded", "result_summary": summary},),
            {"agent_name": "CalcAgent", "status": "succeeded", "result_summary": {"total_steps": result.total_steps, **summary}},
            summary,
        )

    def _compare(
        self, plan
    ) -> tuple[tuple[dict[str, Any], ...], dict[str, Any], Mapping[str, Any]]:
        """只使用计划中已批准的 compare 参数运行 CompareAgent。"""
        binding = plan.binding_for("compare")
        params = plan.input_for("compare")
        if binding is None or binding.agent_name != "CompareAgent" or tuple(binding.tool_names) != ("compare",):
            raise ValueError("compare 步骤必须精确绑定 CompareAgent + compare")
        if self._llm_provider is None or self._tool_registry is None or not isinstance(params, Mapping):
            raise ValueError("CompareAgent 缺少已批准输入或运行依赖")
        compare_tool = self._tool_registry.get("compare")
        if compare_tool is None:
            raise ValueError("CompareAgent 缺少 compare 工具")
        from src.worker_agents.compare_agent import CompareAgent
        result = CompareAgent(compare_tool=compare_tool, llm_provider=self._llm_provider, allow_retrieve=False).run(
            "仅调用 compare 工具，并严格使用以下已批准参数：" + json.dumps(params, ensure_ascii=False)
        )
        comparison_step = next(
            (item for item in result.reasoning_chain if item.get("action") == "compare"), None
        )
        observation = comparison_step.get("observation") if isinstance(comparison_step, Mapping) else None
        if not result.success or not isinstance(observation, str):
            raise ValueError("CompareAgent 未实际调用 compare")
        if comparison_step.get("action_input") != dict(params):
            raise ValueError("CompareAgent 使用了未批准的对比参数")
        try:
            data = json.loads(observation)
        except json.JSONDecodeError as exc:
            raise ValueError("CompareAgent 对比结果不是结构化数据") from exc
        if not isinstance(data, Mapping) or "error" in data:
            raise ValueError("CompareAgent 对比失败")
        summary = {"metric": params["metric"], "result_present": True}
        return (
            ({"tool_name": "compare", "status": "succeeded", "result_summary": summary},),
            {"agent_name": "CompareAgent", "status": "succeeded", "result_summary": {"total_steps": result.total_steps, **summary}},
            summary,
        )

    def _chart(self, plan) -> tuple[tuple[dict[str, Any], ...], dict[str, Any], Mapping[str, Any]]:
        """只使用计划中已批准的图表参数运行 ChartAgent。"""
        binding = plan.binding_for("chart")
        params = plan.input_for("chart")
        if binding is None or binding.agent_name != "ChartAgent" or tuple(binding.tool_names) != ("chart",):
            raise ValueError("chart 步骤必须精确绑定 ChartAgent + chart")
        if self._llm_provider is None or self._tool_registry is None or not isinstance(params, Mapping):
            raise ValueError("ChartAgent 缺少已批准输入或运行依赖")
        chart_tool = self._tool_registry.get("chart")
        if chart_tool is None:
            raise ValueError("ChartAgent 缺少 chart 工具")
        from src.worker_agents.chart_agent import ChartAgent
        result = ChartAgent(chart_tool=chart_tool, llm_provider=self._llm_provider).run("仅调用 chart 工具，并严格使用以下已批准参数：" + json.dumps(params, ensure_ascii=False))
        step = next((item for item in result.reasoning_chain if item.get("action") == "chart"), None)
        observation = step.get("observation") if isinstance(step, Mapping) else None
        if not result.success or not isinstance(observation, str) or step.get("action_input") != dict(params):
            raise ValueError("ChartAgent 未使用已批准参数实际调用 chart")
        try:
            data = json.loads(observation)
        except json.JSONDecodeError as exc:
            raise ValueError("ChartAgent 图表结果不是结构化数据") from exc
        if not isinstance(data, Mapping) or "error" in data:
            raise ValueError("ChartAgent 图表失败")
        summary = {"chart_type": params["chart_type"], "result_present": True}
        return (({"tool_name": "chart", "status": "succeeded", "result_summary": summary},), {"agent_name": "ChartAgent", "status": "succeeded", "result_summary": {"total_steps": result.total_steps, **summary}}, summary)

    def _commit_step(
        self,
        task_id: str,
        step_id: str,
        dag_step_ids: tuple[str, ...],
        dependency_versions: dict[str, str],
        actor: str,
        *,
        artifact_ids: tuple[str, ...],
        step_trace: dict[str, Any] | None = None,
        tool_calls: tuple[dict[str, Any], ...] = (),
        worker_call: dict[str, Any] | None = None,
        report: ResearchReport | None = None,
    ) -> None:
        claim = self._adapter.claim_step(task_id, step_id, f"{actor}:{task_id}:{step_id}")
        snapshot = self._adapter.task_snapshot(task_id)
        result = self._adapter.commit_step(
            task_id,
            step_id,
            claim.attempt.attempt_token,
            claim.attempt.owner_token,
            snapshot.revision,
            dag_step_ids=dag_step_ids,
            dependency_versions=dependency_versions,
            invocation={
                        "idempotency_key": f"research-execution:{task_id}:{step_id}",
                        "status": "succeeded",
                        "actor": actor,
                        **({"step_trace": step_trace} if step_trace is not None else {}),
                        **({"tool_calls": list(tool_calls)} if tool_calls else {}),
                        **({"worker_call": worker_call} if worker_call is not None else {}),
            },
            artifact_ids=artifact_ids,
            on_commit=(lambda connection: self._reports.append_in_transaction(connection, report)) if report is not None else None,
            completion_command_id=f"research-execution:complete:{task_id}" if report is not None else None,
            completion_actor=actor if report is not None else None,
        )
        if result.status != "completed":
            raise RuntimeError(f"步骤 {step_id} 的提交未被接受")

    def _retrieve(
        self, plan
    ) -> tuple[Mapping[str, Any], tuple[dict[str, Any], ...], dict[str, Any] | None]:
        """执行检索；绑定工具的计划只走 ToolRegistry，历史计划保持原路径。"""
        binding = plan.binding_for("retrieve")
        if binding is None or not binding.tool_names:
            return self._query(plan.objective), (), None
        if tuple(binding.tool_names) != ("retrieve",):
            raise ValueError("当前研究执行器仅支持绑定 retrieve 工具")
        if self._tool_registry is None:
            raise ValueError("绑定检索工具尚未装配 ToolRegistry")
        if binding.agent_name == "DataAgent" and self._llm_provider is not None:
            return self._retrieve_via_data_agent(plan)

        result = self._tool_registry.execute("retrieve", query=plan.objective)
        if not result.success or not isinstance(result.data, Mapping):
            raise ValueError("绑定检索工具调用失败")
        query_result = self._tool_result_to_query_result(result.data)
        return query_result, (
            {
                "tool_name": "retrieve",
                "status": "succeeded",
                "result_summary": {
                    "source_count": len(self._source_ids(query_result)),
                    "answer_present": bool(query_result.get("answer")),
                },
            },
        ), None

    def _retrieve_via_data_agent(
        self, plan
    ) -> tuple[Mapping[str, Any], tuple[dict[str, Any], ...], dict[str, Any]]:
        """通过已绑定的 DataAgent 执行检索，复用受控注册表中的 retrieve 工具。"""
        from src.worker_agents.data_agent import DataAgent

        retrieval_tool = self._tool_registry.get("retrieve") if self._tool_registry else None
        if retrieval_tool is None:
            raise ValueError("DataAgent 缺少已注册的 retrieve 工具")
        worker_result = DataAgent(
            retrieval_tool=retrieval_tool,
            llm_provider=self._llm_provider,
        ).run(self._data_agent_query(plan))
        if not worker_result.success:
            raise ValueError("DataAgent 检索执行失败")
        query_result = self._worker_result_to_query_result(worker_result.answer, worker_result.sources)
        if not self._source_ids(query_result):
            raise ValueError("DataAgent 检索未返回可审计来源")
        source_count = len(self._source_ids(query_result))
        tool_calls = (
            {
                "tool_name": "retrieve",
                "status": "succeeded",
                "result_summary": {
                    "source_count": source_count,
                    "answer_present": bool(query_result.get("answer")),
                },
            },
        )
        worker_call = {
            "agent_name": "DataAgent",
            "status": "succeeded",
            "result_summary": {
                "total_steps": worker_result.total_steps,
                "source_count": source_count,
                "answer_present": bool(query_result.get("answer")),
            },
        }
        return query_result, tool_calls, worker_call

    @staticmethod
    def _data_agent_query(plan) -> str:
        """将已审批的研究范围明确传给 DataAgent，避免只凭泛化目标检索。"""
        scope = "；".join(plan.scope)
        return f"{plan.objective}\n已审批研究范围：{scope}"

    @staticmethod
    def _worker_result_to_query_result(
        answer: Any, raw_sources: Any
    ) -> Mapping[str, Any]:
        """将 DataAgent 的来源结构转换为研究报告可引用的来源。"""
        sources: list[dict[str, Any]] = []
        if isinstance(raw_sources, list):
            for item in raw_sources:
                if not isinstance(item, Mapping):
                    continue
                source_file = item.get("source", item.get("source_file"))
                pages = item.get("physical_pages", item.get("pages"))
                if not isinstance(source_file, str) or not source_file.strip():
                    continue
                sources.append({
                    "source_file": source_file,
                    "pages": pages if isinstance(pages, list) else [],
                    "source_text": item.get("verification_text", item.get("content", "")),
                })
        return {
            "answer": answer.strip() if isinstance(answer, str) else "",
            "sources": sources,
        }

    @staticmethod
    def _tool_result_to_query_result(data: Mapping[str, Any]) -> Mapping[str, Any]:
        """将 RetrieveTool 的结构化结果转换为研究报告所需的来源引用。"""
        raw_results = data.get("results")
        if not isinstance(raw_results, list):
            return {"answer": "", "sources": []}
        sources: list[dict[str, Any]] = []
        answer = ""
        for item in raw_results:
            if not isinstance(item, Mapping):
                continue
            source_file = item.get("source_file")
            pages = item.get("physical_pages", item.get("pages"))
            text = item.get("text")
            if not isinstance(source_file, str) or not source_file.strip():
                continue
            if not isinstance(pages, list):
                pages = []
            sources.append({"source_file": source_file, "pages": pages})
            sources[-1]["source_text"] = text if isinstance(text, str) else ""
            if not answer and isinstance(text, str) and text.strip():
                answer = text.strip()
        return {"answer": answer, "sources": sources}

    def _review(
        self, plan, query_result: Mapping[str, Any]
    ) -> tuple[Mapping[str, Any] | None, tuple[dict[str, Any], ...], dict[str, Any] | None]:
        """执行绑定 VerifyAgent 审核；未装配 Worker 时保留旧步骤检查语义。"""
        binding = plan.binding_for("review")
        if binding is None or self._llm_provider is None:
            return None, (), None
        if binding.agent_name != "VerifyAgent" or tuple(binding.tool_names) != ("verify",):
            raise ValueError("当前研究执行器仅支持 VerifyAgent 的精确 verify 审核绑定")
        if self._tool_registry is None:
            raise ValueError("VerifyAgent 审核尚未装配 ToolRegistry")
        verify_tool = self._tool_registry.get("verify")
        if verify_tool is None:
            raise ValueError("VerifyAgent 缺少已注册的 verify 工具")
        answer = query_result.get("answer")
        sources = query_result.get("sources")
        source_texts: list[str] = []
        if isinstance(sources, list):
            for source in sources:
                if isinstance(source, Mapping) and isinstance(source.get("source_text"), str):
                    text = source["source_text"].strip()
                    if text and text not in source_texts:
                        source_texts.append(text)
        source_text = "\n\n".join(source_texts)
        if not isinstance(answer, str) or not answer.strip() or not source_text:
            raise ValueError("VerifyAgent 审核缺少声明或来源正文")

        class _BoundVerifyTool(BaseTool):
            """将审核输入固定为本次执行上下文，避免 Worker 改写声明或来源。"""

            name = verify_tool.name
            description = verify_tool.description
            parameters = getattr(verify_tool, "parameters", {})

            def run(self, **_kwargs):
                return verify_tool.run(claim=answer.strip(), source_text=source_text)

        from src.worker_agents.verify_agent import VerifyAgent

        worker_result = VerifyAgent(
            verify_tool=_BoundVerifyTool(),
            llm_provider=self._llm_provider,
            allow_retrieve=False,
        ).run(
            "审核以下声明是否被来源支持。仅调用 verify 工具，"
            f"claim={answer.strip()}\nsource_text={source_text}"
        )
        if not worker_result.success:
            raise ValueError("VerifyAgent 审核执行失败")
        audit = self._verify_audit_from_worker_result(worker_result.reasoning_chain)
        if audit is None:
            raise ValueError("VerifyAgent 未实际调用 verify 工具")
        if audit["valid"] is not True:
            raise ValueError("VerifyAgent 审核未通过或无有效结论")
        summary = {
            "valid": audit["valid"],
            "confidence": audit["confidence"],
            "total_claims": audit["total_claims"],
            "matched_count": audit["matched_count"],
            "mismatched_count": audit["mismatched_count"],
        }
        tool_calls = ({"tool_name": "verify", "status": "succeeded", "result_summary": summary},)
        worker_call = {
            "agent_name": "VerifyAgent",
            "status": "succeeded",
            "result_summary": {"total_steps": worker_result.total_steps, **summary},
        }
        return summary, tool_calls, worker_call

    @staticmethod
    def _verify_audit_from_worker_result(reasoning_chain: Any) -> Mapping[str, Any] | None:
        """从实际 verify 工具的观察值提取并校验结构化审核结论。"""
        if not isinstance(reasoning_chain, list):
            return None
        for step in reversed(reasoning_chain):
            if not isinstance(step, Mapping) or step.get("action") != "verify":
                continue
            observation = step.get("observation")
            if not isinstance(observation, str):
                return None
            try:
                data = json.loads(observation)
            except json.JSONDecodeError:
                return None
            if not isinstance(data, Mapping) or not isinstance(data.get("valid"), bool):
                return None
            confidence = data.get("confidence")
            counts = tuple(data.get(name) for name in ("total_claims", "matched_count", "mismatched_count"))
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                return None
            if any(isinstance(count, bool) or not isinstance(count, int) for count in counts):
                return None
            return {
                "valid": data["valid"],
                "confidence": confidence,
                "total_claims": counts[0],
                "matched_count": counts[1],
                "mismatched_count": counts[2],
            }
        return None

    def _validate_bindings(self, plan) -> None:
        """按 AgentRegistry 校验新计划；无绑定的历史计划保持兼容。"""
        if not plan.step_bindings:
            return
        if self._agent_registry is None:
            raise ValueError("研究计划 Agent 绑定尚未装配 AgentRegistry")
        for binding in plan.step_bindings:
            capability = self._agent_registry.get(binding.agent_name)
            if capability is None:
                raise ValueError(f"Agent {binding.agent_name} 未注册")
            unauthorized = sorted(set(binding.tool_names) - set(capability.tools))
            if unauthorized:
                raise ValueError(
                    f"Agent {binding.agent_name} 的工具未获授权: {', '.join(unauthorized)}"
                )

    @staticmethod
    def _step_trace(
        plan,
        step_id: str,
        *,
        query_result: Mapping[str, Any] | None,
        calculation_result: Mapping[str, Any] | None,
        comparison_result: Mapping[str, Any] | None,
        chart_result: Mapping[str, Any] | None,
        review_result: Mapping[str, Any] | None,
        report: ResearchReport | None,
        plan_result: Mapping[str, Any] | None = None,
        report_result: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """只保存稳定标识和脱敏统计，不把外部响应正文写入调用账本。"""
        binding = plan.binding_for(step_id)
        if binding is None:
            return None
        if step_id == "plan" and plan_result is not None:
            result_summary = dict(plan_result)
        elif step_id == "retrieve":
            answer = (query_result or {}).get("answer")
            result_summary = {
                "source_count": len(ResearchTaskExecutor._source_ids(query_result or {})),
                "answer_present": bool(isinstance(answer, str) and answer.strip()),
            }
        elif step_id == "calculate" and calculation_result is not None:
            result_summary = dict(calculation_result)
        elif step_id == "compare" and comparison_result is not None:
            result_summary = dict(comparison_result)
        elif step_id == "chart" and chart_result is not None:
            result_summary = dict(chart_result)
        elif step_id == "report" and report is not None:
            result_summary = report_result if report_result is not None else {
                "report_id": report.report_id,
                "claim_count": len(report.claims),
                "review_status": report.review_status.value,
            }
        elif step_id == "review" and review_result is not None:
            result_summary = {
                "source_count": len(ResearchTaskExecutor._source_ids(query_result or {})),
                "reviewed": True,
                "valid": review_result["valid"],
                "confidence": review_result["confidence"],
            }
        elif step_id == "review":
            result_summary = {
                "source_count": len(ResearchTaskExecutor._source_ids(query_result or {})),
                "reviewed": False,
            }
        else:
            result_summary = {"planned_step_count": len(plan.step_ids)}
        return {
            "step_id": step_id,
            "agent_name": binding.agent_name,
            "tool_names": list(binding.tool_names),
            "status": "succeeded",
            "result_summary": result_summary,
        }

    def _append_report(self, task_id: str, plan_id: str, query_result: Mapping[str, Any]) -> ResearchReport:
        sources = self._source_ids(query_result)
        answer = query_result.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("检索未返回有效回答，不能生成研究报告")
        latest = self._reports.latest_for_task(task_id)
        version = 1 if latest is None else latest.report_version + 1
        report = ResearchReport.create(
            report_id=f"research-report:{task_id}:{version}",
            task_id=task_id,
            plan_id=plan_id,
            report_version=version,
            data_version=f"research-execution:{task_id}:{version}",
            review_status=ReportReviewStatus.PENDING_REVIEW,
            claims=(
                Claim.create(
                    claim_id=f"research-claim:{task_id}:{version}:1",
                    text=answer,
                    support_kind=ClaimSupportKind.SOURCE,
                    source_ids=sources,
                ),
            ),
        )
        return report

    @staticmethod
    def _source_ids(query_result: Mapping[str, Any]) -> tuple[str, ...]:
        sources = query_result.get("sources")
        if not isinstance(sources, list):
            return ()
        source_ids: list[str] = []
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            source_file = source.get("source_file")
            pages = source.get("pages")
            if not isinstance(source_file, str) or not source_file.strip():
                continue
            page_text = ",".join(str(page) for page in pages) if isinstance(pages, list) else ""
            digest = hashlib.sha256(f"{source_file.strip()}:{page_text}".encode("utf-8")).hexdigest()[:16]
            source_ids.append(f"source:{digest}")
        return tuple(dict.fromkeys(source_ids))

    def _fail(self, task_id: str, expected_revision: int, actor: str, *, reason: str = "执行任务失败") -> ResearchTaskSnapshot:
        failure = self._adapter.failure_decision("execution_failed", retry_count=0, max_retries=0)
        self._adapter.record_failure(task_id, failure, actor=actor, reason=reason)
        return self._adapter.fail_task(
            task_id,
            expected_revision,
            f"research-execution:failed:{task_id}",
            actor=actor,
        )
