# -*- coding: utf-8 -*-
"""C2.6 研究任务持久执行的 REST API。

六类端点：创建、查询、事件流、暂停、恢复、取消。
任务状态与 revision 全部来自 C0 可恢复执行内核，本模块不复制状态；
控制端点必须携带 command_id 与 expected_revision，重复 command_id
由 C0 幂等回放原结果，过期 revision 返回 409 与当前 revision。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.durable_execution import (
    DurableExecutionStore,
    InvalidRunTransitionError,
    RevisionConflictError,
)
from src.research_task_adapter import ResearchTaskAdapter, ResearchTaskSnapshot
from src.research_task_events import ResearchTaskEventStream
from src.v7_metadata_store import V7MetadataStore

router = APIRouter(prefix="/api/research", tags=["research-tasks"])

# 事件保留期默认 24 小时；调用方可通过查询参数覆盖
_DEFAULT_RETENTION_SECONDS = 86400

# 模块级执行仓储持有者：测试通过 configure_research_task_store 注入独立实例
_execution_store: DurableExecutionStore | None = None


class CreateTaskRequest(BaseModel):
    """创建研究任务请求体。"""

    task_id: str = Field(min_length=1)
    dag_step_ids: list[str] = Field(min_length=1)


class TaskCommandRequest(BaseModel):
    """研究任务控制命令请求体，必须携带幂等命令 ID 与期望 revision。"""

    command_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)


def configure_research_task_store(execution_store: DurableExecutionStore) -> None:
    """注入执行仓储；供测试与装配方使用。"""
    global _execution_store
    _execution_store = execution_store


def _execution_store_or_default() -> DurableExecutionStore:
    """返回注入的仓储；未注入时惰性绑定默认 V7 元数据库。"""
    global _execution_store
    if _execution_store is None:
        v7_root = Path(__file__).resolve().parent.parent / "data" / "v7"
        _execution_store = DurableExecutionStore(V7MetadataStore(v7_root / "metadata.sqlite3"))
    return _execution_store


def _adapter() -> ResearchTaskAdapter:
    return ResearchTaskAdapter(_execution_store_or_default())


def _snapshot_payload(snapshot: ResearchTaskSnapshot) -> dict[str, Any]:
    return {
        "task_id": snapshot.task_id,
        "run_id": snapshot.run_id,
        "status": snapshot.status,
        "revision": snapshot.revision,
        "dag_step_ids": list(snapshot.dag_step_ids),
    }


def _control_transition(
    task_id: str,
    action: str,
    request: TaskCommandRequest,
) -> dict[str, Any]:
    """执行控制命令并统一映射 C0 异常到 HTTP 语义。"""
    try:
        if action == "pause":
            snapshot = _adapter().pause_task(
                task_id, request.expected_revision, request.command_id, actor="api"
            )
        elif action == "resume":
            snapshot = _adapter().resume_task(
                task_id, request.expected_revision, request.command_id, actor="api"
            )
        else:
            snapshot = _adapter().cancel_task(
                task_id, request.expected_revision, request.command_id, actor="api"
            )
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    except RevisionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "current_revision": exc.current_revision},
        )
    except InvalidRunTransitionError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)})
    return _snapshot_payload(snapshot)


@router.post("/tasks", summary="创建研究任务")
def create_task(request: CreateTaskRequest) -> dict[str, Any]:
    """在 C0 创建 pending 运行，DAG 步骤由调用方按 C1 检查点协议保存。"""
    try:
        snapshot = _adapter().create_task(request.task_id, request.dag_step_ids)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail={"message": "任务已存在"}) from exc
    return _snapshot_payload(snapshot)


@router.get("/tasks/{task_id}", summary="查询研究任务快照")
def get_task(task_id: str) -> dict[str, Any]:
    """读取 C0 运行的当前状态与 revision，不复制任务状态。"""
    try:
        snapshot = _adapter().task_snapshot(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    return _snapshot_payload(snapshot)


@router.get("/tasks/{task_id}/events", summary="订阅研究任务事件流")
def stream_task_events(
    task_id: str,
    after_event_id: int | None = Query(default=None, ge=0),
    retention_seconds: int = Query(default=_DEFAULT_RETENTION_SECONDS, gt=0),
) -> StreamingResponse:
    """按持久事件 ID 输出 SSE 窗口；游标早于保留窗口时要求重同步。"""
    try:
        _adapter().task_snapshot(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    page = ResearchTaskEventStream(_execution_store_or_default()).read(
        task_id,
        after_event_id=after_event_id,
        now=now,
        retention_seconds=retention_seconds,
    )

    def frames() -> Iterator[str]:
        for event in page.events:
            frame: dict[str, Any] = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "revision": event.revision,
            }
            frame.update(event.payload)
            yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
        yield "data: " + json.dumps(
            {
                "event_type": "window_end",
                "next_event_id": page.next_event_id,
                "oldest_event_id": page.oldest_event_id,
                "resync_required": page.resync_required,
            },
            ensure_ascii=False,
        ) + "\n\n"

    return StreamingResponse(frames(), media_type="text/event-stream")


@router.post("/tasks/{task_id}/pause", summary="暂停研究任务")
def pause_task(task_id: str, request: TaskCommandRequest) -> dict[str, Any]:
    return _control_transition(task_id, "pause", request)


@router.post("/tasks/{task_id}/resume", summary="恢复研究任务")
def resume_task(task_id: str, request: TaskCommandRequest) -> dict[str, Any]:
    return _control_transition(task_id, "resume", request)


@router.post("/tasks/{task_id}/cancel", summary="取消研究任务")
def cancel_task(task_id: str, request: TaskCommandRequest) -> dict[str, Any]:
    return _control_transition(task_id, "cancel", request)
