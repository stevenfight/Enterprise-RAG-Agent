"""A-GATE-2 追加式人工签核台账校验与写入。"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


REQUIRED_REVIEW_CHECKS = (
    "document",
    "page",
    "period_and_source_caliber",
    "excerpt",
    "answer",
    "tolerance",
    "tools",
)
VALID_DECISIONS = {"approved", "rejected"}
REQUIRED_RECORD_FIELDS = {
    "case_id",
    "decision",
    "reviewer",
    "reviewed_at",
    "candidate_dataset_version",
    "review_packet_version",
    "checks",
    "comment",
}


class SignoffLedgerError(ValueError):
    """人工签核台账记录不符合当前复核包契约。"""


def _as_case_id_set(pending_case_ids: Iterable[str]) -> set[str]:
    case_ids = {str(case_id) for case_id in pending_case_ids}
    if not case_ids:
        raise SignoffLedgerError("待审核 case ID 集不能为空")
    return case_ids


def _validate_record(
    record: Mapping[str, Any],
    *,
    pending_case_ids: set[str],
    candidate_dataset_version: str,
    review_packet_version: str,
    seen_case_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise SignoffLedgerError("签核记录必须是对象")

    extra_fields = set(record) - REQUIRED_RECORD_FIELDS
    missing_fields = REQUIRED_RECORD_FIELDS - set(record)
    if missing_fields:
        raise SignoffLedgerError(f"签核记录缺少字段: {sorted(missing_fields)}")
    if extra_fields:
        raise SignoffLedgerError(f"签核记录包含未知字段: {sorted(extra_fields)}")

    case_id = record["case_id"]
    if not isinstance(case_id, str) or not case_id.strip():
        raise SignoffLedgerError("case_id 必须是非空字符串")
    if case_id not in pending_case_ids:
        raise SignoffLedgerError(f"未知 case ID: {case_id}")
    if case_id in seen_case_ids:
        raise SignoffLedgerError(f"重复 case ID: {case_id}")

    decision = record["decision"]
    if decision not in VALID_DECISIONS:
        raise SignoffLedgerError("decision 只能是 approved 或 rejected")
    if record["candidate_dataset_version"] != candidate_dataset_version:
        raise SignoffLedgerError("候选集版本不匹配")
    if record["review_packet_version"] != review_packet_version:
        raise SignoffLedgerError("复核包版本不匹配")

    for field in ("reviewer", "reviewed_at", "comment"):
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            raise SignoffLedgerError(f"{field} 必须是非空字符串")

    checks = record["checks"]
    if not isinstance(checks, Mapping):
        raise SignoffLedgerError("checks 必须是对象")
    check_names = set(checks)
    required_checks = set(REQUIRED_REVIEW_CHECKS)
    if check_names != required_checks:
        missing_checks = sorted(required_checks - check_names)
        extra_checks = sorted(check_names - required_checks)
        raise SignoffLedgerError(
            f"核对项不完整: missing={missing_checks}, extra={extra_checks}"
        )
    if any(type(checks[name]) is not bool for name in REQUIRED_REVIEW_CHECKS):
        raise SignoffLedgerError("核对项必须全部使用布尔值")

    return dict(record)


def load_signoff_ledger(
    ledger_path: str | Path,
    *,
    pending_case_ids: Iterable[str],
    candidate_dataset_version: str,
    review_packet_version: str,
) -> list[dict[str, Any]]:
    """读取并校验追加式人工签核台账。"""

    path = Path(ledger_path)
    if not path.exists():
        return []

    case_ids = _as_case_id_set(pending_case_ids)
    records: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw_record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SignoffLedgerError(f"第 {line_number} 行不是有效 JSON") from exc
        record = _validate_record(
            raw_record,
            pending_case_ids=case_ids,
            candidate_dataset_version=candidate_dataset_version,
            review_packet_version=review_packet_version,
            seen_case_ids=seen_case_ids,
        )
        records.append(record)
        seen_case_ids.add(record["case_id"])
    return records


def append_signoff_record(
    ledger_path: str | Path,
    record: Mapping[str, Any],
    *,
    pending_case_ids: Iterable[str],
    candidate_dataset_version: str,
    review_packet_version: str,
) -> dict[str, Any]:
    """校验后向台账末尾追加一条人工签核记录，不覆盖历史内容。"""

    path = Path(ledger_path)
    case_ids = _as_case_id_set(pending_case_ids)
    existing = load_signoff_ledger(
        path,
        pending_case_ids=case_ids,
        candidate_dataset_version=candidate_dataset_version,
        review_packet_version=review_packet_version,
    )
    validated = _validate_record(
        record,
        pending_case_ids=case_ids,
        candidate_dataset_version=candidate_dataset_version,
        review_packet_version=review_packet_version,
        seen_case_ids={item["case_id"] for item in existing},
    )
    with path.open("a", encoding="utf-8", newline="") as stream:
        stream.write(json.dumps(validated, ensure_ascii=False, separators=(",", ":")))
        stream.write("\n")
    return validated


__all__ = [
    "REQUIRED_REVIEW_CHECKS",
    "SignoffLedgerError",
    "append_signoff_record",
    "load_signoff_ledger",
]
