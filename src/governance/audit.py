"""D1.4 只追加审计事件与任务回放查询。

设计依据：spec-governance-operations.md「审计与脱敏」与 design.md D 段——
审计事件只追加，包含 actor、action、resource、result、timestamp、correlation_id；
审核人员按任务回放可还原计划、工具、审批、关键输入输出、模型版本和最终结论。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from src.governance.redaction import redact_sensitive_fields
from src.v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class AuditEvent:
    """待写入的审计事件；detail 携带关键输入输出、模型版本等上下文。"""

    task_id: str
    run_id: str
    actor: str
    action: str
    resource: str
    result: str
    detail: dict[str, Any]
    correlation_id: str


@dataclass(frozen=True)
class AuditRecord:
    """持久化后的审计记录，created_at 来自数据库时钟，保证回放时间线可信。"""

    audit_id: int
    event: AuditEvent
    created_at: str

    # 便捷属性：直接透出事件关键字段，兼容 record.action 与 record.event.action 两种访问方式
    @property
    def task_id(self) -> str:
        return self.event.task_id

    @property
    def run_id(self) -> str:
        return self.event.run_id

    @property
    def actor(self) -> str:
        return self.event.actor

    @property
    def action(self) -> str:
        return self.event.action

    @property
    def resource(self) -> str:
        return self.event.resource

    @property
    def result(self) -> str:
        return self.event.result

    @property
    def detail(self) -> dict[str, Any]:
        return self.event.detail

    @property
    def correlation_id(self) -> str:
        return self.event.correlation_id


class GovernanceAuditStore:
    """只追加审计账本：仅提供追加与按任务回放查询，不提供更新或删除路径。"""

    def __init__(self, store: V7MetadataStore) -> None:
        self._store = store
        store.initialize()

    def append(self, event: AuditEvent) -> AuditRecord:
        """追加一条审计事件并提交独立事务。"""
        self._validate(event)
        with self._store.connect() as connection:
            record = self._insert(connection, event)
            connection.commit()
            return record

    def append_in_transaction(self, connection: sqlite3.Connection, event: AuditEvent) -> AuditRecord:
        """在调用方事务内追加审计事件，不提交；提交与回滚由调用方控制。"""
        self._validate(event)
        return self._insert(connection, event)

    def replay_task(self, task_id: str) -> tuple[AuditRecord, ...]:
        """按 audit_id 升序返回任务全部审计事件，用于重建关键路径。"""
        with self._store.connect() as connection:
            rows = connection.execute(
                """
                SELECT audit_id, task_id, run_id, actor, action, resource, result,
                       detail_json, correlation_id, created_at
                FROM v7_governance_audit_events
                WHERE task_id = ?
                ORDER BY audit_id
                """,
                (task_id,),
            ).fetchall()
        return tuple(
            AuditRecord(
                audit_id=int(row[0]),
                event=AuditEvent(
                    task_id=row[1],
                    run_id=row[2],
                    actor=row[3],
                    action=row[4],
                    resource=row[5],
                    result=row[6],
                    detail=json.loads(row[7]),
                    correlation_id=row[8],
                ),
                created_at=row[9],
            )
            for row in rows
        )

    @staticmethod
    def _validate(event: AuditEvent) -> None:
        """写入前校验必填字段，保证回放语义完整。"""
        if not event.task_id:
            raise ValueError("审计事件 task_id 不得为空")
        if not event.action:
            raise ValueError("审计事件 action 不得为空")
        if not event.actor:
            raise ValueError("审计事件 actor 不得为空")

    @staticmethod
    def _insert(connection: sqlite3.Connection, event: AuditEvent) -> AuditRecord:
        """在给定连接上插入审计事件，提交时机由调用方决定。"""
        cursor = connection.execute(
            """
            INSERT INTO v7_governance_audit_events
                (task_id, run_id, actor, action, resource, result, detail_json, correlation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.task_id,
                event.run_id,
                event.actor,
                event.action,
                event.resource,
                event.result,
                # D1.5：持久化前对 detail 做敏感字段脱敏，原始事件对象保持不变
                json.dumps(redact_sensitive_fields(event.detail), ensure_ascii=False, sort_keys=True),
                event.correlation_id,
            ),
        )
        audit_id = int(cursor.lastrowid)
        created_at = connection.execute(
            "SELECT created_at FROM v7_governance_audit_events WHERE audit_id = ?",
            (audit_id,),
        ).fetchone()[0]
        return AuditRecord(audit_id=audit_id, event=event, created_at=created_at)
