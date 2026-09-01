# -*- coding: utf-8 -*-
"""C2.6 研究任务持久执行的 REST API。

六类端点：创建、查询、事件流、暂停、恢复、取消。
任务状态与 revision 全部来自 C0 可恢复执行内核，本模块不复制状态；
控制端点必须携带 command_id 与 expected_revision，重复 command_id
由 C0 幂等回放原结果，过期 revision 返回 409 与当前 revision。
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from src.durable_execution import (
    DurableExecutionStore,
    InvalidRunTransitionError,
    RevisionConflictError,
)
from src.research_task_adapter import ResearchTaskAdapter, ResearchTaskSnapshot
from src.research_task_events import ResearchTaskEventStream
from src.research_delivery import (
    Claim,
    ClaimSupportKind,
    ReportReviewStatus,
    ResearchPlan,
    ResearchReport,
)
from src.research_plan_repository import ResearchPlanRepository
from src.research_conflict_governance import (
    ResearchConflictApprovalService,
    ResearchConflictContextRepository,
)
from src.research_conflict_review import ConflictReviewAction
from src.research_conflict_review import ResearchConflictReviewStore
from src.governance.approval import ApprovalBinding, ApprovalRequest, GovernanceApprovalStore, SUBJECT_REPORT_SIGNOFF
from src.research_report_repository import ResearchReportRepository
from src.research_report_signoff import ResearchReportSignoffRepository
from src.research_task_submission import ResearchTaskSubmissionRepository
from src.research_task_execution import ResearchTaskExecutor
from src.research_task_retry import ResearchTaskRetryService
from src.agent_registry import AgentRegistry
from src.tools import ToolRegistry
from src.v7_metadata_store import V7MetadataStore
from src.research_identity import ResearchIdentityStore

router = APIRouter(prefix="/api/research", tags=["research-tasks"])

# 事件保留期默认 24 小时；调用方可通过查询参数覆盖
_DEFAULT_RETENTION_SECONDS = 86400

# 模块级执行仓储持有者：测试通过 configure_research_task_store 注入独立实例
_execution_store: DurableExecutionStore | None = None
_research_task_query: Callable[[str], Mapping[str, Any]] | None = None
_research_task_agent_registry: AgentRegistry | None = None
_research_task_tool_registry: ToolRegistry | None = None
_research_task_llm_provider: Any | None = None


class ResearchStepBindingRequest(BaseModel):
    """研究步骤绑定的客户端输入；Agent 能力由服务端注册表决定。"""

    agent_name: str = Field(min_length=1)
    tool_names: list[str] = Field(default_factory=list)


class CreateTaskRequest(BaseModel):
    """创建研究任务请求体。"""

    task_id: str = Field(min_length=1)
    dag_step_ids: list[str] = Field(min_length=1)
    objective: str | None = None
    scope: list[str] | None = None
    estimated_cost: str | int | float | None = None
    risks: list[str] | None = None
    step_bindings: dict[str, ResearchStepBindingRequest] | None = None
    step_inputs: dict[str, dict[str, Any]] | None = None


class TaskCommandRequest(BaseModel):
    """研究任务控制命令请求体，必须携带幂等命令 ID 与期望 revision。"""

    command_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)


class LegacyTaskDispositionRequest(TaskCommandRequest):
    """遗留任务处置必须保留明确原因，不能静默清除状态。"""

    reason: str = Field(min_length=1, max_length=500)


class CreateReportClaimRequest(BaseModel):
    """创建报告时允许提交的单条声明输入。"""

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    support_kind: ClaimSupportKind
    fact_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    analysis_label: str | None = None


class CreateReportRequest(BaseModel):
    """创建不可变报告的最小输入；身份、版本和审核状态由服务端确定。"""

    data_version: str = Field(min_length=1)
    claims: list[CreateReportClaimRequest] = Field(min_length=1)


class GrantConflictApprovalRequest(BaseModel):
    """审批授予输入；审批主体和版本绑定只能由服务端确定。"""

    model_config = ConfigDict(extra="forbid")

    action: ConflictReviewAction
    selected_fact_id: str | None = None
    expires_in_seconds: int = Field(gt=0, le=86400)


class ResolveConflictRequest(BaseModel):
    """裁决输入；审批主体与版本绑定由服务端读取。"""
    model_config = ConfigDict(extra="forbid")
    action: ConflictReviewAction
    selected_fact_id: str | None = None
    approval_id: str | None = None


class GrantReportSignoffApprovalRequest(BaseModel):
    """正式报告签发审批的唯一客户端输入是有效期。"""

    model_config = ConfigDict(extra="forbid")
    expires_in_seconds: int = Field(gt=0, le=86400)


class SignoffReportRequest(BaseModel):
    """签发仅引用服务端已经授予的单次审批。"""

    model_config = ConfigDict(extra="forbid")
    approval_id: str = Field(min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


def configure_research_task_store(execution_store: DurableExecutionStore) -> None:
    """注入执行仓储；供测试与装配方使用。"""
    global _execution_store
    _execution_store = execution_store


def configure_research_task_query(query: Callable[[str], Mapping[str, Any]]) -> None:
    """注入批准任务使用的真实检索函数，避免研究模块依赖 API 服务全局变量。"""
    global _research_task_query
    _research_task_query = query


def configure_research_task_agent_registry(registry: AgentRegistry | None) -> None:
    """装配现有 AgentRegistry，供研究步骤绑定校验复用。"""
    global _research_task_agent_registry
    _research_task_agent_registry = registry


def configure_research_task_tool_registry(registry: ToolRegistry | None) -> None:
    """装配既有工具注册表，供绑定步骤执行实际工具调用。"""
    global _research_task_tool_registry
    _research_task_tool_registry = registry


def configure_research_task_llm_provider(provider: Any | None) -> None:
    """装配共享 LLMProvider，供已绑定的 Worker 步骤实际运行。"""
    global _research_task_llm_provider
    _research_task_llm_provider = provider


def _execution_store_or_default() -> DurableExecutionStore:
    """返回注入的仓储；未注入时惰性绑定默认 V7 元数据库。"""
    global _execution_store
    if _execution_store is None:
        v7_root = Path(__file__).resolve().parent.parent / "data" / "v7"
        _execution_store = DurableExecutionStore(V7MetadataStore(v7_root / "metadata.sqlite3"))
    return _execution_store


def _adapter() -> ResearchTaskAdapter:
    return ResearchTaskAdapter(_execution_store_or_default())


def _plan_repository() -> ResearchPlanRepository:
    return ResearchPlanRepository(_execution_store_or_default().metadata_store)


def _report_repository() -> ResearchReportRepository:
    return ResearchReportRepository(_execution_store_or_default().metadata_store)


def _report_signoff_repository() -> ResearchReportSignoffRepository:
    return ResearchReportSignoffRepository(_execution_store_or_default().metadata_store)


def _identity_store() -> ResearchIdentityStore:
    return ResearchIdentityStore(_execution_store_or_default().metadata_store)


def _submission_repository() -> ResearchTaskSubmissionRepository:
    return ResearchTaskSubmissionRepository(_execution_store_or_default().metadata_store)


def _task_executor() -> ResearchTaskExecutor:
    if _research_task_query is None:
        raise RuntimeError("研究任务执行器尚未装配检索函数")
    return ResearchTaskExecutor(
        _adapter(),
        _plan_repository(),
        _report_repository(),
        query=_research_task_query,
        agent_registry=_research_task_agent_registry,
        tool_registry=_research_task_tool_registry,
        llm_provider=_research_task_llm_provider,
    )


def _session_identity(request: Request):
    return _identity_store().identity(request.cookies.get("research_session"))


def _configured_approval_authority(request: Request) -> str:
    """只接受当前 HttpOnly 会话中的 approver 角色，不信任客户端声明。"""
    identity = _session_identity(request)
    if identity is None:
        raise HTTPException(status_code=401, detail={"message": "审批操作需要登录"})
    if "approver" not in identity.roles:
        raise HTTPException(status_code=403, detail={"message": "当前用户没有审批权限"})
    return identity.username


def _configured_researcher(request: Request) -> str:
    """创建研究任务只接受当前会话中的 researcher 角色。"""
    identity = _session_identity(request)
    if identity is None:
        raise HTTPException(status_code=401, detail={"message": "提交研究任务需要登录"})
    if "researcher" not in identity.roles:
        raise HTTPException(status_code=403, detail={"message": "当前用户没有提交研究任务权限"})
    return identity.username


@router.post("/auth/login", summary="研究工作台登录")
def research_login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    result = _identity_store().login(payload.username, payload.password)
    if result is None:
        raise HTTPException(status_code=401, detail={"message": "用户名或密码错误"})
    token, identity = result
    response.set_cookie(
        "research_session", token, httponly=True, samesite="strict",
        secure=os.getenv("RESEARCH_SESSION_COOKIE_SECURE", "true").lower() == "true",
        max_age=28800,
    )
    return {"username": identity.username, "roles": list(identity.roles)}


@router.get("/auth/me", summary="读取当前研究身份")
def research_current_identity(http_request: Request) -> dict[str, Any]:
    identity = _session_identity(http_request)
    if identity is None:
        raise HTTPException(status_code=401, detail={"message": "未登录"})
    return {"user_id": identity.user_id, "username": identity.username, "roles": list(identity.roles)}


@router.post("/auth/logout", summary="退出研究登录")
def research_logout(http_request: Request, response: Response) -> dict[str, bool]:
    _identity_store().logout(http_request.cookies.get("research_session"))
    response.delete_cookie("research_session")
    return {"ok": True}


def _plan_payload(plan: ResearchPlan) -> dict[str, Any]:
    payload = {
        "plan_id": plan.plan_id,
        "task_id": plan.task_id,
        "objective": plan.objective,
        "scope": list(plan.scope),
        "step_ids": list(plan.step_ids),
        "estimated_cost": str(plan.estimated_cost),
        "risks": list(plan.risks),
        "plan_version": plan.plan_version,
    }
    if plan.step_bindings:
        payload["step_bindings"] = {
            binding.step_id: {
                "agent_name": binding.agent_name,
                "tool_names": list(binding.tool_names),
            }
            for binding in plan.step_bindings
        }
    if plan.step_inputs:
        payload["step_inputs"] = {
            item.step_id: plan.input_for(item.step_id)
            for item in plan.step_inputs
        }
    return payload


def _report_payload(report: ResearchReport) -> dict[str, Any]:
    """将不可变报告转换为 API 公开载荷，不补全任何缺失依据。"""
    return {
        "report_id": report.report_id,
        "task_id": report.task_id,
        "plan_id": report.plan_id,
        "report_version": report.report_version,
        "data_version": report.data_version,
        "review_status": report.review_status.value,
        "claims": [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "support_kind": claim.support_kind.value,
                "fact_ids": list(claim.fact_ids),
                "calculation_ids": list(claim.calculation_ids),
                "source_ids": list(claim.source_ids),
                "analysis_label": claim.analysis_label,
            }
            for claim in report.claims
        ],
    }


def _report_signoff_binding(task_id: str, report: ResearchReport) -> tuple[str, ApprovalBinding, dict[str, Any]]:
    """从当前任务、持久化计划和报告快照派生签发审批绑定。"""
    snapshot = _adapter().task_snapshot(task_id)
    plan = _plan_repository().current_for_task(task_id)
    if plan is None:
        raise HTTPException(status_code=409, detail={"message": "任务尚未持久化研究计划"})
    plan_hash = hashlib.sha256(json.dumps(_plan_payload(plan), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    binding = ApprovalBinding(
        task_revision=snapshot.revision,
        plan_hash=plan_hash,
        fact_version=report.data_version,
        artifact_version=report.report_id,
        index_generation=report.data_version,
    )
    return snapshot.run_id, binding, {"report_id": report.report_id, "report_version": report.report_version, "data_version": report.data_version}


def _has_unresolved_critical_conflicts(task_id: str) -> bool:
    """可信上下文中的待审核冲突只有显式批准或驳回后才视为已裁决。"""
    store = _execution_store_or_default()
    from src.financial_fact_conflict_repository import FinancialFactConflictRepository

    conflicts = FinancialFactConflictRepository(store.metadata_store)
    reviews = ResearchConflictReviewStore(store.metadata_store, clock=lambda: datetime.now(timezone.utc))
    for context in ResearchConflictContextRepository(store.metadata_store).current_for_task(task_id):
        conflict = conflicts.get(context.conflict_id)
        if conflict is None or conflict.status != "pending_review":
            continue
        history = tuple(record for record in reviews.history(context.conflict_id) if record.task_id == task_id)
        if not history or history[-1].action is ConflictReviewAction.KEEP_PENDING:
            return True
    return False


def _snapshot_payload(snapshot: ResearchTaskSnapshot) -> dict[str, Any]:
    plan = _plan_repository().current_for_task(snapshot.task_id)
    dag_step_ids = list(snapshot.dag_step_ids)
    if not dag_step_ids and plan is not None:
        # 列表重建快照时 C0 不携带创建参数，从已持久化计划恢复 DAG 展示信息。
        dag_step_ids = list(plan.step_ids)
    payload = {
        "task_id": snapshot.task_id,
        "run_id": snapshot.run_id,
        "status": snapshot.status,
        "revision": snapshot.revision,
        "dag_step_ids": dag_step_ids,
    }
    if plan is not None:
        payload["plan"] = _plan_payload(plan)
    submission = _submission_repository().current_for_task(snapshot.task_id)
    if submission is not None:
        payload["submission"] = {
            "status": submission.status,
            "requester": submission.requester,
            "reviewer": submission.reviewer,
        }
    return payload


def _execution_summary_payload(task_id: str) -> dict[str, Any]:
    """从既有 C0 检查点和只追加失败决策构造只读执行摘要。"""
    snapshot = _adapter().task_snapshot(task_id)
    plan = _plan_repository().current_for_task(task_id)
    recovery = _execution_store_or_default().recovery_plan(snapshot.run_id)
    step_ids = tuple(plan.step_ids) if plan is not None else snapshot.dag_step_ids
    completed_step_set = {item.step_id for item in recovery.checkpoint_records}
    completed_step_ids = [step_id for step_id in step_ids if step_id in completed_step_set]
    completed_step_ids.extend(sorted(completed_step_set.difference(completed_step_ids)))
    current_step_id = None
    if snapshot.status == "running":
        current_step_id = next((step_id for step_id in step_ids if step_id not in completed_step_ids), None)

    failure_reason = None
    if snapshot.status == "failed":
        for decision in reversed(_adapter().route_decisions(task_id)):
            if decision.decision_type == "failure":
                reason = decision.detail.get("reason")
                if isinstance(reason, str) and reason.strip():
                    failure_reason = reason
                break

    completed_at = None
    if snapshot.status == "completed":
        with _execution_store_or_default().metadata_store.connect() as connection:
            row = connection.execute(
                "SELECT updated_at FROM v7_execution_runs WHERE run_id=?",
                (snapshot.run_id,),
            ).fetchone()
        completed_at = row[0] if row is not None else None
    payload = {
        "completed_step_ids": completed_step_ids,
        "current_step_id": current_step_id,
        "completed_at": completed_at,
        "failure_reason": failure_reason,
    }
    if plan is not None and plan.step_bindings:
        traces_by_step: dict[str, dict[str, Any]] = {}
        for invocation in recovery.invocation_records:
            trace = invocation.details.get("step_trace")
            if not isinstance(trace, Mapping):
                continue
            step_id = trace.get("step_id")
            agent_name = trace.get("agent_name")
            tool_names = trace.get("tool_names")
            status = trace.get("status")
            result_summary = trace.get("result_summary")
            if not isinstance(step_id, str) or not isinstance(agent_name, str):
                continue
            if not isinstance(tool_names, list) or not all(isinstance(item, str) for item in tool_names):
                continue
            if not isinstance(status, str) or not isinstance(result_summary, Mapping):
                continue
            traces_by_step[step_id] = {
                "step_id": step_id,
                "agent_name": agent_name,
                "tool_names": tool_names,
                "status": status,
                "result_summary": dict(result_summary),
            }
        payload["step_traces"] = [
            traces_by_step[step_id]
            for step_id in step_ids
            if step_id in traces_by_step
        ]
    return payload


def _control_transition(
    task_id: str,
    action: str,
    request: TaskCommandRequest,
) -> dict[str, Any]:
    """执行控制命令并统一映射 C0 异常到 HTTP 语义。"""
    try:
        if action == "pause":
            snapshot = _adapter().pause_task(
                task_id, request.expected_revision, request.command_id, actor="api"
            )
        elif action == "resume":
            snapshot = _adapter().resume_task(
                task_id, request.expected_revision, request.command_id, actor="api"
            )
        else:
            snapshot = _adapter().cancel_task(
                task_id, request.expected_revision, request.command_id, actor="api"
            )
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    except RevisionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "current_revision": exc.current_revision},
        )
    except InvalidRunTransitionError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)})
    return _snapshot_payload(snapshot)


@router.post("/tasks", summary="提交研究任务")
def create_task(request: CreateTaskRequest, http_request: Request) -> dict[str, Any]:
    """在 C0 创建 pending 运行，DAG 步骤由调用方按 C1 检查点协议保存。"""
    plan_fields = (request.objective, request.scope, request.estimated_cost)
    if (any(value is not None for value in plan_fields) or request.step_bindings is not None or request.step_inputs is not None) and not all(value is not None for value in plan_fields):
        raise HTTPException(status_code=422, detail={"message": "计划必须同时提供 objective、scope 和 estimated_cost"})
    requester = _configured_researcher(http_request)
    try:
        snapshot = _adapter().create_task(request.task_id, request.dag_step_ids)
        if all(value is not None for value in plan_fields):
            plan = ResearchPlan.create(
                plan_id=f"research-plan:{request.task_id}:1",
                task_id=request.task_id,
                objective=request.objective,
                scope=request.scope,
                step_ids=request.dag_step_ids,
                estimated_cost=request.estimated_cost,
                risks=request.risks or (),
                step_bindings=(
                    {step_id: binding.model_dump() for step_id, binding in request.step_bindings.items()}
                    if request.step_bindings is not None
                    else None
                ),
                step_inputs=request.step_inputs,
            )
            _plan_repository().append(plan)
        _submission_repository().submit(snapshot.task_id, requester)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail={"message": "任务已存在"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    return _snapshot_payload(snapshot)


@router.post("/tasks/{task_id}/submission/approve", summary="批准研究任务并启动执行")
def approve_task_submission(task_id: str, request: TaskCommandRequest, http_request: Request, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """审批后先启动 C0，再由后台执行器完成可审计计划。"""
    reviewer = _configured_approval_authority(http_request)
    try:
        current = _adapter().task_snapshot(task_id)
        if current.revision != request.expected_revision:
            raise RevisionConflictError(current.revision)
        submission = _submission_repository().current_for_task(task_id)
        if submission is None or submission.status != "submitted":
            raise ValueError("任务当前不处于待审批状态")
        snapshot = _adapter().start_task(task_id, request.expected_revision, request.command_id, actor=reviewer)
        _submission_repository().decide(task_id, "approved", reviewer)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    except RevisionConflictError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc), "current_revision": exc.current_revision}) from exc
    except (InvalidRunTransitionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    try:
        executor = _task_executor()
    except RuntimeError as exc:
        _adapter().fail_task(task_id, snapshot.revision, f"research-execution:unconfigured:{task_id}", actor=reviewer)
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc
    background_tasks.add_task(executor.execute, task_id, actor=reviewer)
    return _snapshot_payload(snapshot)


@router.post("/tasks/{task_id}/submission/reject", summary="驳回研究任务")
def reject_task_submission(task_id: str, request: TaskCommandRequest, http_request: Request) -> dict[str, Any]:
    """驳回不启动任务，只追加领导决策记录并保留 pending 执行状态。"""
    reviewer = _configured_approval_authority(http_request)
    try:
        snapshot = _adapter().task_snapshot(task_id)
        if snapshot.revision != request.expected_revision:
            raise RevisionConflictError(snapshot.revision)
        _submission_repository().decide(task_id, "rejected", reviewer)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    except RevisionConflictError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc), "current_revision": exc.current_revision}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    return _snapshot_payload(snapshot)


@router.get("/tasks", summary="列出研究任务")
def list_tasks() -> dict[str, list[dict[str, Any]]]:
    """列出研究任务快照，不混入文档处理等其他 C0 运行。"""
    return {"items": [_snapshot_payload(snapshot) for snapshot in _adapter().list_tasks()]}


@router.get("/tasks/{task_id}", summary="查询研究任务快照")
def get_task(task_id: str) -> dict[str, Any]:
    """读取 C0 运行的当前状态与 revision，不复制任务状态。"""
    try:
        snapshot = _adapter().task_snapshot(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    return _snapshot_payload(snapshot)


@router.get("/tasks/{task_id}/execution", summary="查询研究任务只读执行进度")
def get_task_execution_summary(task_id: str) -> dict[str, Any]:
    try:
        return _execution_summary_payload(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})


@router.post("/tasks/{task_id}/legacy-disposition", summary="处置无执行证据的遗留运行任务")
def dispose_legacy_running_task(task_id: str, request: LegacyTaskDispositionRequest, http_request: Request) -> dict[str, Any]:
    """仅 approver 可把没有执行证据的遗留 running 任务安全标记为 failed。"""
    actor = _configured_approval_authority(http_request)
    try:
        snapshot = _adapter().dispose_legacy_running_task(
            task_id,
            request.expected_revision,
            request.command_id,
            actor=actor,
            reason=request.reason,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    except RevisionConflictError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc), "current_revision": exc.current_revision}) from exc
    except (InvalidRunTransitionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    return _snapshot_payload(snapshot)


@router.post("/tasks/{task_id}/retry", summary="从失败研究任务创建重新提交任务")
def retry_failed_task(task_id: str, request: TaskCommandRequest, http_request: Request) -> dict[str, Any]:
    """仅 approver 可复制已失败任务的计划，新的任务必须再次提交审批。"""
    actor = _configured_approval_authority(http_request)
    try:
        snapshot = ResearchTaskRetryService(_adapter()).create_retry(
            task_id,
            request.expected_revision,
            request.command_id,
            actor=actor,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    except RevisionConflictError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc), "current_revision": exc.current_revision}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    return _snapshot_payload(snapshot)


@router.get("/tasks/{task_id}/report", summary="查询任务最新可审计报告")
def get_latest_report(task_id: str) -> dict[str, Any]:
    try:
        _adapter().task_snapshot(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    report = _report_repository().latest_for_task(task_id)
    if report is None:
        raise HTTPException(status_code=404, detail={"message": "报告不存在"})
    return _report_payload(report)


@router.post("/tasks/{task_id}/report", summary="创建任务报告")
def create_report(task_id: str, request: CreateReportRequest) -> dict[str, Any]:
    """从当前持久化计划与声明输入生成只追加的待审核报告版本。"""
    try:
        _adapter().task_snapshot(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})

    plan = _plan_repository().current_for_task(task_id)
    if plan is None:
        raise HTTPException(status_code=409, detail={"message": "任务尚未持久化研究计划"})

    try:
        claims = [
            Claim.create(
                claim_id=item.claim_id,
                text=item.text,
                support_kind=item.support_kind,
                fact_ids=item.fact_ids,
                calculation_ids=item.calculation_ids,
                source_ids=item.source_ids,
                analysis_label=item.analysis_label,
            )
            for item in request.claims
        ]
        latest_report = _report_repository().latest_for_task(task_id)
        report_version = 1 if latest_report is None else latest_report.report_version + 1
        report = ResearchReport.create(
            report_id=f"research-report:{task_id}:{report_version}",
            task_id=task_id,
            plan_id=plan.plan_id,
            report_version=report_version,
            data_version=request.data_version,
            review_status=ReportReviewStatus.PENDING_REVIEW,
            claims=claims,
        )
        _report_repository().append(report)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail={"message": "报告版本已存在"}) from exc
    return _report_payload(report)


@router.post("/tasks/{task_id}/report/signoff/approvals", summary="授予正式报告签发审批")
def grant_report_signoff_approval(task_id: str, payload: GrantReportSignoffApprovalRequest, http_request: Request) -> dict[str, Any]:
    """只允许 approver 为最新报告申请一次与当前快照绑定的签发审批。"""
    approver = _configured_approval_authority(http_request)
    report = _report_repository().latest_for_task(task_id)
    if report is None:
        raise HTTPException(status_code=404, detail={"message": "报告不存在"})
    try:
        run_id, binding, params = _report_signoff_binding(task_id, report)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    now = datetime.now(timezone.utc)
    approval = GovernanceApprovalStore(_execution_store_or_default().metadata_store, clock=lambda: now).grant(
        ApprovalRequest(task_id=task_id, run_id=run_id, subject=SUBJECT_REPORT_SIGNOFF, subject_id=report.report_id, params=params, binding=binding, approver=approver, expires_at=now + timedelta(seconds=payload.expires_in_seconds))
    )
    return {"approval_id": approval.approval_id, "status": approval.status, "report_id": report.report_id}


@router.post("/tasks/{task_id}/report/signoff", summary="正式签发任务最新报告")
def signoff_report(task_id: str, payload: SignoffReportRequest, http_request: Request) -> dict[str, Any]:
    """签发前重建绑定并检查未决冲突，随后原子消费审批并只追加签发记录。"""
    actor = _configured_approval_authority(http_request)
    report = _report_repository().latest_for_task(task_id)
    if report is None:
        raise HTTPException(status_code=404, detail={"message": "报告不存在"})
    if _has_unresolved_critical_conflicts(task_id):
        raise HTTPException(status_code=409, detail={"message": "存在未裁决关键冲突，禁止正式签发报告"})
    try:
        _, binding, params = _report_signoff_binding(task_id, report)
        now = datetime.now(timezone.utc)
        approvals = GovernanceApprovalStore(_execution_store_or_default().metadata_store, clock=lambda: now)
        gate = approvals.check_gate(task_id, SUBJECT_REPORT_SIGNOFF, report.report_id, params, binding)
        if not gate.allowed or gate.approval_id != payload.approval_id:
            raise ValueError("报告签发审批无效、已过期或与当前报告不匹配")
        record = None

        def write(connection) -> None:
            nonlocal record
            record = _report_signoff_repository().append_in_transaction(connection, report_id=report.report_id, task_id=task_id, approval_id=payload.approval_id, actor=actor, now=now)

        approvals.consume_in_transaction(payload.approval_id, actor=actor, business_transition=write)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    assert record is not None
    return {"signoff_id": record.signoff_id, "report_id": record.report_id, "approval_id": record.approval_id, "actor": record.actor, "signed_at": record.signed_at}


@router.get("/tasks/{task_id}/report/signoff", summary="读取任务最新报告的正式签发状态")
def get_report_signoff(task_id: str) -> dict[str, Any]:
    """只读返回最新报告的持久化签发记录；未签发保持明确 404 空态。"""
    report = _report_repository().latest_for_task(task_id)
    if report is None:
        raise HTTPException(status_code=404, detail={"message": "报告不存在"})
    record = _report_signoff_repository().find_for_report(report.report_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"message": "报告尚未正式签发"})
    return {"signoff_id": record.signoff_id, "report_id": record.report_id, "approval_id": record.approval_id, "actor": record.actor, "signed_at": record.signed_at}


@router.post(
    "/tasks/{task_id}/conflicts/{conflict_id}/approvals",
    summary="授予任务冲突裁决审批",
)
def grant_conflict_approval(
    task_id: str,
    conflict_id: str,
    payload: GrantConflictApprovalRequest,
    http_request: Request,
) -> dict[str, Any]:
    """授予单次冲突审批；主体、过期时间和依赖绑定全部由服务端生成。"""
    approver = _configured_approval_authority(http_request)
    execution_store = _execution_store_or_default()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=payload.expires_in_seconds)
    service = ResearchConflictApprovalService(
        execution_store,
        ResearchConflictContextRepository(execution_store.metadata_store),
        clock=lambda: now,
    )
    try:
        granted = service.grant(
            task_id=task_id,
            conflict_id=conflict_id,
            action=payload.action.value,
            selected_fact_id=payload.selected_fact_id,
            approver=approver,
            expires_at=expires_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    return {
        "approval_id": granted.approval.approval_id,
        "status": granted.approval.status,
        "approver": approver,
        "expires_at": expires_at.isoformat(),
    }


@router.get("/tasks/{task_id}/conflicts", summary="列出任务可信冲突")
def list_task_conflicts(task_id: str) -> dict[str, list[dict[str, Any]]]:
    store = _execution_store_or_default()
    try:
        _adapter().task_snapshot(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    contexts = ResearchConflictContextRepository(store.metadata_store)
    from src.financial_fact_conflict_repository import FinancialFactConflictRepository
    conflicts = FinancialFactConflictRepository(store.metadata_store)
    items = []
    for context in contexts.current_for_task(task_id):
        conflict = conflicts.get(context.conflict_id)
        if conflict is not None:
            items.append({"conflict_id": context.conflict_id, "status": conflict.status, "conflict_type": conflict.conflict_type, "fact_ids": list(conflict.fact_ids), "context_version": context.context_version})
    return {"items": items}


@router.get("/tasks/{task_id}/conflicts/{conflict_id}/reviews", summary="读取冲突裁决历史")
def conflict_review_history(task_id: str, conflict_id: str) -> dict[str, list[dict[str, Any]]]:
    store = _execution_store_or_default()
    if ResearchConflictContextRepository(store.metadata_store).current_for(task_id, conflict_id) is None:
        raise HTTPException(status_code=404, detail={"message": "任务冲突不存在"})
    records = ResearchConflictReviewStore(store.metadata_store, clock=lambda: datetime.now(timezone.utc)).history(conflict_id)
    return {"items": [{"review_id": r.review_id, "action": r.action.value, "selected_fact_id": r.selected_fact_id, "fact_ids": list(r.fact_ids), "actor": r.actor, "approval_id": r.approval_id} for r in records if r.task_id == task_id]}


@router.post("/tasks/{task_id}/conflicts/{conflict_id}/reviews", summary="裁决任务冲突")
def resolve_task_conflict(task_id: str, conflict_id: str, payload: ResolveConflictRequest, http_request: Request) -> dict[str, Any]:
    actor = _configured_approval_authority(http_request)
    store = _execution_store_or_default(); now = datetime.now(timezone.utc)
    service = ResearchConflictApprovalService(store, ResearchConflictContextRepository(store.metadata_store), clock=lambda: now)
    try:
        run_id, binding, _ = service.current_binding(task_id, conflict_id)
        approvals = None if payload.action is ConflictReviewAction.KEEP_PENDING else GovernanceApprovalStore(store.metadata_store, clock=lambda: now)
        record = ResearchConflictReviewStore(store.metadata_store, clock=lambda: now).resolve(task_id=task_id, run_id=run_id, conflict_id=conflict_id, action=payload.action, selected_fact_id=payload.selected_fact_id, binding=binding, actor=actor, approvals=approvals, approval_id=payload.approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    return {"review_id": record.review_id, "action": record.action.value, "selected_fact_id": record.selected_fact_id, "fact_ids": list(record.fact_ids), "actor": record.actor, "approval_id": record.approval_id}


@router.get("/tasks/{task_id}/events", summary="订阅研究任务事件流")
def stream_task_events(
    task_id: str,
    after_event_id: int | None = Query(default=None, ge=0),
    retention_seconds: int = Query(default=_DEFAULT_RETENTION_SECONDS, gt=0),
) -> StreamingResponse:
    """按持久事件 ID 输出 SSE 窗口；游标早于保留窗口时要求重同步。"""
    try:
        _adapter().task_snapshot(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    page = ResearchTaskEventStream(_execution_store_or_default()).read(
        task_id,
        after_event_id=after_event_id,
        now=now,
        retention_seconds=retention_seconds,
    )

    def frames() -> Iterator[str]:
        for event in page.events:
            frame: dict[str, Any] = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "revision": event.revision,
            }
            frame.update(event.payload)
            yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
        yield "data: " + json.dumps(
            {
                "event_type": "window_end",
                "next_event_id": page.next_event_id,
                "oldest_event_id": page.oldest_event_id,
                "resync_required": page.resync_required,
            },
            ensure_ascii=False,
        ) + "\n\n"

    return StreamingResponse(frames(), media_type="text/event-stream")


@router.post("/tasks/{task_id}/pause", summary="暂停研究任务")
def pause_task(task_id: str, request: TaskCommandRequest) -> dict[str, Any]:
    return _control_transition(task_id, "pause", request)


@router.post("/tasks/{task_id}/resume", summary="恢复研究任务")
def resume_task(task_id: str, request: TaskCommandRequest) -> dict[str, Any]:
    return _control_transition(task_id, "resume", request)


@router.post("/tasks/{task_id}/cancel", summary="取消研究任务")
def cancel_task(task_id: str, request: TaskCommandRequest) -> dict[str, Any]:
    return _control_transition(task_id, "cancel", request)
