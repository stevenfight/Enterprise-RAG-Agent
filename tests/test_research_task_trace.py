# -*- coding: utf-8 -*-
"""E-T39：研究步骤 Agent/工具绑定和可审计轨迹。"""

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agent_registry import AgentCapability, AgentRegistry
from src.durable_execution import DurableExecutionStore
from src.research_delivery import ResearchPlan
from src.research_plan_repository import ResearchPlanRepository
from src.research_report_repository import ResearchReportRepository
from src.research_task_adapter import ResearchTaskAdapter
from src.tools import BaseTool, ToolRegistry, ToolResult
from src.v7_metadata_store import V7MetadataStore


def _registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(AgentCapability(name="PlanAgent", description="计划确认", tools=[]))
    registry.register(AgentCapability(name="ReportAgent", description="报告确认", tools=[]))
    registry.register(AgentCapability(name="DataAgent", description="检索", tools=["retrieve"]))
    registry.register(AgentCapability(name="CalcAgent", description="计算", tools=["calculator"]))
    registry.register(AgentCapability(name="CompareAgent", description="对比", tools=["compare"]))
    registry.register(AgentCapability(name="ChartAgent", description="图表", tools=["chart"]))
    registry.register(AgentCapability(name="VerifyAgent", description="审核", tools=["verify", "retrieve"]))
    return registry


def _tool_registry() -> ToolRegistry:
    class SourceRetrieveTool(BaseTool):
        name = "retrieve"
        description = "测试检索工具"

        def run(self, **_kwargs) -> ToolResult:
            return ToolResult(
                success=True,
                data={
                    "results": [
                        {
                            "source_file": "annual-report.pdf",
                            "physical_pages": [12],
                            "text": "营业收入同比增长，详见年报披露。",
                        }
                    ]
                },
            )

    registry = ToolRegistry()
    registry.register(SourceRetrieveTool())
    return registry


def _bound_plan(
    task_id: str,
    *,
    objective: str = "核对营业收入变化",
    scope: tuple[str, ...] = ("营业收入",),
) -> ResearchPlan:
    return ResearchPlan.create(
        plan_id=f"research-plan:{task_id}:1",
        task_id=task_id,
        objective=objective,
        scope=scope,
        step_ids=("plan", "retrieve", "review", "report"),
        estimated_cost=Decimal("1.00"),
        step_bindings={
            "plan": {"agent_name": "DataAgent", "tool_names": []},
            "retrieve": {"agent_name": "DataAgent", "tool_names": ["retrieve"]},
            "review": {"agent_name": "VerifyAgent", "tool_names": ["verify"]},
            "report": {"agent_name": "VerifyAgent", "tool_names": []},
        },
    )


def _running_bound_task(
    tmp_path: Path,
    task_id: str,
    *,
    objective: str = "核对营业收入变化",
    scope: tuple[str, ...] = ("营业收入",),
):
    metadata_store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    adapter = ResearchTaskAdapter(DurableExecutionStore(metadata_store))
    created = adapter.create_task(task_id, ("plan", "retrieve", "review", "report"))
    adapter.start_task(task_id, created.revision, f"start:{task_id}", actor="approver")
    plans = ResearchPlanRepository(metadata_store)
    plans.append(_bound_plan(task_id, objective=objective, scope=scope))
    return adapter, plans, ResearchReportRepository(metadata_store)


def test_bound_plan_round_trips_agent_and_tool_bindings(tmp_path: Path) -> None:
    metadata_store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    plans = ResearchPlanRepository(metadata_store)
    plan = _bound_plan("trace-plan")

    plans.append(plan)

    restored = plans.current_for_task("trace-plan")
    assert restored is not None
    assert restored.step_bindings == plan.step_bindings


def test_executor_persists_step_agent_tool_and_safe_result_trace(tmp_path: Path) -> None:
    from src.research_task_execution import ResearchTaskExecutor

    adapter, plans, reports = _running_bound_task(tmp_path, "trace-success")
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: {
            "answer": "营业收入同比增长，详见年报披露。",
            "sources": [{"source_file": "annual-report.pdf", "pages": [12]}],
            "secret": "不得持久化",
        },
        agent_registry=_registry(),
        tool_registry=_tool_registry(),
    )

    snapshot = executor.execute("trace-success", actor="worker")

    assert snapshot.status == "completed"
    invocations = adapter.execution_store.recovery_plan(adapter.run_id_for("trace-success")).invocation_records
    traces = [item.details["step_trace"] for item in invocations]
    assert [trace["step_id"] for trace in traces] == ["plan", "retrieve", "review", "report"]
    assert traces[1]["agent_name"] == "DataAgent"
    assert traces[1]["tool_names"] == ["retrieve"]
    assert traces[1]["result_summary"] == {"source_count": 1, "answer_present": True}
    assert all("secret" not in item.details for item in invocations)


def test_execution_summary_exposes_persisted_step_traces(tmp_path: Path, monkeypatch) -> None:
    from src import research_task_api
    from src.research_task_execution import ResearchTaskExecutor

    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    adapter, plans, reports = _running_bound_task(tmp_path, "trace-summary")
    registry = _registry()
    research_task_api.configure_research_task_store(adapter.execution_store)
    research_task_api.configure_research_task_agent_registry(registry)
    research_task_api.configure_research_task_tool_registry(_tool_registry())
    app = FastAPI()
    app.include_router(research_task_api.router)
    client = TestClient(app)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200
    ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: {"answer": "收入增长", "sources": [{"source_file": "annual-report.pdf", "pages": [12]}]},
        agent_registry=registry,
        tool_registry=_tool_registry(),
    ).execute("trace-summary", actor="worker")

    response = client.get("/api/research/tasks/trace-summary/execution")

    assert response.status_code == 200
    assert [item["step_id"] for item in response.json()["step_traces"]] == ["plan", "retrieve", "review", "report"]


def test_create_task_endpoint_persists_explicit_step_bindings(tmp_path: Path, monkeypatch) -> None:
    from src import research_task_api

    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    store = DurableExecutionStore(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    research_task_api.configure_research_task_store(store)
    app = FastAPI()
    app.include_router(research_task_api.router)
    client = TestClient(app)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200

    response = client.post(
        "/api/research/tasks",
        json={
            "task_id": "trace-api",
            "dag_step_ids": ["retrieve"],
            "objective": "核对收入",
            "scope": ["营业收入"],
            "estimated_cost": "1",
            "step_bindings": {"retrieve": {"agent_name": "DataAgent", "tool_names": ["retrieve"]}},
        },
    )

    assert response.status_code == 200
    assert response.json()["plan"]["step_bindings"] == {
        "retrieve": {"agent_name": "DataAgent", "tool_names": ["retrieve"]},
    }


def test_bound_task_http_approval_executes_and_exposes_trace_summary(tmp_path: Path, monkeypatch) -> None:
    """受控 HTTP 链路覆盖绑定任务的提交、审批、执行和摘要读取。"""
    from src import research_task_api

    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    store = DurableExecutionStore(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    research_task_api.configure_research_task_store(store)
    research_task_api.configure_research_task_query(
        lambda _: {
            "answer": "营业收入同比增长。",
            "sources": [{"source_file": "annual-report.pdf", "pages": [12]}],
        }
    )
    research_task_api.configure_research_task_agent_registry(_registry())
    research_task_api.configure_research_task_tool_registry(_tool_registry())
    app = FastAPI()
    app.include_router(research_task_api.router)
    client = TestClient(app)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200

    created = client.post(
        "/api/research/tasks",
        json={
            "task_id": "trace-http-e2e",
            "dag_step_ids": ["plan", "retrieve", "review", "report"],
            "objective": "核对收入",
            "scope": ["营业收入"],
            "estimated_cost": "1",
            "step_bindings": {
                "plan": {"agent_name": "DataAgent", "tool_names": []},
                "retrieve": {"agent_name": "DataAgent", "tool_names": ["retrieve"]},
                "review": {"agent_name": "VerifyAgent", "tool_names": ["verify"]},
                "report": {"agent_name": "VerifyAgent", "tool_names": []},
            },
        },
    )
    assert created.status_code == 200

    approved = client.post(
        "/api/research/tasks/trace-http-e2e/submission/approve",
        json={"expected_revision": 0, "command_id": "approve-trace-http-e2e"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "running"

    detail = client.get("/api/research/tasks/trace-http-e2e")
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"
    execution = client.get("/api/research/tasks/trace-http-e2e/execution")
    assert execution.status_code == 200
    traces = execution.json()["step_traces"]
    assert [item["step_id"] for item in traces] == ["plan", "retrieve", "review", "report"]
    assert traces[1]["agent_name"] == "DataAgent"
    assert traces[1]["result_summary"] == {"source_count": 1, "answer_present": True}
    assert client.get("/api/research/tasks/trace-http-e2e/report").status_code == 200


def test_retry_copies_step_bindings_without_back_migrating_source(tmp_path: Path) -> None:
    from src.research_task_retry import ResearchTaskRetryService
    from src.research_task_submission import ResearchTaskSubmissionRepository

    adapter, plans, _ = _running_bound_task(tmp_path, "trace-retry")
    ResearchTaskSubmissionRepository(adapter.execution_store.metadata_store).submit("trace-retry", "researcher")
    adapter.fail_task("trace-retry", 1, "fail-trace-retry", actor="worker")

    retried = ResearchTaskRetryService(adapter).create_retry(
        "trace-retry", 2, "retry-trace-1", actor="approver"
    )

    copied = plans.current_for_task(retried.task_id)
    assert copied is not None
    assert copied.step_bindings == _bound_plan("trace-retry").step_bindings
    assert adapter.task_snapshot("trace-retry").status == "failed"


def test_bound_retrieve_step_calls_injected_tool_registry_and_persists_safe_summary(tmp_path: Path) -> None:
    """绑定检索必须真实调用工具，账本不得保留参数或来源正文。"""
    from src.research_task_execution import ResearchTaskExecutor

    class RecordingRetrieveTool(BaseTool):
        name = "retrieve"
        description = "测试检索工具"

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run(self, **kwargs) -> ToolResult:
            self.calls.append(kwargs)
            return ToolResult(
                success=True,
                data={
                    "results": [
                        {
                            "source_file": "annual-report.pdf",
                            "physical_pages": [12],
                            "text": "营业收入为100亿元。",
                        }
                    ]
                },
            )

    adapter, plans, reports = _running_bound_task(tmp_path, "trace-tool-registry")
    tools = ToolRegistry()
    retrieve_tool = RecordingRetrieveTool()
    tools.register(retrieve_tool)
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: pytest.fail("绑定检索不应调用通用查询函数"),
        agent_registry=_registry(),
        tool_registry=tools,
    )

    snapshot = executor.execute("trace-tool-registry", actor="worker")

    assert snapshot.status == "completed"
    assert retrieve_tool.calls == [{"query": "核对营业收入变化"}]
    invocations = adapter.execution_store.recovery_plan(
        adapter.run_id_for("trace-tool-registry")
    ).invocation_records
    retrieve_invocation = next(
        item
        for item in invocations
        if item.details.get("step_trace", {}).get("step_id") == "retrieve"
    )
    assert retrieve_invocation.details["tool_calls"] == [
        {
            "tool_name": "retrieve",
            "status": "succeeded",
            "result_summary": {"source_count": 1, "answer_present": True},
        }
    ]
    assert "query" not in retrieve_invocation.details
    assert "营业收入为100亿元。" not in str(retrieve_invocation.details)


def test_bound_retrieve_step_fails_when_tool_registry_is_not_configured(tmp_path: Path) -> None:
    """绑定检索未装配工具时不得回退为通用查询。"""
    from src.research_task_execution import ResearchTaskExecutor

    adapter, plans, reports = _running_bound_task(tmp_path, "trace-tool-missing")
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: {"answer": "不应回退", "sources": [{"source_file": "annual-report.pdf", "pages": [12]}]},
        agent_registry=_registry(),
    )

    snapshot = executor.execute("trace-tool-missing", actor="worker")

    assert snapshot.status == "failed"
    assert reports.latest_for_task("trace-tool-missing") is None


def test_bound_data_agent_retrieve_runs_worker_and_persists_safe_worker_summary(tmp_path: Path) -> None:
    """已装配 Provider 的 DataAgent 绑定必须实际运行 Worker，而不是直连工具。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor
    from src.tools.verify_tool import VerifyTool

    class RecordingRetrieveTool(BaseTool):
        name = "retrieve"
        description = "测试检索工具"

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run(self, **kwargs) -> ToolResult:
            self.calls.append(kwargs)
            return ToolResult(
                success=True,
                data={
                    "results": [
                        {
                            "source_file": "annual-report.pdf",
                            "physical_pages": [12],
                            "text": "营业收入为100亿元。",
                        }
                    ]
                },
            )

    class ScriptedProvider:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.responses = iter((
                'Thought: 先检索年报。\nAction: retrieve\nAction Input: {"query": "核对营业收入变化"}',
                "Thought: 已取得来源。\nFinal Answer: 营业收入为100亿元。",
                'Thought: 审核数据。\nAction: verify\nAction Input: {"claim": "营业收入为100亿元。", "source_text": "营业收入为100亿元。"}',
                "Thought: 审核通过。\nFinal Answer: 声明与来源一致。",
            ))

        def chat(self, **kwargs) -> LLMResponse:
            self.calls.append(kwargs)
            return LLMResponse(content=next(self.responses), success=True)

    adapter, plans, reports = _running_bound_task(
        tmp_path,
        "trace-data-agent-worker",
        scope=("中国移动", "营业收入"),
    )
    tools = ToolRegistry()
    retrieve_tool = RecordingRetrieveTool()
    tools.register(retrieve_tool)
    tools.register(VerifyTool())
    provider = ScriptedProvider()
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: pytest.fail("DataAgent Worker 路径不应调用通用查询函数"),
        agent_registry=_registry(),
        tool_registry=tools,
        llm_provider=provider,
    )

    snapshot = executor.execute("trace-data-agent-worker", actor="worker")

    assert snapshot.status == "completed"
    first_messages = provider.calls[0]["messages"]
    first_user_content = "\n".join(
        item["content"] for item in first_messages if item["role"] == "user"
    )
    assert "中国移动" in first_user_content
    assert retrieve_tool.calls == [{"query": "核对营业收入变化"}]
    assert len(provider.calls) == 4
    invocations = adapter.execution_store.recovery_plan(
        adapter.run_id_for("trace-data-agent-worker")
    ).invocation_records
    retrieve_invocation = next(
        item
        for item in invocations
        if item.details.get("step_trace", {}).get("step_id") == "retrieve"
    )
    assert retrieve_invocation.details["worker_call"] == {
        "agent_name": "DataAgent",
        "status": "succeeded",
        "result_summary": {"total_steps": 2, "source_count": 1, "answer_present": True},
    }
    assert "核对营业收入变化" not in str(retrieve_invocation.details)
    assert "营业收入为100亿元。" not in str(retrieve_invocation.details)


def test_bound_data_agent_receives_approved_scope_in_worker_context(tmp_path: Path) -> None:
    """DataAgent 必须收到计划 scope，不能只收到泛化 objective。"""
    from src.research_task_execution import ResearchTaskExecutor
    plan = _bound_plan(
        "trace-data-agent-scope",
        objective="核对营业收入变化",
        scope=("中国移动", "2023年度", "营业收入"),
    )

    assert ResearchTaskExecutor._data_agent_query(plan) == (
        "核对营业收入变化\n已审批研究范围：中国移动；2023年度；营业收入"
    )


def test_bound_verify_agent_receives_full_retrieved_source_context(tmp_path: Path) -> None:
    """审核 Worker 必须收到完整来源正文，不能因来源摘要截断而丢失表格数据。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor

    source_text = "前置说明。" * 70 + "营业收入为100亿元。"

    class RecordingRetrieveTool(BaseTool):
        name = "retrieve"
        description = "测试检索工具"

        def run(self, **_kwargs) -> ToolResult:
            return ToolResult(
                success=True,
                data={
                    "results": [
                        {
                            "source_file": "annual-report.pdf",
                            "physical_pages": [12],
                            "text": source_text,
                        }
                    ]
                },
            )

    class RecordingVerifyTool(BaseTool):
        name = "verify"
        description = "测试审核工具"

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run(self, **kwargs) -> ToolResult:
            self.calls.append(kwargs)
            return ToolResult(
                success=True,
                data={
                    "valid": True,
                    "confidence": 0.9,
                    "total_claims": 1,
                    "matched_count": 1,
                    "mismatched_count": 0,
                },
            )

    class ScriptedProvider:
        def __init__(self) -> None:
            self.responses = iter((
                'Thought: 先检索年报。\nAction: retrieve\nAction Input: {"query": "核对营业收入"}',
                "Thought: 已取得来源。\nFinal Answer: 营业收入为100亿元。",
                'Thought: 使用审核工具。\nAction: verify\nAction Input: {"claim": "营业收入为100亿元。", "source_text": "营业收入为100亿元。"}',
                "Thought: 审核通过。\nFinal Answer: 声明与来源一致。",
            ))

        def chat(self, **_kwargs) -> LLMResponse:
            return LLMResponse(content=next(self.responses), success=True)

    adapter, plans, reports = _running_bound_task(tmp_path, "trace-full-source-context")
    tools = ToolRegistry()
    tools.register(RecordingRetrieveTool())
    verify_tool = RecordingVerifyTool()
    tools.register(verify_tool)
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: pytest.fail("Worker 路径不应调用通用查询函数"),
        agent_registry=_registry(),
        tool_registry=tools,
        llm_provider=ScriptedProvider(),
    )

    snapshot = executor.execute("trace-full-source-context", actor="worker")

    assert snapshot.status == "completed"
    assert verify_tool.calls == [{
        "claim": "营业收入为100亿元。",
        "source_text": source_text,
    }]


def test_bound_verify_agent_review_runs_verify_only_and_persists_safe_summary(tmp_path: Path) -> None:
    """审核绑定必须实际运行 VerifyAgent，且只允许它调用 verify 工具。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor

    class RecordingVerifyTool(BaseTool):
        name = "verify"
        description = "测试审核工具"

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run(self, **kwargs) -> ToolResult:
            self.calls.append(kwargs)
            return ToolResult(
                success=True,
                data={
                    "valid": True,
                    "confidence": 0.9,
                    "total_claims": 1,
                    "matched_count": 1,
                    "mismatched_count": 0,
                },
            )

    class ScriptedProvider:
        def __init__(self) -> None:
            self.responses = iter((
                'Thought: 先检索年报。\nAction: retrieve\nAction Input: {"query": "核对营业收入变化"}',
                "Thought: 已取得来源。\nFinal Answer: 营业收入为100亿元。",
                'Thought: 使用审核工具。\nAction: verify\nAction Input: {"claim": "营业收入为100亿元。", "source_text": "营业收入为100亿元。"}',
                "Thought: 审核通过。\nFinal Answer: 声明与来源一致。",
            ))

        def chat(self, **_kwargs) -> LLMResponse:
            return LLMResponse(content=next(self.responses), success=True)

    adapter, plans, reports = _running_bound_task(tmp_path, "trace-verify-agent-worker")
    tools = _tool_registry()
    verify_tool = RecordingVerifyTool()
    tools.register(verify_tool)
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: pytest.fail("Worker 路径不应调用通用查询函数"),
        agent_registry=_registry(),
        tool_registry=tools,
        llm_provider=ScriptedProvider(),
    )

    snapshot = executor.execute("trace-verify-agent-worker", actor="worker")

    assert snapshot.status == "completed"
    assert verify_tool.calls == [{
        "claim": "营业收入为100亿元。",
        "source_text": "营业收入同比增长，详见年报披露。",
    }]
    invocations = adapter.execution_store.recovery_plan(
        adapter.run_id_for("trace-verify-agent-worker")
    ).invocation_records
    review_invocation = next(
        item
        for item in invocations
        if item.details.get("step_trace", {}).get("step_id") == "review"
    )
    assert review_invocation.details["worker_call"] == {
        "agent_name": "VerifyAgent",
        "status": "succeeded",
        "result_summary": {
            "total_steps": 2,
            "valid": True,
            "confidence": 0.9,
            "total_claims": 1,
            "matched_count": 1,
            "mismatched_count": 0,
        },
    }
    assert "营业收入为100亿元。" not in str(review_invocation.details)


def test_bound_calc_agent_runs_only_approved_calculator_input_and_persists_safe_summary(tmp_path: Path) -> None:
    """计算 Worker 必须只消费审批计划中的参数，并且账本不得保存具体数值。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor

    class RecordingCalculatorTool(BaseTool):
        name = "calculator"
        description = "测试计算工具"

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run(self, **kwargs) -> ToolResult:
            self.calls.append(kwargs)
            return ToolResult(success=True, data={"growth_rate_pct": 20.0})

    class RecordingVerifyTool(BaseTool):
        name = "verify"
        description = "测试审核工具"

        def run(self, **_kwargs) -> ToolResult:
            return ToolResult(
                success=True,
                data={
                    "valid": True,
                    "confidence": 0.9,
                    "total_claims": 1,
                    "matched_count": 1,
                    "mismatched_count": 0,
                },
            )

    class ScriptedProvider:
        def __init__(self) -> None:
            self.responses = iter((
                'Thought: 先检索年报。\nAction: retrieve\nAction Input: {"query": "核对营业收入变化"}',
                "Thought: 已取得来源。\nFinal Answer: 营业收入为100亿元。",
                'Thought: 使用已批准参数计算。\nAction: calculator\nAction Input: {"operation": "yoy_growth", "current": 120, "previous": 100}',
                "Thought: 计算完成。\nFinal Answer: 同比增长20%。",
                'Thought: 使用审核工具。\nAction: verify\nAction Input: {"claim": "营业收入为100亿元。", "source_text": "营业收入同比增长，详见年报披露。"}',
                "Thought: 审核通过。\nFinal Answer: 声明与来源一致。",
            ))

        def chat(self, **_kwargs) -> LLMResponse:
            return LLMResponse(content=next(self.responses), success=True)

    task_id = "trace-calc-agent-worker"
    metadata_store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    adapter = ResearchTaskAdapter(DurableExecutionStore(metadata_store))
    created = adapter.create_task(task_id, ("retrieve", "calculate", "review", "report"))
    adapter.start_task(task_id, created.revision, f"start:{task_id}", actor="approver")
    plans = ResearchPlanRepository(metadata_store)
    plans.append(ResearchPlan.create(
        plan_id=f"research-plan:{task_id}:1",
        task_id=task_id,
        objective="核对营业收入变化",
        scope=("营业收入",),
        step_ids=("retrieve", "calculate", "review", "report"),
        estimated_cost=Decimal("1.00"),
        step_bindings={
            "retrieve": {"agent_name": "DataAgent", "tool_names": ["retrieve"]},
            "calculate": {"agent_name": "CalcAgent", "tool_names": ["calculator"]},
            "review": {"agent_name": "VerifyAgent", "tool_names": ["verify"]},
            "report": {"agent_name": "VerifyAgent", "tool_names": []},
        },
        step_inputs={"calculate": {"operation": "yoy_growth", "current": 120, "previous": 100}},
    ))
    tools = _tool_registry()
    calculator = RecordingCalculatorTool()
    tools.register(calculator)
    tools.register(RecordingVerifyTool())
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        ResearchReportRepository(metadata_store),
        query=lambda _: pytest.fail("Worker 路径不应调用通用查询函数"),
        agent_registry=_registry(),
        tool_registry=tools,
        llm_provider=ScriptedProvider(),
    )

    snapshot = executor.execute(task_id, actor="worker")

    assert snapshot.status == "completed"
    assert plans.current_for_task(task_id).input_for("calculate") == {
        "operation": "yoy_growth", "current": 120, "previous": 100,
    }
    assert calculator.calls == [{"operation": "yoy_growth", "current": 120, "previous": 100}]
    invocations = adapter.execution_store.recovery_plan(adapter.run_id_for(task_id)).invocation_records
    calculate_invocation = next(
        item for item in invocations
        if item.details.get("step_trace", {}).get("step_id") == "calculate"
    )
    assert calculate_invocation.details["step_trace"]["result_summary"] == {
        "operation": "yoy_growth", "result_present": True,
    }
    assert calculate_invocation.details["worker_call"] == {
        "agent_name": "CalcAgent",
        "status": "succeeded",
        "result_summary": {"total_steps": 2, "operation": "yoy_growth", "result_present": True},
    }
    assert "120" not in str(calculate_invocation.details)
    assert "100" not in str(calculate_invocation.details)


def test_bound_compare_agent_runs_only_approved_input_and_returns_safe_trace() -> None:
    """CompareAgent 必须只使用批准参数，且回放摘要不含公司和年份。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor

    class RecordingCompareTool(BaseTool):
        name = "compare"
        description = "测试对比工具"

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run(self, **kwargs) -> ToolResult:
            self.calls.append(kwargs)
            return ToolResult(success=True, data={"table": "安全测试表", "companies_compared": 2})

    class ScriptedProvider:
        def __init__(self) -> None:
            self.responses = iter((
                'Thought: 使用批准参数。\nAction: compare\nAction Input: {"companies": ["中国移动", "中国电信"], "metric": "营收", "year": "2024", "top_n": 3}',
                "Thought: 对比完成。\nFinal Answer: 已完成。",
            ))

        def chat(self, **_kwargs) -> LLMResponse:
            return LLMResponse(content=next(self.responses), success=True)

    params = {"companies": ["中国移动", "中国电信"], "metric": "营收", "year": "2024", "top_n": 3}
    plan = ResearchPlan.create(
        plan_id="research-plan:trace-compare:1",
        task_id="trace-compare",
        objective="比较运营商营收",
        scope=("营收",),
        step_ids=("compare",),
        estimated_cost=Decimal("1.00"),
        step_bindings={"compare": {"agent_name": "CompareAgent", "tool_names": ["compare"]}},
        step_inputs={"compare": params},
    )
    tools = ToolRegistry()
    compare_tool = RecordingCompareTool()
    tools.register(compare_tool)
    executor = ResearchTaskExecutor(None, None, None, query=lambda _: pytest.fail("不得调用通用查询"), tool_registry=tools, llm_provider=ScriptedProvider())

    tool_calls, worker_call, comparison_result = executor._compare(plan)

    assert compare_tool.calls == [params]
    assert tool_calls == ({"tool_name": "compare", "status": "succeeded", "result_summary": {"metric": "营收", "result_present": True}},)
    assert worker_call == {"agent_name": "CompareAgent", "status": "succeeded", "result_summary": {"total_steps": 2, "metric": "营收", "result_present": True}}
    assert ResearchTaskExecutor._step_trace(plan, "compare", query_result=None, calculation_result=None, comparison_result=comparison_result, chart_result=None, review_result=None, report=None)["result_summary"] == {"metric": "营收", "result_present": True}


def test_bound_compare_agent_execution_persists_safe_c0_invocation(tmp_path: Path) -> None:
    """完整任务必须持久化 compare Worker 的脱敏 C0 调用记录。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor

    class RecordingCompareTool(BaseTool):
        name = "compare"
        description = "测试对比工具"

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run(self, **kwargs) -> ToolResult:
            self.calls.append(kwargs)
            return ToolResult(success=True, data={"table": "安全测试表", "companies_compared": 2})

    class RecordingVerifyTool(BaseTool):
        name = "verify"
        description = "测试审核工具"

        def run(self, **_kwargs) -> ToolResult:
            return ToolResult(success=True, data={"valid": True, "confidence": 0.9, "total_claims": 1, "matched_count": 1, "mismatched_count": 0})

    class ScriptedProvider:
        def __init__(self) -> None:
            self.responses = iter((
                'Thought: 检索。\nAction: retrieve\nAction Input: {"query": "比较运营商营收"}',
                "Thought: 完成。\nFinal Answer: 营收已披露。",
                'Thought: 对比。\nAction: compare\nAction Input: {"companies": ["中国移动", "中国电信"], "metric": "营收", "year": "2024", "top_n": 3}',
                "Thought: 完成。\nFinal Answer: 对比完成。",
                'Thought: 审核。\nAction: verify\nAction Input: {"claim": "营收已披露。", "source_text": "营业收入同比增长，详见年报披露。"}',
                "Thought: 完成。\nFinal Answer: 审核通过。",
            ))

        def chat(self, **_kwargs) -> LLMResponse:
            return LLMResponse(content=next(self.responses), success=True)

    task_id = "trace-compare-c0"
    metadata_store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    adapter = ResearchTaskAdapter(DurableExecutionStore(metadata_store))
    created = adapter.create_task(task_id, ("retrieve", "compare", "review", "report"))
    adapter.start_task(task_id, created.revision, f"start:{task_id}", actor="approver")
    plans = ResearchPlanRepository(metadata_store)
    params = {"companies": ["中国移动", "中国电信"], "metric": "营收", "year": "2024", "top_n": 3}
    plans.append(ResearchPlan.create(
        plan_id=f"research-plan:{task_id}:1", task_id=task_id, objective="比较运营商营收",
        scope=("营收",), step_ids=("retrieve", "compare", "review", "report"), estimated_cost=Decimal("1.00"),
        step_bindings={"retrieve": {"agent_name": "DataAgent", "tool_names": ["retrieve"]}, "compare": {"agent_name": "CompareAgent", "tool_names": ["compare"]}, "review": {"agent_name": "VerifyAgent", "tool_names": ["verify"]}, "report": {"agent_name": "VerifyAgent", "tool_names": []}},
        step_inputs={"compare": params},
    ))
    tools = _tool_registry()
    compare_tool = RecordingCompareTool()
    tools.register(compare_tool)
    tools.register(RecordingVerifyTool())
    executor = ResearchTaskExecutor(adapter, plans, ResearchReportRepository(metadata_store), query=lambda _: pytest.fail("不得调用通用查询"), agent_registry=_registry(), tool_registry=tools, llm_provider=ScriptedProvider())

    assert executor.execute(task_id, actor="worker").status == "completed"
    assert compare_tool.calls == [params]
    invocations = adapter.execution_store.recovery_plan(adapter.run_id_for(task_id)).invocation_records
    invocation = next(item for item in invocations if item.details.get("step_trace", {}).get("step_id") == "compare")
    assert invocation.details["step_trace"]["result_summary"] == {"metric": "营收", "result_present": True}
    assert invocation.details["worker_call"] == {"agent_name": "CompareAgent", "status": "succeeded", "result_summary": {"total_steps": 2, "metric": "营收", "result_present": True}}
    assert "中国移动" not in str(invocation.details)
    assert "2024" not in str(invocation.details)


def test_bound_chart_agent_runs_only_approved_input_and_returns_safe_trace() -> None:
    """ChartAgent 必须实际调用 chart，且安全摘要不保留原始数据。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor

    class RecordingChartTool(BaseTool):
        name = "chart"
        description = "测试图表工具"
        def __init__(self) -> None: self.calls: list[dict[str, object]] = []
        def run(self, **kwargs) -> ToolResult:
            self.calls.append(kwargs)
            return ToolResult(success=True, data={"url": "/api/charts/images/test.png"})

    class Provider:
        def __init__(self) -> None:
            self.responses = iter(('Thought: 生成图表。\nAction: chart\nAction Input: {"data": {"中国移动": 100, "中国电信": 80}, "chart_type": "bar", "title": "营收"}', "Thought: 完成。\nFinal Answer: 已生成。"))
        def chat(self, **_kwargs) -> LLMResponse: return LLMResponse(content=next(self.responses), success=True)

    params = {"data": {"中国移动": 100, "中国电信": 80}, "chart_type": "bar", "title": "营收"}
    plan = ResearchPlan.create(plan_id="research-plan:chart:1", task_id="chart", objective="图表", scope=("营收",), step_ids=("chart",), estimated_cost="1", step_bindings={"chart": {"agent_name": "ChartAgent", "tool_names": ["chart"]}}, step_inputs={"chart": params})
    tools = ToolRegistry(); tool = RecordingChartTool(); tools.register(tool)
    executor = ResearchTaskExecutor(None, None, None, query=lambda _: pytest.fail("不得查询"), tool_registry=tools, llm_provider=Provider())
    tool_calls, worker_call, summary = executor._chart(plan)
    assert tool.calls == [params]
    assert tool_calls[0]["result_summary"] == {"chart_type": "bar", "result_present": True}
    assert worker_call["result_summary"] == {"total_steps": 2, "chart_type": "bar", "result_present": True}
    assert "中国移动" not in str(summary)


def test_bound_chart_agent_execution_persists_safe_c0_invocation(tmp_path: Path) -> None:
    """完整任务必须持久化 chart Worker 的脱敏 C0 调用记录。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor
    class Chart(BaseTool):
        name = "chart"; description = "测试图表"
        def __init__(self): self.calls = []
        def run(self, **kwargs): self.calls.append(kwargs); return ToolResult(success=True, data={"url": "/safe.png"})
    class Verify(BaseTool):
        name = "verify"; description = "测试审核"
        def run(self, **_kwargs): return ToolResult(success=True, data={"valid": True, "confidence": .9, "total_claims": 1, "matched_count": 1, "mismatched_count": 0})
    class Provider:
        def __init__(self): self.responses = iter((
            'Thought: 检索。\nAction: retrieve\nAction Input: {"query": "生成营收图表"}', "Thought: 完成。\nFinal Answer: 营收已披露。",
            'Thought: 图表。\nAction: chart\nAction Input: {"data": {"中国移动": 100, "中国电信": 80}, "chart_type": "bar", "title": "营收"}', "Thought: 完成。\nFinal Answer: 图表完成。",
            'Thought: 审核。\nAction: verify\nAction Input: {"claim": "营收已披露。", "source_text": "营业收入同比增长，详见年报披露。"}', "Thought: 完成。\nFinal Answer: 审核通过。"))
        def chat(self, **_kwargs): return LLMResponse(content=next(self.responses), success=True)
    task_id = "trace-chart-c0"; store = V7MetadataStore(tmp_path / "m.sqlite3"); adapter = ResearchTaskAdapter(DurableExecutionStore(store)); created = adapter.create_task(task_id, ("retrieve", "chart", "review", "report")); adapter.start_task(task_id, created.revision, "start", actor="approver")
    params = {"data": {"中国移动": 100, "中国电信": 80}, "chart_type": "bar", "title": "营收"}; plans = ResearchPlanRepository(store)
    plans.append(ResearchPlan.create(plan_id="plan-chart-c0", task_id=task_id, objective="生成营收图表", scope=("营收",), step_ids=("retrieve", "chart", "review", "report"), estimated_cost="1", step_bindings={"retrieve": {"agent_name": "DataAgent", "tool_names": ["retrieve"]}, "chart": {"agent_name": "ChartAgent", "tool_names": ["chart"]}, "review": {"agent_name": "VerifyAgent", "tool_names": ["verify"]}, "report": {"agent_name": "VerifyAgent", "tool_names": []}}, step_inputs={"chart": params}))
    tools = _tool_registry(); chart = Chart(); tools.register(chart); tools.register(Verify())
    assert ResearchTaskExecutor(adapter, plans, ResearchReportRepository(store), query=lambda _: pytest.fail("不得查询"), agent_registry=_registry(), tool_registry=tools, llm_provider=Provider()).execute(task_id, actor="worker").status == "completed"
    invocation = next(item for item in adapter.execution_store.recovery_plan(adapter.run_id_for(task_id)).invocation_records if item.details.get("step_trace", {}).get("step_id") == "chart")
    assert chart.calls == [params]
    assert invocation.details["step_trace"]["result_summary"] == {"chart_type": "bar", "result_present": True}
    assert "中国移动" not in str(invocation.details)


def test_bound_plan_agent_reads_only_approved_snapshot_and_returns_safe_trace() -> None:
    """PlanAgent 只能确认审批快照，不能生成或修改研究计划。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor

    class Provider:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def chat(self, **kwargs) -> LLMResponse:
            self.prompts.append(kwargs["messages"][-1]["content"])
            return LLMResponse(content="Thought: 已核对审批快照。\nFinal Answer: 已确认。", success=True)

    plan = ResearchPlan.create(
        plan_id="research-plan:plan-worker:1", task_id="plan-worker", objective="核对营业收入变化",
        scope=("营业收入",), step_ids=("plan",), estimated_cost="1",
        step_bindings={"plan": {"agent_name": "PlanAgent", "tool_names": []}},
    )
    provider = Provider()
    executor = ResearchTaskExecutor(None, None, None, query=lambda _: pytest.fail("不得查询"), llm_provider=provider)

    tool_calls, worker_call, summary = executor._plan(plan)

    assert tool_calls == ()
    assert worker_call == {"agent_name": "PlanAgent", "status": "succeeded", "result_summary": {"total_steps": 1, "plan_version": 1, "scope_count": 1, "step_count": 1, "acknowledged": True}}
    assert summary == {"plan_version": 1, "scope_count": 1, "step_count": 1, "acknowledged": True}
    assert "核对营业收入变化" in provider.prompts[0]
    assert ResearchTaskExecutor._step_trace(plan, "plan", query_result=None, calculation_result=None, comparison_result=None, chart_result=None, review_result=None, report=None, plan_result=summary)["result_summary"] == summary


def test_bound_plan_agent_execution_persists_safe_c0_invocation(tmp_path: Path) -> None:
    """完整任务的 plan C0 记录不得泄露目标或模型原文。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor

    class Verify(BaseTool):
        name = "verify"
        description = "测试审核"

        def run(self, **_kwargs) -> ToolResult:
            return ToolResult(success=True, data={"valid": True, "confidence": .9, "total_claims": 1, "matched_count": 1, "mismatched_count": 0})

    class Provider:
        def __init__(self) -> None:
            self.responses = iter((
                "Thought: 已确认计划。\nFinal Answer: 已确认。",
                'Thought: 检索。\nAction: retrieve\nAction Input: {"query": "核对营业收入变化"}',
                "Thought: 完成。\nFinal Answer: 营收已披露。",
                'Thought: 审核。\nAction: verify\nAction Input: {"claim": "营收已披露。", "source_text": "营业收入同比增长，详见年报披露。"}',
                "Thought: 完成。\nFinal Answer: 审核通过。",
            ))

        def chat(self, **_kwargs) -> LLMResponse:
            return LLMResponse(content=next(self.responses), success=True)

    task_id = "trace-plan-c0"
    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    adapter = ResearchTaskAdapter(DurableExecutionStore(store))
    created = adapter.create_task(task_id, ("plan", "retrieve", "review", "report"))
    adapter.start_task(task_id, created.revision, "start", actor="approver")
    plans = ResearchPlanRepository(store)
    plans.append(ResearchPlan.create(
        plan_id="research-plan:trace-plan-c0:1", task_id=task_id, objective="核对营业收入变化",
        scope=("营业收入",), step_ids=("plan", "retrieve", "review", "report"), estimated_cost="1",
        risks=("敏感风险",),
        step_bindings={"plan": {"agent_name": "PlanAgent", "tool_names": []}, "retrieve": {"agent_name": "DataAgent", "tool_names": ["retrieve"]}, "review": {"agent_name": "VerifyAgent", "tool_names": ["verify"]}, "report": {"agent_name": "VerifyAgent", "tool_names": []}},
    ))
    tools = _tool_registry()
    tools.register(Verify())
    executor = ResearchTaskExecutor(adapter, plans, ResearchReportRepository(store), query=lambda _: pytest.fail("不得查询"), agent_registry=_registry(), tool_registry=tools, llm_provider=Provider())

    assert executor.execute(task_id, actor="worker").status == "completed"
    invocation = next(item for item in adapter.execution_store.recovery_plan(adapter.run_id_for(task_id)).invocation_records if item.details.get("step_trace", {}).get("step_id") == "plan")
    assert invocation.details["step_trace"]["result_summary"] == {"plan_version": 1, "scope_count": 1, "step_count": 4, "acknowledged": True}
    assert invocation.details["worker_call"] == {"agent_name": "PlanAgent", "status": "succeeded", "result_summary": {"total_steps": 1, "plan_version": 1, "scope_count": 1, "step_count": 4, "acknowledged": True}}
    assert "核对营业收入变化" not in str(invocation.details)
    assert "敏感风险" not in str(invocation.details)


def test_bound_report_agent_confirms_immutable_draft_and_persists_safe_c0_invocation(tmp_path: Path) -> None:
    """ReportAgent 只能确认已有草稿，C0 不得保留声明或来源正文。"""
    from src.llm_provider import LLMResponse
    from src.research_task_execution import ResearchTaskExecutor

    class Provider:
        def __init__(self) -> None:
            self.responses = iter((
                'Thought: 检索。\nAction: retrieve\nAction Input: {"query": "核对营业收入变化"}',
                "Thought: 完成。\nFinal Answer: 营收已披露。",
                'Thought: 审核。\nAction: verify\nAction Input: {"claim": "营收已披露。", "source_text": "营业收入同比增长，详见年报披露。"}',
                "Thought: 完成。\nFinal Answer: 审核通过。",
                "Thought: 已确认不可变草稿。\nFinal Answer: 已确认。",
            ))
            self.prompts: list[str] = []

        def chat(self, **kwargs) -> LLMResponse:
            self.prompts.append(kwargs["messages"][-1]["content"])
            return LLMResponse(content=next(self.responses), success=True)

    class Verify(BaseTool):
        name = "verify"
        description = "测试审核"
        def run(self, **_kwargs) -> ToolResult:
            return ToolResult(success=True, data={"valid": True, "confidence": .9, "total_claims": 1, "matched_count": 1, "mismatched_count": 0})

    task_id = "trace-report-c0"; store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    adapter = ResearchTaskAdapter(DurableExecutionStore(store)); created = adapter.create_task(task_id, ("retrieve", "review", "report")); adapter.start_task(task_id, created.revision, "start", actor="approver")
    plans = ResearchPlanRepository(store)
    plans.append(ResearchPlan.create(plan_id="research-plan:trace-report-c0:1", task_id=task_id, objective="核对营业收入变化", scope=("营业收入",), step_ids=("retrieve", "review", "report"), estimated_cost="1", step_bindings={"retrieve": {"agent_name": "DataAgent", "tool_names": ["retrieve"]}, "review": {"agent_name": "VerifyAgent", "tool_names": ["verify"]}, "report": {"agent_name": "ReportAgent", "tool_names": []}}))
    tools = _tool_registry(); tools.register(Verify()); provider = Provider()
    assert ResearchTaskExecutor(adapter, plans, ResearchReportRepository(store), query=lambda _: pytest.fail("不得查询"), agent_registry=_registry(), tool_registry=tools, llm_provider=provider).execute(task_id, actor="worker").status == "completed"
    invocation = next(item for item in adapter.execution_store.recovery_plan(adapter.run_id_for(task_id)).invocation_records if item.details.get("step_trace", {}).get("step_id") == "report")
    assert invocation.details["step_trace"]["result_summary"] == {"report_version": 1, "claim_count": 1, "review_status": "pending_review", "acknowledged": True}
    assert invocation.details["worker_call"] == {"agent_name": "ReportAgent", "status": "succeeded", "result_summary": {"total_steps": 1, "report_version": 1, "claim_count": 1, "review_status": "pending_review", "acknowledged": True}}
    assert "营收已披露" not in str(invocation.details)
    assert "annual-report.pdf" not in str(invocation.details)
    assert "营收已披露" in provider.prompts[-1]


@pytest.mark.parametrize(
    "agent_name,tool_names,expected",
    [("MissingAgent", [], "未注册"), ("DataAgent", ["verify"], "未获授权")],
)
def test_executor_rejects_unregistered_agent_or_tool_binding(
    tmp_path: Path, agent_name: str, tool_names: list[str], expected: str
) -> None:
    from src.research_task_execution import ResearchTaskExecutor

    adapter, plans, reports = _running_bound_task(tmp_path, f"trace-invalid-{agent_name}")
    invalid = ResearchPlan.create(
        plan_id=f"research-plan:trace-invalid-{agent_name}:2",
        task_id=f"trace-invalid-{agent_name}",
        objective="核对营业收入变化",
        scope=("营业收入",),
        step_ids=("retrieve",),
        estimated_cost=Decimal("1.00"),
        step_bindings={"retrieve": {"agent_name": agent_name, "tool_names": tool_names}},
        plan_version=2,
    )
    plans.append(invalid)
    executor = ResearchTaskExecutor(
        adapter,
        plans,
        reports,
        query=lambda _: {"answer": "不应执行", "sources": []},
        agent_registry=_registry(),
    )

    snapshot = executor.execute(f"trace-invalid-{agent_name}", actor="worker")

    assert snapshot.status == "failed"
    assert expected in (adapter.route_decisions(snapshot.task_id)[-1].detail.get("reason") or "")
