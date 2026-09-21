# -*- coding: utf-8 -*-
"""E-T31：研究任务提交、审批和启动的服务端边界。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.durable_execution import DurableExecutionStore
from src.research_identity import _password_hash
from src.v7_metadata_store import V7MetadataStore


def _client(tmp_path: Path, monkeypatch) -> tuple[TestClient, V7MetadataStore]:
    from src import research_task_api

    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    metadata_store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    research_task_api.configure_research_task_store(DurableExecutionStore(metadata_store))
    research_task_api.configure_research_task_query(
        lambda _: {
            "answer": "年报披露的营业收入同比变化。",
            "sources": [{"source_file": "annual-report.pdf", "pages": [12]}],
        }
    )
    app = FastAPI()
    app.include_router(research_task_api.router)
    return TestClient(app), metadata_store


def _task_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "dag_step_ids": ["plan", "retrieve", "review", "report"],
        "objective": "核对收入变化",
        "scope": ["营业收入"],
        "estimated_cost": "1.00",
    }


def test_task_submission_requires_researcher_session_and_approver_starts_execution(tmp_path: Path, monkeypatch) -> None:
    client, _ = _client(tmp_path, monkeypatch)

    anonymous = client.post("/api/research/tasks", json=_task_payload("task-submission"))
    assert anonymous.status_code == 401

    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200
    submitted = client.post("/api/research/tasks", json=_task_payload("task-submission"))
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending"
    assert submitted.json()["submission"] == {
        "status": "submitted",
        "requester": "admin",
        "reviewer": None,
    }

    approved = client.post(
        "/api/research/tasks/task-submission/submission/approve",
        json={"expected_revision": 0, "command_id": "approve-submission-1"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "running"
    assert approved.json()["submission"] == {
        "status": "approved",
        "requester": "admin",
        "reviewer": "admin",
    }
    report = client.get("/api/research/tasks/task-submission/report")
    assert report.status_code == 200
    assert report.json()["claims"][0]["support_kind"] == "source"
    assert client.get("/api/research/tasks/task-submission").json()["status"] == "completed"


def test_researcher_cannot_approve_and_approver_can_reject(tmp_path: Path, monkeypatch) -> None:
    client, metadata_store = _client(tmp_path, monkeypatch)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200
    with metadata_store.connect() as connection:
        connection.execute("INSERT INTO v7_research_users(user_id, username, password_hash, enabled) VALUES (?, ?, ?, 1)", ("user:researcher", "researcher", _password_hash("researcher-password")))
        connection.execute("INSERT INTO v7_research_roles(role_id) VALUES ('researcher') ON CONFLICT(role_id) DO NOTHING")
        connection.execute("INSERT INTO v7_research_user_roles(user_id, role_id) VALUES (?, 'researcher')", ("user:researcher",))
        connection.commit()

    client.post("/api/research/auth/logout")
    assert client.post("/api/research/auth/login", json={"username": "researcher", "password": "researcher-password"}).status_code == 200
    assert client.post("/api/research/tasks", json=_task_payload("task-rejection")).status_code == 200
    forbidden = client.post(
        "/api/research/tasks/task-rejection/submission/approve",
        json={"expected_revision": 0, "command_id": "researcher-approve"},
    )
    assert forbidden.status_code == 403

    client.post("/api/research/auth/logout")
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200
    rejected = client.post(
        "/api/research/tasks/task-rejection/submission/reject",
        json={"expected_revision": 0, "command_id": "reject-submission-1"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "pending"
    assert rejected.json()["submission"] == {
        "status": "rejected",
        "requester": "researcher",
        "reviewer": "admin",
    }
