# -*- coding: utf-8 -*-
"""E-T17 配置化冲突审批授予 API 的 TDD 测试。"""

from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.durable_execution import DurableExecutionStore
from src.financial_fact_conflict_repository import FinancialFactConflictRepository
from src.financial_fact_conflict_service import FinancialFactConflictDecision
from src.research_conflict_governance import (
    ResearchConflictContext,
    ResearchConflictContextRepository,
)
from src.research_delivery import ResearchPlan
from src.research_plan_repository import ResearchPlanRepository
from src.research_task_adapter import ResearchTaskAdapter
from src.v7_metadata_store import V7MetadataStore


def _approval_client(tmp_path: Path) -> TestClient:
    """创建带有任务、计划、冲突和可信上下文的独立审批测试应用。"""
    from src import research_task_api

    store = DurableExecutionStore(V7MetadataStore(tmp_path / "v7_metadata.sqlite3"))
    research_task_api.configure_research_task_store(store)
    adapter = ResearchTaskAdapter(store)
    adapter.create_task("task-approval", ("retrieve",))
    ResearchPlanRepository(store.metadata_store).append(
        ResearchPlan.create(
            plan_id="research-plan:task-approval:1",
            task_id="task-approval",
            objective="核对收入",
            scope=("收入",),
            step_ids=("retrieve",),
            estimated_cost=Decimal("2.50"),
        )
    )
    app = FastAPI()
    app.include_router(research_task_api.router)
    client = TestClient(app)
    FinancialFactConflictRepository(store.metadata_store).save(
        "conflict-approval",
        FinancialFactConflictDecision(
            "pending_review", "VALUE_CONFLICT", ("fact-a", "fact-b"), "0.10"
        ),
    )
    ResearchConflictContextRepository(store.metadata_store).append(
        ResearchConflictContext.create(
            task_id="task-approval",
            run_id="research:task-approval",
            conflict_id="conflict-approval",
            fact_version="facts-v1",
            artifact_version="artifacts-v1",
            index_generation="generation-v1",
        )
    )
    return client


def _approval_payload() -> dict[str, object]:
    return {
        "action": "approve",
        "selected_fact_id": "fact-a",
        "expires_in_seconds": 3600,
    }


def test_grant_conflict_approval_uses_configured_authority_not_request_body(
    tmp_path: Path, monkeypatch
) -> None:
    """E-T17：服务端从部署配置取得审批主体并生成审批。"""
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    client = _approval_client(tmp_path)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200

    response = client.post(
        "/api/research/tasks/task-approval/conflicts/conflict-approval/approvals",
        json=_approval_payload(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "granted"
    assert response.json()["approver"] == "admin"
    assert response.json()["approval_id"]


def test_grant_conflict_approval_fails_closed_for_missing_or_invalid_key(
    tmp_path: Path, monkeypatch
) -> None:
    """未配置或密钥不匹配时，通用 API Key 不得替代审批身份。"""
    client = _approval_client(tmp_path)
    missing_configuration = client.post(
        "/api/research/tasks/task-approval/conflicts/conflict-approval/approvals",
        json=_approval_payload(),
    )
    invalid_key = client.post(
        "/api/research/tasks/task-approval/conflicts/conflict-approval/approvals",
        json=_approval_payload(),
    )

    assert missing_configuration.status_code == 401
    assert invalid_key.status_code == 401


def test_grant_conflict_approval_rejects_client_supplied_approver_or_binding(
    tmp_path: Path, monkeypatch
) -> None:
    """客户端不能伪造审批主体、任务版本或其他审批绑定字段。"""
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    client = _approval_client(tmp_path)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200
    payload = _approval_payload() | {
        "approver": "forged-user",
        "binding": {"task_revision": 99},
    }

    response = client.post(
        "/api/research/tasks/task-approval/conflicts/conflict-approval/approvals",
        json=payload,
    )

    assert response.status_code == 422
