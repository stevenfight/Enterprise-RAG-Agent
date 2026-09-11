# -*- coding: utf-8 -*-
"""C2.6 研究任务六端点 API 的 TDD 测试。

覆盖任务创建、查询、事件流、暂停、恢复、取消；
控制端点必须携带 command_id + expected_revision，并复用 C0 的幂等与 CAS 语义。
"""

import json
import os
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

    os.environ["RESEARCH_BOOTSTRAP_USERNAME"] = "admin"
    os.environ["RESEARCH_BOOTSTRAP_PASSWORD"] = "strong-password"
    os.environ["RESEARCH_SESSION_COOKIE_SECURE"] = "false"
    store = DurableExecutionStore(V7MetadataStore(tmp_path / "v7_metadata.sqlite3"))
    research_task_api.configure_research_task_store(store)
    app = FastAPI()
    app.include_router(research_task_api.router)
    client = TestClient(app)
    assert client.post("/api/research/auth/login", json={"username": "admin", "password": "strong-password"}).status_code == 200
    return client, store, ResearchTaskAdapter(store)


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


def test_create_task_with_plan_returns_budget_snapshot(tmp_path: Path):
    """E-T01：创建任务时必须同时生成可读取的计划与预算快照。"""
    client, _, _ = _build_client(tmp_path)
    response = client.post("/api/research/tasks", json={
        "task_id": "t-plan", "dag_step_ids": ["retrieve"],
        "objective": "比较收入", "scope": ["收入"], "estimated_cost": "2.50", "risks": ["口径差异"],
    })
    assert response.status_code == 200
    assert response.json()["plan"]["task_id"] == "t-plan"
    assert response.json()["plan"]["estimated_cost"] == "2.50"
    detail = client.get("/api/research/tasks/t-plan")
    assert detail.json()["plan"]["scope"] == ["收入"]


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


def test_get_latest_persisted_report_endpoint(tmp_path: Path):
    from src.research_delivery import Claim, ClaimSupportKind, ReportReviewStatus, ResearchReport
    from src.research_report_repository import ResearchReportRepository
    client, store, _ = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-report", "dag_step_ids": ["plan"]})
    ResearchReportRepository(store.metadata_store).append(ResearchReport.create(report_id="r-1", task_id="t-report", plan_id="p-1", report_version=1, data_version="facts-1", review_status=ReportReviewStatus.PENDING_REVIEW, claims=[Claim.create(claim_id="c-1", text="结论", support_kind=ClaimSupportKind.FACT, fact_ids=["f-1"])]))
    response = client.get("/api/research/tasks/t-report/report")
    assert response.status_code == 200
    assert response.json()["claims"][0]["fact_ids"] == ["f-1"]


def test_create_report_uses_persisted_plan_and_generates_immutable_versions(tmp_path: Path):
    """E-T15：浏览器只提交声明输入，报告身份、版本和审核状态由服务端确定。"""
    client, _, _ = _build_client(tmp_path)
    client.post("/api/research/tasks", json={
        "task_id": "t-create-report", "dag_step_ids": ["retrieve"],
        "objective": "比较收入", "scope": ["收入"], "estimated_cost": "2.50",
    })
    first = client.post("/api/research/tasks/t-create-report/report", json={
        "data_version": "facts-1",
        "claims": [{
            "claim_id": "claim-1", "text": "收入增长", "support_kind": "fact",
            "fact_ids": ["fact-1"],
        }],
    })
    second = client.post("/api/research/tasks/t-create-report/report", json={
        "data_version": "facts-2",
        "claims": [{
            "claim_id": "claim-2", "text": "收入继续增长", "support_kind": "source",
            "source_ids": ["source-2"],
        }],
    })

    assert first.status_code == 200
    assert first.json()["report_id"] == "research-report:t-create-report:1"
    assert first.json()["plan_id"] == "research-plan:t-create-report:1"
    assert first.json()["report_version"] == 1
    assert first.json()["review_status"] == "pending_review"
    assert second.status_code == 200
    assert second.json()["report_version"] == 2
    assert second.json()["report_id"] == "research-report:t-create-report:2"
    assert client.get("/api/research/tasks/t-create-report/report").json()["claims"][0]["claim_id"] == "claim-2"


def test_create_report_requires_researcher_role(tmp_path: Path):
    client, store, _ = _build_client(tmp_path)
    client.post("/api/research/tasks", json={
        "task_id": "t-report-role", "dag_step_ids": ["retrieve"],
        "objective": "比较收入", "scope": ["收入"], "estimated_cost": "2.50",
    })
    with store.metadata_store.connect() as connection:
        connection.execute(
            "DELETE FROM v7_research_user_roles WHERE user_id=? AND role_id=?",
            ("user:admin", "researcher"),
        )
        connection.commit()

    response = client.post("/api/research/tasks/t-report-role/report", json={
        "data_version": "facts-1",
        "claims": [{
            "claim_id": "claim-1", "text": "收入增长", "support_kind": "fact",
            "fact_ids": ["fact-1"],
        }],
    })

    assert response.status_code == 403
    assert response.json()["detail"]["message"] == "当前用户没有创建报告权限"


def test_create_report_rejects_unknown_task_or_task_without_persisted_plan(tmp_path: Path):
    client, _, _ = _build_client(tmp_path)
    payload = {
        "data_version": "facts-1",
        "claims": [{"claim_id": "claim-1", "text": "结论", "support_kind": "fact", "fact_ids": ["fact-1"]}],
    }
    unknown = client.post("/api/research/tasks/ghost/report", json=payload)
    client.post("/api/research/tasks", json={"task_id": "t-no-plan", "dag_step_ids": ["retrieve"]})
    no_plan = client.post("/api/research/tasks/t-no-plan/report", json=payload)

    assert unknown.status_code == 404
    assert no_plan.status_code == 409
    assert no_plan.json()["detail"]["message"] == "任务尚未持久化研究计划"


def test_create_report_rejects_claim_without_auditable_support(tmp_path: Path):
    client, _, _ = _build_client(tmp_path)
    client.post("/api/research/tasks", json={
        "task_id": "t-invalid-report", "dag_step_ids": ["retrieve"],
        "objective": "比较收入", "scope": ["收入"], "estimated_cost": "2.50",
    })
    response = client.post("/api/research/tasks/t-invalid-report/report", json={
        "data_version": "facts-1",
        "claims": [{"claim_id": "claim-invalid", "text": "无依据结论", "support_kind": "fact"}],
    })

    assert response.status_code == 422
    assert client.get("/api/research/tasks/t-invalid-report/report").status_code == 404


def test_list_tasks_returns_only_research_runs_in_stable_order(tmp_path: Path):
    """研究任务列表不得暴露非研究 C0 运行，并使用稳定任务 ID 顺序。"""
    client, store, _ = _build_client(tmp_path)
    store.create_run("document:ingestion")
    client.post("/api/research/tasks", json={"task_id": "task-b", "dag_step_ids": ["plan"]})
    client.post("/api/research/tasks", json={"task_id": "task-a", "dag_step_ids": ["plan"]})

    response = client.get("/api/research/tasks")

    assert response.status_code == 200
    assert [item["task_id"] for item in response.json()["items"]] == ["task-a", "task-b"]
    assert [item["run_id"] for item in response.json()["items"]] == [
        "research:task-a",
        "research:task-b",
    ]


def test_list_tasks_preserves_dag_steps_from_persisted_plan(tmp_path: Path):
    client, _, _ = _build_client(tmp_path)
    client.post("/api/research/tasks", json={
        "task_id": "task-dag-list",
        "dag_step_ids": ["plan", "retrieve", "report"],
        "objective": "展示 DAG",
        "scope": ["收入"],
        "estimated_cost": "1",
    })

    response = client.get("/api/research/tasks")

    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["task_id"] == "task-dag-list")
    assert item["dag_step_ids"] == ["plan", "retrieve", "report"]


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


def test_execution_summary_exposes_step_progress_completion_time_and_safe_failure_reason(tmp_path: Path):
    client, _, adapter = _build_client(tmp_path)
    client.post("/api/research/tasks", json={"task_id": "t-progress", "dag_step_ids": ["plan", "retrieve"]})
    adapter.start_task("t-progress", 0, "start-progress", actor="worker")
    claimed = adapter.claim_step("t-progress", "plan", "worker-progress")
    adapter.commit_step(
        "t-progress", "plan", claimed.attempt.attempt_token, claimed.attempt.owner_token, 1,
        dag_step_ids=("plan", "retrieve"), dependency_versions={},
        invocation={"idempotency_key": "progress-plan", "status": "succeeded"},
    )
    adapter.complete_task("t-progress", 1, "complete-progress", actor="worker")

    completed = client.get("/api/research/tasks/t-progress/execution")

    assert completed.status_code == 200
    assert completed.json() == {
        "completed_step_ids": ["plan"],
        "current_step_id": None,
        "completed_at": completed.json()["completed_at"],
        "failure_reason": None,
    }
    assert completed.json()["completed_at"]

    client.post("/api/research/tasks", json={"task_id": "t-failure", "dag_step_ids": ["plan"]})
    adapter.start_task("t-failure", 0, "start-failure", actor="worker")
    failure = adapter.failure_decision("execution_failed", retry_count=0, max_retries=0)
    adapter.record_failure("t-failure", failure, actor="worker", reason="检索未返回可审计来源")
    adapter.fail_task("t-failure", 1, "fail-progress", actor="worker")

    failed = client.get("/api/research/tasks/t-failure/execution")

    assert failed.status_code == 200
    assert failed.json()["current_step_id"] is None
    assert failed.json()["completed_at"] is None
    assert failed.json()["failure_reason"] == "检索未返回可审计来源"


def test_api_service_mounts_research_task_routes():
    from src import api_service

    paths = {route.path for route in api_service.app.routes}
    assert "/api/research/tasks" in paths
    assert "/api/research/tasks/{task_id}" in paths
    assert "/api/research/tasks/{task_id}/events" in paths
    assert "/api/research/tasks/{task_id}/pause" in paths
    assert "/api/research/tasks/{task_id}/resume" in paths
    assert "/api/research/tasks/{task_id}/cancel" in paths
