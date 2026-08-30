# -*- coding: utf-8 -*-
"""C2.6 研究任务六端点 API 的 TDD 测试。

覆盖任务创建、查询、事件流、暂停、恢复、取消；
控制端点必须携带 command_id + expected_revision，并复用 C0 的幂等与 CAS 语义。
"""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.durable_execution import DurableExecutionStore
from src.research_task_adapter import ResearchTaskAdapter
from src.v7_metadata_store import V7MetadataStore


def _build_client(tmp_path: Path) -> tuple[TestClient, DurableExecutionStore, ResearchTaskAdapter]:
    """构造挂载了研究任务路由的测试应用，并绑定独立的临时元数据库。"""
    from src import research_task_api

    store = DurableExecutionStore(V7MetadataStore(tmp_path / "v7_metadata.sqlite3"))
    research_task_api.configure_research_task_store(store)
    app = FastAPI()
    app.include_router(research_task_api.router)
    return TestClient(app), store, ResearchTaskAdapter(store)


def _sse_frames(body: str) -> list[dict]:
    """解析 SSE 正文中的 data 帧为 JSON 对象列表。"""
    frames: list[dict] = []
    for chunk in body.split("\n\n"):
        data_lines = [
            line[len("data:"):].strip() for line in chunk.split("\n") if line.startswith("data:")
        ]
        if data_lines:
            frames.append(json.loads("\n".join(data_lines)))
    return frames


def test_create_task_endpoint_returns_pending_snapshot(tmp_path: Path):
    client, _, _ = _build_client(tmp_path)

    response = client.post(
        "/api/research/tasks",
        json={"task_id": "t-create", "dag_step_ids": ["plan", "execute"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "t-create"
    assert body["run_id"] == "research:t-create"
    assert body["status"] == "pending"
    assert body["revision"] == 0
    assert body["dag_step_ids"] == ["plan", "execute"]


def test_create_task_rejects_duplicate_task_id(tmp_path: Path):
    client, _, _ = _build_client(tmp_path)
    payload = {"task_id": "t-dup", "dag_step_ids": ["plan"]}
    first = client.post("/api/research/tasks", json=payload)
    assert first.status_code == 200

    second = client.post("/api/research/tasks", json=payload)

    assert second.status_code == 409


def test_create_task_validates_request_body(tmp_path: Path):
    client, _, _ = _build_client(tmp_path)

    missing_task = client.post("/api/research/tasks", json={"dag_step_ids": ["plan"]})
    empty_steps = client.post("/api/research/tasks", json={"task_id": "t-empty", "dag_step_ids": []})

    assert missing_task.status_code == 422
    assert empty_steps.status_code == 422


def test_get_task_snapshot_endpoint(tmp_path: Path):
    client, _, adapter = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-get", "dag_step_ids": ["plan"]})

    initial = client.get("/api/research/tasks/t-get")
    assert initial.status_code == 200
    assert initial.json()["status"] == "pending"
    assert initial.json()["revision"] == 0

    adapter.start_task("t-get", 0, "cmd-worker-start", actor="worker")

    running = client.get("/api/research/tasks/t-get")
    assert running.status_code == 200
    assert running.json()["status"] == "running"
    assert running.json()["revision"] == 1


def test_get_unknown_task_returns_404(tmp_path: Path):
    client, _, _ = _build_client(tmp_path)

    response = client.get("/api/research/tasks/ghost")

    assert response.status_code == 404


def test_pause_resume_cancel_control_endpoints(tmp_path: Path):
    client, _, adapter = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-flow", "dag_step_ids": ["plan"]})
    adapter.start_task("t-flow", 0, "cmd-worker-start", actor="worker")

    paused = client.post(
        "/api/research/tasks/t-flow/pause",
        json={"command_id": "cmd-pause-1", "expected_revision": 1},
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["revision"] == 2

    resumed = client.post(
        "/api/research/tasks/t-flow/resume",
        json={"command_id": "cmd-resume-1", "expected_revision": 2},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"
    assert resumed.json()["revision"] == 3

    cancelled = client.post(
        "/api/research/tasks/t-flow/cancel",
        json={"command_id": "cmd-cancel-1", "expected_revision": 3},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["revision"] == 4


def test_control_endpoints_require_command_id_and_revision(tmp_path: Path):
    client, _, adapter = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-guard", "dag_step_ids": ["plan"]})
    adapter.start_task("t-guard", 0, "cmd-worker-start", actor="worker")

    missing_command = client.post(
        "/api/research/tasks/t-guard/pause", json={"expected_revision": 1}
    )
    missing_revision = client.post(
        "/api/research/tasks/t-guard/pause", json={"command_id": "cmd-x"}
    )

    assert missing_command.status_code == 422
    assert missing_revision.status_code == 422


def test_control_endpoint_stale_revision_returns_409_with_current(tmp_path: Path):
    client, _, adapter = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-stale", "dag_step_ids": ["plan"]})
    adapter.start_task("t-stale", 0, "cmd-worker-start", actor="worker")

    response = client.post(
        "/api/research/tasks/t-stale/pause",
        json={"command_id": "cmd-stale-1", "expected_revision": 99},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["current_revision"] == 1


def test_duplicate_command_id_replays_original_result(tmp_path: Path):
    client, _, adapter = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-idem", "dag_step_ids": ["plan"]})
    adapter.start_task("t-idem", 0, "cmd-worker-start", actor="worker")

    first = client.post(
        "/api/research/tasks/t-idem/pause",
        json={"command_id": "cmd-same", "expected_revision": 1},
    )
    replay = client.post(
        "/api/research/tasks/t-idem/pause",
        json={"command_id": "cmd-same", "expected_revision": 1},
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["status"] == first.json()["status"]
    assert replay.json()["revision"] == first.json()["revision"]


def test_events_endpoint_streams_sse_frames(tmp_path: Path):
    client, _, adapter = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-events", "dag_step_ids": ["plan"]})
    adapter.start_task("t-events", 0, "cmd-worker-start", actor="worker")

    response = client.get("/api/research/tasks/t-events/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = _sse_frames(response.text)
    event_frames = [frame for frame in frames if frame.get("event_type") != "window_end"]
    window_frames = [frame for frame in frames if frame.get("event_type") == "window_end"]
    assert [frame["event_type"] for frame in event_frames] == ["run_created", "run_transitioned"]
    assert [frame["event_id"] for frame in event_frames] == [1, 2]
    assert event_frames[1]["status"] == "running"
    assert len(window_frames) == 1
    assert window_frames[0]["next_event_id"] == 2
    assert window_frames[0]["resync_required"] is False


def test_events_endpoint_resumes_from_cursor(tmp_path: Path):
    client, _, adapter = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-cursor", "dag_step_ids": ["plan"]})
    adapter.start_task("t-cursor", 0, "cmd-worker-start", actor="worker")

    response = client.get("/api/research/tasks/t-cursor/events?after_event_id=1")

    frames = _sse_frames(response.text)
    event_frames = [frame for frame in frames if frame.get("event_type") != "window_end"]
    window_frames = [frame for frame in frames if frame.get("event_type") == "window_end"]
    assert [frame["event_id"] for frame in event_frames] == [2]
    assert window_frames[0]["next_event_id"] == 2


def test_events_endpoint_returns_resync_frame_for_stale_cursor(tmp_path: Path):
    client, store, adapter = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-resync", "dag_step_ids": ["plan"]})
    adapter.start_task("t-resync", 0, "cmd-worker-start", actor="worker")
    events = store.events("research:t-resync")
    with store.metadata_store.connect() as connection:
        connection.execute(
            "UPDATE v7_task_events SET created_at='2020-01-01 00:00:00' WHERE event_id=?",
            (events[0].event_id,),
        )
        connection.commit()

    response = client.get("/api/research/tasks/t-resync/events?after_event_id=0")

    frames = _sse_frames(response.text)
    event_frames = [frame for frame in frames if frame.get("event_type") != "window_end"]
    window_frames = [frame for frame in frames if frame.get("event_type") == "window_end"]
    assert event_frames == []
    assert len(window_frames) == 1
    assert window_frames[0]["resync_required"] is True
    assert window_frames[0]["oldest_event_id"] == events[1].event_id


def test_events_endpoint_rejects_negative_cursor(tmp_path: Path):
    client, _, _ = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-neg", "dag_step_ids": ["plan"]})

    response = client.get("/api/research/tasks/t-neg/events?after_event_id=-1")

    assert response.status_code == 422


def test_api_service_mounts_research_task_routes():
    from src import api_service

    paths = {route.path for route in api_service.app.routes}
    assert "/api/research/tasks" in paths
    assert "/api/research/tasks/{task_id}" in paths
    assert "/api/research/tasks/{task_id}/events" in paths
    assert "/api/research/tasks/{task_id}/pause" in paths
    assert "/api/research/tasks/{task_id}/resume" in paths
    assert "/api/research/tasks/{task_id}/cancel" in paths
