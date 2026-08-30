"""D1.5 敏感字段脱敏测试（D-T08）。

规格依据：spec-governance-operations.md「审计与脱敏」——
日志、追踪和报告持久化前对敏感字段实施脱敏，原结构不改动。
"""

from __future__ import annotations

import pytest

from src.governance.audit import AuditEvent, GovernanceAuditStore
from src.governance.redaction import REDACTED_VALUE, redact_sensitive_fields
from src.v7_metadata_store import V7MetadataStore


@pytest.fixture()
def metadata_store(tmp_path):
    """每个用例独立初始化的 V7 元数据库。"""
    store = V7MetadataStore(tmp_path / "governance.db")
    store.initialize()
    return store


def test_top_level_sensitive_fields_masked() -> None:
    """顶层敏感键（api_key/password）必须替换为统一掩码。"""
    data = {"api_key": "sk-123", "password": "p", "note": "营收增长"}
    out = redact_sensitive_fields(data)
    assert out["api_key"] == REDACTED_VALUE
    assert out["password"] == REDACTED_VALUE
    assert out["note"] == "营收增长"


def test_nested_and_list_structures_masked() -> None:
    """嵌套字典与列表内的敏感键同样脱敏，大小写与连字符变体不遗漏。"""
    data = {
        "steps": [{"authorization": "Bearer abc"}, {"safe": 1}],
        "headers": {"Cookie": "sid=1", "X-Api-Key": "k"},
    }
    out = redact_sensitive_fields(data)
    assert out["steps"][0]["authorization"] == REDACTED_VALUE
    assert out["steps"][1] == {"safe": 1}
    assert out["headers"]["Cookie"] == REDACTED_VALUE
    assert out["headers"]["X-Api-Key"] == REDACTED_VALUE


def test_original_dict_not_mutated() -> None:
    """脱敏返回新结构，不修改调用方原始数据。"""
    data = {"token": "t"}
    out = redact_sensitive_fields(data)
    assert data["token"] == "t"
    assert out["token"] == REDACTED_VALUE


def test_audit_detail_masked_before_persistence(metadata_store) -> None:
    """审计事件 detail 持久化前自动脱敏，回放读不到明文敏感值。"""
    audit = GovernanceAuditStore(metadata_store)
    audit.append(
        AuditEvent(
            task_id="task-1",
            run_id="run-1",
            actor="planner",
            action="tool_executed",
            resource="tool:read_fact",
            result="ok",
            detail={"api_key": "sk-1", "fact_id": "F1"},
            correlation_id="c1",
        )
    )
    records = audit.replay_task("task-1")
    assert records[0].event.detail["api_key"] == REDACTED_VALUE
    assert records[0].event.detail["fact_id"] == "F1"
