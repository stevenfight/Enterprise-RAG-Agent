# -*- coding: utf-8 -*-
"""E-T20 用户、角色与会话身份 API 的 TDD 测试。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.durable_execution import DurableExecutionStore
from src.v7_metadata_store import V7MetadataStore


def _client(tmp_path: Path) -> TestClient:
    from src import research_task_api
    research_task_api.configure_research_task_store(
        DurableExecutionStore(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    )
    app = FastAPI()
    app.include_router(research_task_api.router)
    return TestClient(app)


def test_bootstrap_admin_login_and_current_identity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("RESEARCH_BOOTSTRAP_PASSWORD", "strong-password")
    monkeypatch.setenv("RESEARCH_SESSION_COOKIE_SECURE", "false")
    client = _client(tmp_path)

    login = client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"})
    current = client.get("/api/research/auth/me")

    assert login.status_code == 200
    assert "research_session" in login.headers.get("set-cookie", "")
    assert current.status_code == 200
    assert current.json()["username"] == "admin"
    assert "approver" in current.json()["roles"]


def test_login_rejects_invalid_password_and_missing_bootstrap(tmp_path: Path) -> None:
    client = _client(tmp_path)
    missing = client.post("/api/research/auth/login", json={"username": "nobody", "password": "wrong"})
    assert missing.status_code == 401
