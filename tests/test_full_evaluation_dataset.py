"""A1.7 完整评测候选集的数量、分类和来源可定位性契约。"""

import json
from pathlib import Path

from src.evaluation import CoverageRequirements, build_coverage_report, load_jsonl_cases
from src.evaluation.manual_signoff import load_signoff_ledger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FULL_DATASET = PROJECT_ROOT / "evals" / "datasets" / "full-v7-candidate.jsonl"
FULL_METADATA = PROJECT_ROOT / "evals" / "datasets" / "full-v7-candidate.metadata.json"
FULL_REVIEW_PACKET = PROJECT_ROOT / "evals" / "datasets" / "full-v7-candidate.review.jsonl"
FULL_REVIEW_METADATA = PROJECT_ROOT / "evals" / "datasets" / "full-v7-candidate.review.metadata.json"
FULL_SIGNOFF_LEDGER = PROJECT_ROOT / "evals" / "datasets" / "full-v7-candidate.manual-signoff.jsonl"
SOURCE_INVENTORY = PROJECT_ROOT / "data" / "stock_data" / "pdf_source_inventory.json"


def test_full_candidate_has_at_least_100_cases_and_records_category_coverage():
    cases = load_jsonl_cases(FULL_DATASET)
    metadata = json.loads(FULL_METADATA.read_text(encoding="utf-8"))
    report = build_coverage_report(cases, CoverageRequirements())

    assert len(cases) >= 100
    assert len({case.case_id for case in cases}) == len(cases)
    assert {
        "numeric", "unit", "period", "refusal", "conflict", "tool_trace",
    }.issubset(report["categories"])
    assert len(report["companies"]) >= 4
    assert len(report["periods"]) >= 2
    assert all(case.review_status in {"draft", "verified"} for case in cases)
    assert all(case.review_status == "verified" for case in cases)

    assert metadata["dataset_version"] == "v7-full-candidate-20260904"
    assert metadata["case_count"] == len(cases)
    assert metadata["status"] == "draft"
    assert metadata["source_evidence_status"] == "pending_review"
    assert metadata["review_packet_status"] == "pending_manual_review"
    assert metadata["review_progress"] == {
        "total_manual_review_scope": 70,
        "approved": 70,
        "pending": 0,
        "rejected": 0,
    }
    assert metadata["coverage"]["category_counts"] == {
        category: sum(case.category == category for case in cases)
        for category in sorted({case.category for case in cases})
    }
    assert metadata["coverage"]["categories"] == report["categories"]


def test_full_candidate_sources_are_registered_and_pages_are_in_pdf_range():
    cases = load_jsonl_cases(FULL_DATASET)
    inventory = json.loads(SOURCE_INVENTORY.read_text(encoding="utf-8"))
    page_counts = {
        document["relative_source_path"]: document["physical_page_count"]
        for document in inventory["documents"]
    }

    for case in cases:
        for source in case.expected_sources:
            assert source.source_file in page_counts
            assert all(page <= page_counts[source.source_file] for page in source.pages)
        if case.expected_sources:
            source_pages = {
                page for source in case.expected_sources for page in source.pages
            }
            assert set(case.expected_pages).issubset(source_pages)


def test_full_candidate_keeps_manual_review_boundary_explicit():
    metadata = json.loads(FULL_METADATA.read_text(encoding="utf-8"))

    assert metadata["review_required"] is True
    assert metadata["release_ready"] is False
    assert metadata["composition"]["core_verified"] == 30
    assert metadata["composition"]["legacy_migrated_verified"] == 20
    assert metadata["composition"]["legacy_migrated_draft"] == 0
    assert metadata["composition"]["new_candidate_verified"] == 50
    assert metadata["composition"]["new_candidate_draft"] == 0


def test_full_candidate_review_scope_has_complete_packet_and_statuses():
    cases = [
        json.loads(line)
        for line in FULL_DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    review_scope = {
        case["id"]: case for case in cases if not case["id"].startswith("core-")
    }
    packet_rows = [
        json.loads(line)
        for line in FULL_REVIEW_PACKET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    packet = {row["case_id"]: row for row in packet_rows}
    packet_metadata = json.loads(FULL_REVIEW_METADATA.read_text(encoding="utf-8"))

    assert len(review_scope) == 70
    assert len(packet_rows) == len(packet) == len(review_scope)
    assert set(packet) == set(review_scope)
    assert packet_metadata["dataset_version"] == "v7-full-candidate-20260904"
    assert packet_metadata["case_count"] == len(packet_rows)
    assert packet_metadata["status"] == "pending_review"
    assert packet_metadata["review_required"] is True
    assert packet_metadata["release_ready"] is False

    assert packet_metadata["review_progress"] == {
        "review_scope": 70,
        "approved": 70,
        "pending": 0,
        "rejected": 0,
    }
    assert packet_metadata["approved_case_ids"] == ["gen-001", "gen-002", "gen-003", "gen-004", "gen-005", "gen-006", "gen-007", "gen-008", "gen-009", "gen-010", "ret-001", "ret-002", "ret-003", "ret-004", "ret-005", "ret-006", "ret-007", "ret-008", "ret-009", "ret-010", "full-v7-001", "full-v7-002", "full-v7-003", "full-v7-004", "full-v7-005", "full-v7-006", "full-v7-007", "full-v7-008", "full-v7-009", "full-v7-010", "full-v7-011", "full-v7-012", "full-v7-013", "full-v7-014", "full-v7-015", "full-v7-016", "full-v7-017", "full-v7-018", "full-v7-019", "full-v7-020", "full-v7-021", "full-v7-022", "full-v7-023", "full-v7-024", "full-v7-025", "full-v7-026", "full-v7-027", "full-v7-028", "full-v7-029", "full-v7-030", "full-v7-031", "full-v7-032", "full-v7-033", "full-v7-034", "full-v7-035", "full-v7-036", "full-v7-037", "full-v7-038", "full-v7-039", "full-v7-040", "full-v7-041", "full-v7-042", "full-v7-043", "full-v7-044", "full-v7-045", "full-v7-046", "full-v7-047", "full-v7-048", "full-v7-049", "full-v7-050"]

    required_checks = {
        "document",
        "page",
        "period_and_source_caliber",
        "excerpt",
        "answer",
        "tolerance",
        "tools",
    }
    for case_id, case in review_scope.items():
        row = packet[case_id]
        assert row["query"] == case["query"]
        assert row["candidate_answer"] == case["expected_answer"]
        assert row["expected_facts"] == case["expected_facts"]
        assert row["expected_sources"] == case["expected_sources"]
        assert row["expected_pages"] == case["expected_pages"]
        assert row["numeric_tolerance"] == case["numeric_tolerance"]
        assert set(row["review_checks"]) == required_checks
        assert len(row["evidence"]) >= 1
        if case["review_status"] == "draft":
            assert row["review_status"] == "pending_review"
            assert row["final_status"] == "pending"
            assert all(value == "pending" for value in row["review_checks"].values())
            assert all(
                evidence["excerpt"] is None
                and evidence["excerpt_status"] == "pending_manual_review"
                for evidence in row["evidence"]
            )
        else:
            assert case["id"] in {"gen-001", "gen-002", "gen-003", "gen-004", "gen-005", "gen-006", "gen-007", "gen-008", "gen-009", "gen-010", "ret-001", "ret-002", "ret-003", "ret-004", "ret-005", "ret-006", "ret-007", "ret-008", "ret-009", "ret-010", "full-v7-001", "full-v7-002", "full-v7-003", "full-v7-004", "full-v7-005", "full-v7-006", "full-v7-007", "full-v7-008", "full-v7-009", "full-v7-010", "full-v7-011", "full-v7-012", "full-v7-013", "full-v7-014", "full-v7-015", "full-v7-016", "full-v7-017", "full-v7-018", "full-v7-019", "full-v7-020", "full-v7-021", "full-v7-022", "full-v7-023", "full-v7-024", "full-v7-025", "full-v7-026", "full-v7-027", "full-v7-028", "full-v7-029", "full-v7-030", "full-v7-031", "full-v7-032", "full-v7-033", "full-v7-034", "full-v7-035", "full-v7-036", "full-v7-037", "full-v7-038", "full-v7-039", "full-v7-040", "full-v7-041", "full-v7-042", "full-v7-043", "full-v7-044", "full-v7-045", "full-v7-046", "full-v7-047", "full-v7-048", "full-v7-049", "full-v7-050"}
            assert row["review_status"] == "verified"
            assert row["final_status"] == "approved"
            expected_answer_check = {
                "gen-001": "candidate_matches_sources",
                "gen-002": "approved",
                "gen-003": "approved",
                "gen-004": "approved",
                "gen-005": "approved",
                "gen-006": "approved",
                "gen-007": "approved",
                "gen-008": "approved",
                "gen-009": "approved",
                "gen-010": "approved",
                "ret-001": "approved",
                "ret-002": "approved",
                "ret-003": "approved",
                "ret-004": "approved",
                "ret-005": "approved",
                "ret-006": "approved",
                "ret-007": "approved",
                "ret-008": "approved",
                "ret-009": "approved",
                "ret-010": "approved",
                "full-v7-001": "approved",
                "full-v7-002": "approved",
                "full-v7-003": "approved",
                "full-v7-004": "approved",
                "full-v7-005": "approved",
                "full-v7-006": "approved",
                "full-v7-007": "approved",
                "full-v7-008": "approved",
                "full-v7-009": "approved",
                "full-v7-010": "approved",
                "full-v7-011": "approved",
                "full-v7-012": "approved",
                "full-v7-013": "approved",
                "full-v7-014": "approved",
                "full-v7-015": "approved",
                "full-v7-016": "approved",
                "full-v7-017": "approved",
                "full-v7-018": "approved",
                "full-v7-019": "approved",
                "full-v7-020": "approved",
                "full-v7-021": "approved",
                "full-v7-022": "approved",
                "full-v7-023": "approved",
                "full-v7-024": "approved",
                "full-v7-025": "approved",
                "full-v7-026": "approved",
                "full-v7-027": "approved",
                "full-v7-028": "approved",
                "full-v7-029": "approved",
                "full-v7-030": "approved",
                "full-v7-031": "approved",
                "full-v7-032": "approved",
                "full-v7-033": "approved",
                "full-v7-034": "approved",
                "full-v7-035": "approved",
                "full-v7-036": "approved",
                "full-v7-037": "approved",
                "full-v7-038": "approved",
                "full-v7-039": "approved",
                "full-v7-040": "approved",
                "full-v7-041": "candidate_matches_excerpt",
                "full-v7-042": "candidate_matches_excerpt",
                "full-v7-043": "candidate_matches_excerpt",
                "full-v7-044": "candidate_matches_excerpt",
                "full-v7-045": "candidate_matches_excerpt",
                "full-v7-046": "candidate_matches_excerpt",
                "full-v7-047": "candidate_matches_excerpt",
                "full-v7-048": "candidate_matches_excerpt",
                "full-v7-049": "candidate_matches_excerpt",
                "full-v7-050": "candidate_matches_excerpt",
            }[case["id"]]
            assert row["review_checks"]["answer"] == expected_answer_check
            assert all(
                evidence["excerpt"]
                and evidence["excerpt_status"] == "verified"
                for evidence in row["evidence"]
            )


def test_full_candidate_manual_signoff_ledger_matches_approved_review_rows():
    packet_rows = [
        json.loads(line)
        for line in FULL_REVIEW_PACKET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    packet_case_ids = {row["case_id"] for row in packet_rows}
    records = load_signoff_ledger(
        FULL_SIGNOFF_LEDGER,
        pending_case_ids=packet_case_ids,
        candidate_dataset_version="v7-full-candidate-20260904",
        review_packet_version="v7-full-review-packet-20260904",
    )

    assert len(records) == 70
    assert [record["case_id"] for record in records] == ["gen-001", "gen-002", "gen-003", "gen-004", "gen-005", "gen-006", "gen-007", "gen-008", "gen-009", "gen-010", "ret-001", "ret-002", "ret-003", "ret-004", "ret-005", "ret-006", "ret-007", "ret-008", "ret-009", "ret-010", "full-v7-001", "full-v7-002", "full-v7-003", "full-v7-004", "full-v7-005", "full-v7-006", "full-v7-007", "full-v7-008", "full-v7-009", "full-v7-010", "full-v7-011", "full-v7-012", "full-v7-013", "full-v7-014", "full-v7-015", "full-v7-016", "full-v7-017", "full-v7-018", "full-v7-019", "full-v7-020", "full-v7-021", "full-v7-022", "full-v7-023", "full-v7-024", "full-v7-025", "full-v7-026", "full-v7-027", "full-v7-028", "full-v7-029", "full-v7-030", "full-v7-031", "full-v7-032", "full-v7-033", "full-v7-034", "full-v7-035", "full-v7-036", "full-v7-037", "full-v7-038", "full-v7-039", "full-v7-040", "full-v7-041", "full-v7-042", "full-v7-043", "full-v7-044", "full-v7-045", "full-v7-046", "full-v7-047", "full-v7-048", "full-v7-049", "full-v7-050"]
    assert all(record["decision"] == "approved" for record in records)
    assert all(all(record["checks"].values()) for record in records)


def test_full_review_packet_source_locators_match_inventory_and_candidate_pages():
    cases = {
        case["id"]: case
        for case in (
            json.loads(line)
            for line in FULL_DATASET.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if not case["id"].startswith("core-")
    }
    packet_rows = [
        json.loads(line)
        for line in FULL_REVIEW_PACKET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    inventory = json.loads(SOURCE_INVENTORY.read_text(encoding="utf-8"))
    page_counts = {
        document["relative_source_path"]: document["physical_page_count"]
        for document in inventory["documents"]
    }

    for row in packet_rows:
        case = cases[row["case_id"]]
        assert row["expected_pages"] == case["expected_pages"]
        for evidence in row["evidence"]:
            assert evidence["source_file"] in page_counts
            assert evidence["physical_page"] in case["expected_pages"]
            assert evidence["physical_page"] <= page_counts[evidence["source_file"]]
