"""D1.2/D1.2.1/D1.3/D1.4.1 参数绑定、时效限制的审批记录与同事务消费。

设计依据：spec-governance-operations.md「工具权限」与 design.md D 段——
- D1.2：审批与规范化参数哈希绑定，参数变化后失效；带 expires_at 时效限制；
- D1.2.1：审批哈希绑定 task revision、plan hash、事实/制品版本与 index generation，
  任一依赖变化使旧审批失效（D-T11）；
- D1.3：关键冲突裁决与正式报告签发的门禁查询（check_gate）；
- D1.4.1：审批消费、业务状态迁移与审计事件在同一事务提交（D-T12）。
"""

from __future__ import annotations

import hashlib
import json
import uuid
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable

from src.governance.audit import AuditEvent, GovernanceAuditStore
from src.v7_metadata_store import V7MetadataStore

# D1.3：审批主题常量——当前仅冲突裁决与报告签发为强制门禁，
# 工具执行通道保留（真实高风险工具出现前不强制启用）。
SUBJECT_CONFLICT_RESOLUTION = "conflict_resolution"
SUBJECT_REPORT_SIGNOFF = "report_signoff"
SUBJECT_TOOL_EXECUTION = "tool_execution"

# 门禁裁决原因语义：missing（无有效审批）/ params_changed（参数变化）/
# expired（过期）/ dependencies_changed（依赖哈希变化）/ allowed（放行）。
_REASON_MISSING = "missing"
_REASON_PARAMS_CHANGED = "params_changed"
_REASON_EXPIRED = "expired"
_REASON_DEPENDENCIES_CHANGED = "dependencies_changed"
_REASON_ALLOWED = "allowed"


@dataclass(frozen=True)
class ApprovalBinding:
    """审批依赖绑定：任一字段变化都会使旧审批失效（D-T11）。"""

    task_revision: int
    plan_hash: str
    fact_version: str
    artifact_version: str
    index_generation: str


@dataclass(frozen=True)
class ApprovalRequest:
    """审批请求：携带任务上下文、规范化参数、依赖绑定、审批人与时效。"""

    task_id: str
    run_id: str
    subject: str
    subject_id: str
    params: dict[str, Any]
    binding: ApprovalBinding
    approver: str
    expires_at: datetime


@dataclass(frozen=True)
class ApprovalRecord:
    """审批结果记录：approval_id 供门禁引用，consumed_at 由消费事务写入。"""

    approval_id: str
    status: str
    consumed_at: str | None


@dataclass(frozen=True)
class GateDecision:
    """门禁裁决：allowed 为放行结论；reason 使用固定语义集合。"""

    allowed: bool
    reason: str
    approval_id: str | None


def _canonical_json(value: Any) -> str:
    """规范化 JSON 序列化：排序键、紧凑分隔符，保证哈希输入稳定。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _canonical_hash(value: Any) -> str:
    """对规范化 JSON 计算 SHA-256 摘要，用于参数哈希与审批绑定摘要。"""
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime:
    """解析数据库中存储的 ISO 时间字符串。"""
    return datetime.fromisoformat(value)


class GovernanceApprovalStore:
    """治理审批存储：授予、门禁查询、消费与同事务消费，审计事件由本类注入。"""

    def __init__(self, store: V7MetadataStore, *, clock: Callable[[], datetime]) -> None:
        self._store = store
        self._clock = clock
        self.audit = GovernanceAuditStore(store)
        store.initialize()

    def grant(self, request: ApprovalRequest) -> ApprovalRecord:
        """授予审批：计算参数哈希与绑定摘要后落库，返回审批记录。"""
        params_hash = _canonical_hash(request.params)
        binding_json = _canonical_json(asdict(request.binding))
        digest = _canonical_hash([request.subject, request.subject_id, params_hash, binding_json])
        approval_id = uuid.uuid4().hex
        with self._store.connect() as connection:
            connection.execute(
                """
                INSERT INTO v7_governance_approvals
                    (approval_id, task_id, run_id, subject, subject_id,
                     params_hash, binding_json, digest, approver, status, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'granted', ?)
                """,
                (
                    approval_id,
                    request.task_id,
                    request.run_id,
                    request.subject,
                    request.subject_id,
                    params_hash,
                    binding_json,
                    digest,
                    request.approver,
                    request.expires_at.isoformat(),
                ),
            )
            connection.commit()
        return ApprovalRecord(approval_id=approval_id, status="granted", consumed_at=None)

    def check_gate(
        self,
        task_id: str,
        subject: str,
        subject_id: str,
        params: dict[str, Any],
        binding: ApprovalBinding,
    ) -> GateDecision:
        """D1.3 门禁查询：无审批/参数变化/过期/依赖变化时阻止，否则放行。"""
        params_hash = _canonical_hash(params)
        binding_json = _canonical_json(asdict(binding))
        now = self._clock()
        with self._store.connect() as connection:
            row = connection.execute(
                """
                SELECT approval_id, params_hash, binding_json, expires_at
                FROM v7_governance_approvals
                WHERE task_id = ? AND subject = ? AND subject_id = ? AND status = 'granted'
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (task_id, subject, subject_id),
            ).fetchone()
        if row is None:
            return GateDecision(allowed=False, reason=_REASON_MISSING, approval_id=None)
        approval_id, stored_params_hash, stored_binding_json, expires_at = row
        if stored_params_hash != params_hash:
            return GateDecision(allowed=False, reason=_REASON_PARAMS_CHANGED, approval_id=None)
        if _parse_time(expires_at) <= now:
            return GateDecision(allowed=False, reason=_REASON_EXPIRED, approval_id=None)
        if stored_binding_json != binding_json:
            return GateDecision(allowed=False, reason=_REASON_DEPENDENCIES_CHANGED, approval_id=None)
        return GateDecision(allowed=True, reason=_REASON_ALLOWED, approval_id=approval_id)

    def consume(self, approval_id: str, *, actor: str) -> ApprovalRecord:
        """消费审批：状态迁移与审计事件在同一事务提交，不可重复消费。"""
        return self.consume_in_transaction(approval_id, actor=actor, business_transition=None)

    def consume_in_transaction(
        self,
        approval_id: str,
        *,
        actor: str,
        business_transition: Callable[[sqlite3.Connection], None] | None,
    ) -> ApprovalRecord:
        """D-T12：业务状态迁移、审批消费与审计事件同事务提交，失败全部回滚。"""
        with self._store.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT status, expires_at FROM v7_governance_approvals WHERE approval_id = ?",
                    (approval_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("审批不存在，无法消费")
                status, expires_at = row
                if status != "granted":
                    raise ValueError("审批已消费，不可重复消费")
                if _parse_time(expires_at) <= self._clock():
                    raise ValueError("审批已过期，不可消费")
                context = connection.execute(
                    "SELECT task_id, run_id, subject, subject_id FROM v7_governance_approvals WHERE approval_id = ?",
                    (approval_id,),
                ).fetchone()
                consumed_at = self._clock().isoformat()
                connection.execute(
                    "UPDATE v7_governance_approvals SET status = 'consumed', consumed_at = ? WHERE approval_id = ?",
                    (consumed_at, approval_id),
                )
                self.audit.append_in_transaction(
                    connection,
                    AuditEvent(
                        task_id=context[0],
                        run_id=context[1],
                        actor=actor,
                        action="approval_consumed",
                        resource=f"{context[2]}:{context[3]}",
                        result="consumed",
                        detail={"approval_id": approval_id},
                        correlation_id=context[1],
                    ),
                )
                if business_transition is not None:
                    business_transition(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return ApprovalRecord(approval_id=approval_id, status="consumed", consumed_at=consumed_at)

    def valid_approval(
        self,
        task_id: str,
        subject: str,
        subject_id: str,
        params: dict[str, Any],
        binding: ApprovalBinding,
    ) -> str | None:
        """返回当前可用的 approval_id；无有效审批时返回 None。"""
        decision = self.check_gate(task_id, subject, subject_id, params, binding)
        return decision.approval_id if decision.allowed else None

    def approval_status(self, approval_id: str) -> str:
        """查询审批状态：granted 或 consumed；不存在时抛出 ValueError。"""
        with self._store.connect() as connection:
            row = connection.execute(
                "SELECT status FROM v7_governance_approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
        if row is None:
            raise ValueError("审批不存在")
        return str(row[0])
