# -*- coding: utf-8 -*-
"""Agent SSE 鉴权必须在进入下游路由前完成。"""

import asyncio

from fastapi.testclient import TestClient
import pytest


def _stream_request_status(monkeypatch, headers, research_session_valid=False):
    """以无副作用下游应用验证中间件是否放行 SSE 请求。"""
    from src import api_service

    monkeypatch.setattr(api_service, "_api_key", "stream-test-key")
    monkeypatch.setattr(
        api_service,
        "_research_session_is_valid",
        lambda _: research_session_valid,
    )
    downstream_calls = []

    async def downstream(scope, receive, send):
        downstream_calls.append(scope["path"])
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def request():
        status = {}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/agent/stream",
            "headers": headers,
            "query_string": b"query=%E8%90%A5%E6%94%B6",
        }
        await api_service.APIAuthMiddleware(downstream)(scope, receive, send)
        return status["code"]

    return asyncio.run(request()), downstream_calls


def test_agent_stream_requires_valid_credentials_before_downstream(monkeypatch):
    """无 Key 或错误 Key 的 SSE 请求必须在中间件被拒绝。"""
    from src import api_service

    assert "/api/agent/stream" not in api_service.APIAuthMiddleware.SKIP_PATHS

    status, calls = _stream_request_status(monkeypatch, [])
    assert status == 401
    assert calls == []

    status, calls = _stream_request_status(
        monkeypatch,
        [(b"authorization", b"Bearer wrong-key")],
    )
    assert status == 401
    assert calls == []


def test_agent_stream_accepts_existing_bearer_or_research_session(monkeypatch):
    """正确 Bearer Key 与既有有效研究会话都必须保留 SSE 下游访问。"""
    status, calls = _stream_request_status(
        monkeypatch,
        [(b"authorization", b"Bearer stream-test-key")],
    )
    assert status == 204
    assert calls == ["/api/agent/stream"]

    status, calls = _stream_request_status(monkeypatch, [], research_session_valid=True)
    assert status == 204
    assert calls == ["/api/agent/stream"]


def test_health_check_remains_anonymous_whitelist(monkeypatch):
    """SSE 修复不得收紧既有健康检查白名单。"""
    from src import api_service

    monkeypatch.setattr(api_service, "_research_session_is_valid", lambda _: False)
    calls = []

    async def downstream(scope, receive, send):
        calls.append(scope["path"])
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def request():
        status = {}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]

        await api_service.APIAuthMiddleware(downstream)(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/health",
                "headers": [],
                "query_string": b"",
            },
            receive,
            send,
        )
        return status["code"]

    assert asyncio.run(request()) == 204
    assert calls == ["/api/health"]


def test_cors_preflight_reaches_cors_middleware_without_weakening_sse_auth():
    """真实 CORS 预检交由 CORS 中间件处理，实际 SSE 请求仍须认证。"""
    from src import api_service

    client = TestClient(api_service.app)
    preflight_headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    allowed = client.options("/api/agent/stream", headers=preflight_headers)
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers["access-control-allow-credentials"] == "true"

    denied = client.options(
        "/api/agent/stream",
        headers={
            "Origin": "https://unconfigured.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert denied.status_code == 400
    assert denied.headers.get("access-control-allow-origin") is None


def test_cors_allowed_origins_require_explicit_safe_configuration(monkeypatch):
    """部署来源必须显式配置，非法值不能让携带 Cookie 的 CORS 放宽。"""
    from src import api_service

    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert api_service._cors_allowed_origins() == (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://app.example.test,http://localhost:5173",
    )
    assert api_service._cors_allowed_origins() == (
        "https://app.example.test",
        "http://localhost:5173",
    )

    for value in ("", "*", "https://app.example.test/path", "ftp://app.example.test", "https://app.example.test,https://app.example.test"):
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", value)
        with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS"):
            api_service._cors_allowed_origins()
