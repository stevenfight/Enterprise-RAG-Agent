# -*- coding: utf-8 -*-
"""E-T18 冲突列表、历史与裁决 API 的 TDD 测试。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.durable_execution import DurableExecutionStore
from src.financial_fact_conflict_repository import FinancialFactConflictRepository
from src.financial_fact_conflict_service import FinancialFactConflictDecision
from src.research_conflict_governance import ResearchConflictContext, ResearchConflictContextRepository
from src.v7_metadata_store import V7MetadataStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    from src import research_task_api
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    store = DurableExecutionStore(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    research_task_api.configure_research_task_store(store)
    app = FastAPI(); app.include_router(research_task_api.router)
    client = TestClient(app)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200
    assert client.post("/api/research/tasks", json={"task_id":"task-review","dag_step_ids":["retrieve"],"objective":"核对","scope":["收入"],"estimated_cost":"1"}).status_code == 200
    FinancialFactConflictRepository(store.metadata_store).save("conflict-review", FinancialFactConflictDecision("pending_review","VALUE_CONFLICT",("fact-a","fact-b"),"0.1"))
    ResearchConflictContextRepository(store.metadata_store).append(ResearchConflictContext.create(task_id="task-review", run_id="research:task-review", conflict_id="conflict-review", fact_version="facts-v1", artifact_version="artifacts-v1", index_generation="generation-v1"))
    return client


def _headers() -> dict[str, str]:
    return {}


def test_task_conflict_list_and_history_use_trusted_context(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    listed = client.get("/api/research/tasks/task-review/conflicts")
    history = client.get("/api/research/tasks/task-review/conflicts/conflict-review/reviews")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["conflict_id"] == "conflict-review"
    assert listed.json()["items"][0]["fact_ids"] == ["fact-a", "fact-b"]
    assert history.status_code == 200
    assert history.json()["items"] == []


def test_approve_consumes_server_bound_approval_and_keep_pending_does_not(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    grant = client.post("/api/research/tasks/task-review/conflicts/conflict-review/approvals", json={"action":"approve","selected_fact_id":"fact-a","expires_in_seconds":3600}, headers=_headers())
    approved = client.post("/api/research/tasks/task-review/conflicts/conflict-review/reviews", json={"action":"approve","selected_fact_id":"fact-a","approval_id":grant.json()["approval_id"]}, headers=_headers())
    pending = client.post("/api/research/tasks/task-review/conflicts/conflict-review/reviews", json={"action":"keep_pending"}, headers=_headers())
    assert approved.status_code == 200
    assert approved.json()["approval_id"] == grant.json()["approval_id"]
    assert pending.status_code == 200
    assert pending.json()["approval_id"] is None


def test_review_rejects_client_binding_fields(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post("/api/research/tasks/task-review/conflicts/conflict-review/reviews", json={"action":"keep_pending","binding":{"task_revision":99}}, headers=_headers())
    assert response.status_code == 422
