# -*- coding: utf-8 -*-
"""E-T36：遗留运行任务必须经审批和 CAS 处置。"""

from pathlib import Path
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.durable_execution import DurableExecutionStore
from src.research_task_adapter import ResearchTaskAdapter
from src.research_delivery import ResearchPlan
from src.research_plan_repository import ResearchPlanRepository
from src.research_task_submission import ResearchTaskSubmissionRepository
from src.v7_metadata_store import V7MetadataStore


def _client_with_running_task(tmp_path: Path, monkeypatch, task_id: str) -> tuple[TestClient, ResearchTaskAdapter]:
    from src import research_task_api

    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    adapter = ResearchTaskAdapter(DurableExecutionStore(V7MetadataStore(tmp_path / "metadata.sqlite3")))
    created = adapter.create_task(task_id, ("plan", "retrieve"))
    adapter.start_task(task_id, created.revision, f"start:{task_id}", actor="admin")
    research_task_api.configure_research_task_store(adapter.execution_store)
    app = FastAPI()
    app.include_router(research_task_api.router)
    client = TestClient(app)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200
    return client, adapter


def test_approver_can_fail_legacy_running_task_without_execution_evidence(tmp_path: Path, monkeypatch) -> None:
    client, adapter = _client_with_running_task(tmp_path, monkeypatch, "legacy-running")

    disposed = client.post(
        "/api/research/tasks/legacy-running/legacy-disposition",
        json={"expected_revision": 1, "command_id": "dispose-legacy-1", "reason": "执行器接入前遗留任务，未领取步骤"},
    )

    assert disposed.status_code == 200
    assert disposed.json()["status"] == "failed"
    assert adapter.task_snapshot("legacy-running").status == "failed"
    decisions = adapter.route_decisions("legacy-running")
    assert decisions[-1].decision_type == "failure"
    assert decisions[-1].detail["reason"] == "执行器接入前遗留任务，未领取步骤"


def test_legacy_disposition_rejects_task_with_active_lease(tmp_path: Path, monkeypatch) -> None:
    client, adapter = _client_with_running_task(tmp_path, monkeypatch, "active-running")
    adapter.claim_step("active-running", "plan", "worker-a")

    disposed = client.post(
        "/api/research/tasks/active-running/legacy-disposition",
        json={"expected_revision": 1, "command_id": "dispose-active-1", "reason": "不应处置有活动租约的任务"},
    )

    assert disposed.status_code == 409
    assert adapter.task_snapshot("active-running").status == "running"


def test_approver_retries_failed_legacy_task_with_copied_plan_and_new_submission(tmp_path: Path, monkeypatch) -> None:
    client, adapter = _client_with_running_task(tmp_path, monkeypatch, "legacy-retry")
    plans = ResearchPlanRepository(adapter.execution_store.metadata_store)
    plans.append(
        ResearchPlan.create(
            plan_id="research-plan:legacy-retry:1",
            task_id="legacy-retry",
            objective="核对营业收入变化",
            scope=("营业收入",),
            step_ids=("plan", "retrieve"),
            estimated_cost=Decimal("1.00"),
        )
    )
    ResearchTaskSubmissionRepository(adapter.execution_store.metadata_store).submit("legacy-retry", "researcher")
    assert client.post(
        "/api/research/tasks/legacy-retry/legacy-disposition",
        json={"expected_revision": 1, "command_id": "dispose-retry-source", "reason": "历史执行器未接入"},
    ).status_code == 200

    retried = client.post(
        "/api/research/tasks/legacy-retry/retry",
        json={"expected_revision": 2, "command_id": "retry-legacy-1"},
    )

    assert retried.status_code == 200
    assert retried.json()["task_id"] == "legacy-retry-retry-1"
    assert retried.json()["status"] == "pending"
    assert retried.json()["plan"]["objective"] == "核对营业收入变化"
    assert retried.json()["submission"] == {"status": "submitted", "requester": "researcher", "reviewer": None}
    assert adapter.task_snapshot("legacy-retry").status == "failed"
    assert client.post(
        "/api/research/tasks/legacy-retry/retry",
        json={"expected_revision": 2, "command_id": "retry-legacy-1"},
    ).json()["task_id"] == "legacy-retry-retry-1"
    stale = client.post(
        "/api/research/tasks/legacy-retry/retry",
        json={"expected_revision": 1, "command_id": "retry-legacy-stale"},
    )
    assert stale.status_code == 409


def test_retry_rejects_failed_task_without_persisted_plan(tmp_path: Path, monkeypatch) -> None:
    client, _ = _client_with_running_task(tmp_path, monkeypatch, "legacy-without-plan")
    assert client.post(
        "/api/research/tasks/legacy-without-plan/legacy-disposition",
        json={"expected_revision": 1, "command_id": "dispose-without-plan", "reason": "历史执行器未接入"},
    ).status_code == 200

    retried = client.post(
        "/api/research/tasks/legacy-without-plan/retry",
        json={"expected_revision": 2, "command_id": "retry-without-plan"},
    )

    assert retried.status_code == 409
