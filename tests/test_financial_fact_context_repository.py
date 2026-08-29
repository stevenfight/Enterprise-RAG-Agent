"""B1.6 事实上下文 SQLite 外键仓储测试。"""

from datetime import date

import pytest


def test_context_repository_persists_source_against_real_document_version(tmp_path):
    from src.financial_fact_context import FinancialFactSource, FinancialPeriod, FinancialScope
    from src.financial_fact_context_repository import FinancialFactContextRepository
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    document = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="mobile-2024", display_name="移动 2024", original_filename="移动2024年度报告.pdf",
        file_content=b"fixture-pdf", physical_page_count=3,
    )
    repository = FinancialFactContextRepository(store)
    repository.save_period(FinancialPeriod.create(
        period_id="fy2024", period_start=date(2024, 1, 1), period_end=date(2024, 12, 31),
        fiscal_year=2024, period_type="annual",
    ))
    repository.save_scope(FinancialScope.create(
        scope_id="consolidated-cas", consolidation="consolidated", accounting_standard="CAS", audited=True,
    ))
    repository.save_source(FinancialFactSource.create(
        source_id="mobile-p3", logical_document_id=document.logical_document_id,
        document_version_id=document.document_version_id, source_file="移动2024年度报告.pdf",
        physical_pages=(3,), excerpt="营业收入", source_type="annual_report", authority_level="primary",
    ))

    assert repository.get_source("mobile-p3").document_version_id == document.document_version_id


def test_context_repository_is_idempotent_and_rejects_conflicting_source_evidence(tmp_path):
    from src.financial_fact_context import FinancialFactSource
    from src.financial_fact_context_repository import FinancialFactContextConflictError, FinancialFactContextRepository
    from src.v7_document_repository import V7DocumentRepository
    from src.v7_metadata_store import V7MetadataStore

    store = V7MetadataStore(tmp_path / "metadata.sqlite3")
    document = V7DocumentRepository(store, tmp_path / "blobs").register_document_version(
        logical_document_key="mobile-2024", display_name="移动 2024", original_filename="移动2024年度报告.pdf",
        file_content=b"fixture-pdf", physical_page_count=3,
    )
    repository = FinancialFactContextRepository(store)
    source = FinancialFactSource.create(
        source_id="mobile-p3", logical_document_id=document.logical_document_id,
        document_version_id=document.document_version_id, source_file="移动2024年度报告.pdf",
        physical_pages=(3,), excerpt="营业收入", source_type="annual_report", authority_level="primary",
    )

    repository.save_source(source)
    repository.save_source(source)
    with pytest.raises(FinancialFactContextConflictError):
        repository.save_source(FinancialFactSource.create(
            source_id="mobile-p3", logical_document_id=document.logical_document_id,
            document_version_id=document.document_version_id, source_file="移动2024年度报告.pdf",
            physical_pages=(2,), excerpt="营业收入", source_type="annual_report", authority_level="primary",
        ))
