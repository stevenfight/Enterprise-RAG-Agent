"""A1.7.2 A-GATE-2 追加式人工签核台账契约。"""

import json
from pathlib import Path

import pytest

from src.evaluation.manual_signoff import (
    SignoffLedgerError,
    append_signoff_record,
    load_signoff_ledger,
)


DATASET_VERSION = "v7-full-candidate-20260904"
PACKET_VERSION = "v7-full-review-packet-20260904"
CASE_IDS = {"gen-001", "gen-002"}
CHECK_NAMES = {
    "document",
    "page",
    "period_and_source_caliber",
    "excerpt",
    "answer",
    "tolerance",
    "tools",
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FULL_REVIEW_PACKET = PROJECT_ROOT / "evals" / "datasets" / "full-v7-candidate.review.jsonl"
FULL_REVIEW_METADATA = PROJECT_ROOT / "evals" / "datasets" / "full-v7-candidate.review.metadata.json"


def _record(case_id: str = "gen-001", decision: str = "approved") -> dict:
    return {
        "case_id": case_id,
        "decision": decision,
        "reviewer": "用户审核",
        "reviewed_at": "2026-09-04T21:00:00+08:00",
        "candidate_dataset_version": DATASET_VERSION,
        "review_packet_version": PACKET_VERSION,
        "checks": {name: True for name in CHECK_NAMES},
        "comment": "用户逐条核对后的记录。",
    }


def test_append_and_load_signoff_record_is_append_only(tmp_path: Path):
    ledger_path = tmp_path / "manual-signoff.jsonl"

    appended = append_signoff_record(
        ledger_path,
        _record(),
        pending_case_ids=CASE_IDS,
        candidate_dataset_version=DATASET_VERSION,
        review_packet_version=PACKET_VERSION,
    )
    records = load_signoff_ledger(
        ledger_path,
        pending_case_ids=CASE_IDS,
        candidate_dataset_version=DATASET_VERSION,
        review_packet_version=PACKET_VERSION,
    )

    assert appended["case_id"] == "gen-001"
    assert len(records) == 1
    assert records[0]["decision"] == "approved"
    assert len(ledger_path.read_text(encoding="utf-8").splitlines()) == 1


def test_duplicate_case_id_is_rejected_without_overwriting_history(tmp_path: Path):
    ledger_path = tmp_path / "manual-signoff.jsonl"
    kwargs = {
        "pending_case_ids": CASE_IDS,
        "candidate_dataset_version": DATASET_VERSION,
        "review_packet_version": PACKET_VERSION,
    }

    append_signoff_record(ledger_path, _record(), **kwargs)
    with pytest.raises(SignoffLedgerError, match="重复"):
        append_signoff_record(ledger_path, _record(), **kwargs)

    assert len(ledger_path.read_text(encoding="utf-8").splitlines()) == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("case_id", "unknown", "未知"),
        ("decision", "pending", "decision"),
        ("candidate_dataset_version", "other-dataset", "版本"),
    ],
)
def test_invalid_signoff_record_is_rejected(tmp_path: Path, field: str, value: str, message: str):
    record = _record()
    record[field] = value

    with pytest.raises(SignoffLedgerError, match=message):
        append_signoff_record(
            tmp_path / "manual-signoff.jsonl",
            record,
            pending_case_ids=CASE_IDS,
            candidate_dataset_version=DATASET_VERSION,
            review_packet_version=PACKET_VERSION,
        )


def test_missing_review_check_and_duplicate_lines_are_rejected(tmp_path: Path):
    missing_check = _record()
    del missing_check["checks"]["excerpt"]
    with pytest.raises(SignoffLedgerError, match="核对项"):
        append_signoff_record(
            tmp_path / "missing.jsonl",
            missing_check,
            pending_case_ids=CASE_IDS,
            candidate_dataset_version=DATASET_VERSION,
            review_packet_version=PACKET_VERSION,
        )

    ledger_path = tmp_path / "tampered.jsonl"
    raw = json.dumps(_record(), ensure_ascii=False)
    ledger_path.write_text(f"{raw}\n{raw}\n", encoding="utf-8")
    with pytest.raises(SignoffLedgerError, match="重复"):
        load_signoff_ledger(
            ledger_path,
            pending_case_ids=CASE_IDS,
            candidate_dataset_version=DATASET_VERSION,
            review_packet_version=PACKET_VERSION,
        )


def test_rejected_decision_is_valid_when_all_review_fields_are_present(tmp_path: Path):
    record = _record(decision="rejected")
    record["checks"]["answer"] = False

    appended = append_signoff_record(
        tmp_path / "manual-signoff.jsonl",
        record,
        pending_case_ids=CASE_IDS,
        candidate_dataset_version=DATASET_VERSION,
        review_packet_version=PACKET_VERSION,
    )

    assert appended["decision"] == "rejected"
    assert appended["checks"]["answer"] is False


def test_real_full_review_packet_binds_to_signoff_contract(tmp_path: Path):
    packet_rows = [
        json.loads(line)
        for line in FULL_REVIEW_PACKET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    metadata = json.loads(FULL_REVIEW_METADATA.read_text(encoding="utf-8"))
    packet_case_ids = {row["case_id"] for row in packet_rows}
    record = _record()
    record["candidate_dataset_version"] = metadata["dataset_version"]
    record["review_packet_version"] = metadata["packet_version"]

    appended = append_signoff_record(
        tmp_path / "manual-signoff.jsonl",
        record,
        pending_case_ids=packet_case_ids,
        candidate_dataset_version=metadata["dataset_version"],
        review_packet_version=metadata["packet_version"],
    )

    assert len(packet_case_ids) == metadata["case_count"] == 70
    assert appended["case_id"] in packet_case_ids
