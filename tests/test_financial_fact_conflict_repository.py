"""B2.4 未决事实冲突人工确认仓储测试。"""

import pytest


def test_pending_conflict_is_persisted_for_manual_review(tmp_path):
    from src.financial_fact_conflict_repository import FinancialFactConflictRepository
    from src.financial_fact_conflict_service import FinancialFactConflictDecision
    from src.v7_metadata_store import V7MetadataStore

    repository = FinancialFactConflictRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    decision = FinancialFactConflictDecision(
        status="pending_review", conflict_type="VALUE_CONFLICT", fact_ids=("fact-a", "fact-b"),
        relative_difference="0.06", preferred_fact_id="fact-a",
    )
    repository.save("conflict-1", decision)

    stored = repository.get("conflict-1")
    assert stored.status == "pending_review"
    assert stored.preferred_fact_id == "fact-a"


def test_conflict_repository_rejects_conflicting_replay(tmp_path):
    from src.financial_fact_conflict_repository import FinancialFactConflictConflictError, FinancialFactConflictRepository
    from src.financial_fact_conflict_service import FinancialFactConflictDecision
    from src.v7_metadata_store import V7MetadataStore

    repository = FinancialFactConflictRepository(V7MetadataStore(tmp_path / "metadata.sqlite3"))
    decision = FinancialFactConflictDecision("pending_review", "VALUE_CONFLICT", ("a", "b"), "0.06")
    repository.save("conflict-1", decision)
    repository.save("conflict-1", decision)
    with pytest.raises(FinancialFactConflictConflictError):
        repository.save("conflict-1", FinancialFactConflictDecision("pending_review", "VALUE_CONFLICT", ("a", "b"), "0.07"))
