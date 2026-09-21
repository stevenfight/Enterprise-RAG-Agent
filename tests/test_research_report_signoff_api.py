# -*- coding: utf-8 -*-
"""E-T24 正式报告签发门禁的 RED→GREEN 测试。"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.durable_execution import DurableExecutionStore
from src.financial_fact_conflict_repository import FinancialFactConflictRepository
from src.financial_fact_conflict_service import FinancialFactConflictDecision
from src.governance.approval import GovernanceApprovalStore
from src.research_conflict_governance import ResearchConflictContext, ResearchConflictContextRepository
from src.v7_metadata_store import V7MetadataStore


def _client_with_report(tmp_path: Path, monkeypatch) -> tuple[TestClient, DurableExecutionStore]:
    from src import research_task_api

    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    store = DurableExecutionStore(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    research_task_api.configure_research_task_store(store)
    app = FastAPI(); app.include_router(research_task_api.router)
    client = TestClient(app)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200
    assert client.post("/api/research/tasks", json={"task_id": "task-signoff", "dag_step_ids": ["retrieve"], "objective": "核对收入", "scope": ["收入"], "estimated_cost": "1"}).status_code == 200
    assert client.post("/api/research/tasks/task-signoff/report", json={"data_version": "facts-v1", "claims": [{"claim_id": "claim-1", "text": "收入增长", "support_kind": "fact", "fact_ids": ["fact-1"]}]}).status_code == 200
    return client, store


def test_signoff_requires_bound_approval_and_appends_record(tmp_path: Path, monkeypatch) -> None:
    client, _ = _client_with_report(tmp_path, monkeypatch)

    missing = client.post("/api/research/tasks/task-signoff/report/signoff", json={"approval_id": "missing"})
    grant = client.post("/api/research/tasks/task-signoff/report/signoff/approvals", json={"expires_in_seconds": 3600})

    assert grant.status_code == 200
    signed = client.post("/api/research/tasks/task-signoff/report/signoff", json={"approval_id": grant.json()["approval_id"]})
    assert missing.status_code == 422
    assert signed.status_code == 200
    assert signed.json()["report_id"] == "research-report:task-signoff:1"
    assert signed.json()["approval_id"] == grant.json()["approval_id"]
    status = client.get("/api/research/tasks/task-signoff/report/signoff")
    assert status.status_code == 200
    assert status.json()["signoff_id"] == signed.json()["signoff_id"]


def test_signoff_rejects_pending_trusted_conflict_before_consuming_approval(tmp_path: Path, monkeypatch) -> None:
    client, store = _client_with_report(tmp_path, monkeypatch)
    FinancialFactConflictRepository(store.metadata_store).save("conflict-signoff", FinancialFactConflictDecision("pending_review", "VALUE_CONFLICT", ("fact-a", "fact-b"), "0.1"))
    ResearchConflictContextRepository(store.metadata_store).append(ResearchConflictContext.create(task_id="task-signoff", run_id="research:task-signoff", conflict_id="conflict-signoff", fact_version="facts-v1", artifact_version="artifacts-v1", index_generation="generation-v1"))

    grant = client.post("/api/research/tasks/task-signoff/report/signoff/approvals", json={"expires_in_seconds": 3600})

    assert grant.status_code == 200
    blocked = client.post("/api/research/tasks/task-signoff/report/signoff", json={"approval_id": grant.json()["approval_id"]})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["message"] == "存在未裁决关键冲突，禁止正式签发报告"


def test_signoff_rejects_second_valid_approval_without_consuming_it(tmp_path: Path, monkeypatch) -> None:
    client, store = _client_with_report(tmp_path, monkeypatch)
    first_grant = client.post("/api/research/tasks/task-signoff/report/signoff/approvals", json={"expires_in_seconds": 3600})
    second_grant = client.post("/api/research/tasks/task-signoff/report/signoff/approvals", json={"expires_in_seconds": 3600})

    assert first_grant.status_code == 200
    assert second_grant.status_code == 200
    assert client.post("/api/research/tasks/task-signoff/report/signoff", json={"approval_id": second_grant.json()["approval_id"]}).status_code == 200

    duplicate = client.post("/api/research/tasks/task-signoff/report/signoff", json={"approval_id": first_grant.json()["approval_id"]})

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["message"] == "报告已正式签发"
    assert GovernanceApprovalStore(store.metadata_store, clock=lambda: datetime.now(timezone.utc)).approval_status(first_grant.json()["approval_id"]) == "granted"
