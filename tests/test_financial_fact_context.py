"""B1.1 财务事实期间、口径、来源与修订版本实体测试。"""

from datetime import date

import pytest


def test_fact_context_entities_preserve_period_scope_source_and_revision():
    from src.financial_fact_context import (
        FinancialFactRevision,
        FinancialFactSource,
        FinancialPeriod,
        FinancialScope,
    )

    period = FinancialPeriod.create(
        period_id="period-fy2024", period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31), fiscal_year=2024, period_type="annual",
    )
    scope = FinancialScope.create(
        scope_id="scope-consolidated-cas", consolidation="consolidated",
        accounting_standard="CAS", audited=True,
    )
    source = FinancialFactSource.create(
        source_id="source-mobile-2024-p3", logical_document_id="doc-mobile-2024",
        document_version_id="docver-mobile-2024-a", source_file="移动2024年度报告.pdf",
        physical_pages=(3,), excerpt="营业收入达到人民币 10,408 亿元。",
        source_type="annual_report", authority_level="primary",
    )
    revision = FinancialFactRevision.create(
        fact_version_id="factver-mobile-revenue-v2",
        fact_id="operating-revenue-2024-中国移动",
        supersedes_fact_version_id="factver-mobile-revenue-v1",
    )

    assert period.period_type == "annual"
    assert scope.audited is True
    assert source.document_version_id == "docver-mobile-2024-a"
    assert source.physical_pages == (3,)
    assert revision.supersedes_fact_version_id == "factver-mobile-revenue-v1"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "period_id": "period-fy2024", "period_start": date(2024, 1, 1),
                "period_end": date(2024, 4, 10), "fiscal_year": 2024,
                "period_type": "annual",
            },
            "annual",
        ),
        (
            {
                "period_id": "period-q1-2024", "period_start": date(2024, 4, 1),
                "period_end": date(2024, 3, 31), "fiscal_year": 2024,
                "period_type": "quarter",
            },
            "起止日期",
        ),
    ],
)
def test_period_rejects_invalid_annual_or_date_range(kwargs, message):
    from src.financial_fact_context import FinancialPeriod

    with pytest.raises(ValueError, match=message):
        FinancialPeriod.create(**kwargs)


def test_source_rejects_missing_document_version_or_invalid_physical_pages():
    from src.financial_fact_context import FinancialFactSource

    with pytest.raises(ValueError, match="document_version_id"):
        FinancialFactSource.create(
            source_id="source-1", logical_document_id="doc-1", document_version_id="",
            source_file="报告.pdf", physical_pages=(1,), excerpt="摘录",
            source_type="annual_report", authority_level="primary",
        )
    with pytest.raises(ValueError, match="physical_pages"):
        FinancialFactSource.create(
            source_id="source-1", logical_document_id="doc-1", document_version_id="version-1",
            source_file="报告.pdf", physical_pages=(1, 1), excerpt="摘录",
            source_type="annual_report", authority_level="primary",
        )


def test_non_calendar_fiscal_year_remains_a_valid_annual_period():
    from src.financial_fact_context import FinancialPeriod

    period = FinancialPeriod.create(
        period_id="period-fy2024-mar", period_start=date(2023, 4, 1),
        period_end=date(2024, 3, 31), fiscal_year=2024, period_type="annual",
    )

    assert period.fiscal_year == 2024


def test_scope_and_revision_reject_invalid_values():
    from src.financial_fact_context import FinancialFactRevision, FinancialScope

    with pytest.raises(ValueError, match="consolidation"):
        FinancialScope.create(
            scope_id="scope-1", consolidation="unknown", accounting_standard="CAS", audited=True
        )
    with pytest.raises(ValueError, match="supersedes"):
        FinancialFactRevision.create(
            fact_version_id="factver-1", fact_id="fact-1", supersedes_fact_version_id="factver-1"
        )


def test_context_comparison_rejects_annual_vs_quarter_and_consolidated_vs_parent():
    from src.financial_fact_context import FinancialPeriod, FinancialScope
    from src.financial_fact_context_compatibility import IncompatibleFactContextError, ensure_context_comparable

    annual = FinancialPeriod.create(
        period_id="fy2024", period_start=date(2024, 1, 1), period_end=date(2024, 12, 31),
        fiscal_year=2024, period_type="annual",
    )
    quarter = FinancialPeriod.create(
        period_id="q4-2024", period_start=date(2024, 10, 1), period_end=date(2024, 12, 31),
        fiscal_year=2024, period_type="quarter",
    )
    consolidated = FinancialScope.create(
        scope_id="consolidated", consolidation="consolidated", accounting_standard="CAS", audited=True
    )
    parent = FinancialScope.create(
        scope_id="parent", consolidation="parent_company", accounting_standard="CAS", audited=True
    )

    with pytest.raises(IncompatibleFactContextError, match="期间"):
        ensure_context_comparable(annual, quarter, consolidated, consolidated)
    with pytest.raises(IncompatibleFactContextError, match="口径"):
        ensure_context_comparable(annual, annual, consolidated, parent)
