# -*- coding: utf-8 -*-
"""E-T21 全局门禁接受有效研究会话的 TDD 测试。"""
import asyncio


def test_api_auth_middleware_accepts_session_or_existing_bearer(monkeypatch) -> None:
    from src import api_service
    monkeypatch.setattr(api_service, "_api_key", "legacy-key")
    calls = []
    async def app(scope, receive, send):
        calls.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    async def request(headers, session):
        monkeypatch.setattr(api_service, "_research_session_is_valid", lambda _: session)
        status = {}
        async def receive(): return {"type": "http.request", "body": b"", "more_body": False}
        async def send(message):
            if message["type"] == "http.response.start": status["code"] = message["status"]
        await api_service.APIAuthMiddleware(app)({"type": "http", "method": "GET", "path": "/api/research/tasks", "headers": headers, "query_string": b""}, receive, send)
        return status["code"]
    assert asyncio.run(request([], True)) == 200
    assert asyncio.run(request([(b"authorization", b"Bearer legacy-key")], False)) == 200
    assert asyncio.run(request([], False)) == 401
