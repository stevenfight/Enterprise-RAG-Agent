"""同口径事实冲突必须显式进入人工确认状态。"""


def _fact(fact_id: str, normalized_value: str):
    from src.financial_fact import FinancialFact

    return FinancialFact.create(
        fact_id=fact_id,
        metric_key="operating_revenue",
        company_name="中国移动",
        raw_value=normalized_value,
        raw_unit="元",
        normalized_value=normalized_value,
        normalized_unit="元",
        currency="CNY",
        period="FY2024",
        scope="consolidated",
        source_file=f"{fact_id}.pdf",
        physical_pages=(1,),
        excerpt="来源",
    )


def test_conflict_service_accepts_values_within_relative_tolerance():
    from src.financial_fact_conflict_service import FinancialFactConflictService

    decision = FinancialFactConflictService(relative_tolerance=0.05).compare(
        _fact("fact-a", "100"),
        _fact("fact-b", "104"),
    )

    assert decision.status == "consistent"
    assert decision.relative_difference == "0.04"


def test_conflict_service_sends_excess_difference_to_pending_review():
    from src.financial_fact_conflict_service import FinancialFactConflictService

    decision = FinancialFactConflictService(relative_tolerance=0.05).compare(
        _fact("fact-a", "100"),
        _fact("fact-b", "106"),
    )

    assert decision.status == "pending_review"
    assert decision.conflict_type == "VALUE_CONFLICT"
    assert decision.fact_ids == ("fact-a", "fact-b")


def test_conflict_service_records_primary_source_priority_without_auto_resolving():
    from src.financial_fact_context import FinancialFactSource
    from src.financial_fact_conflict_service import FinancialFactConflictService

    primary = FinancialFactSource.create(
        source_id="primary", logical_document_id="doc-a", document_version_id="version-a",
        source_file="a.pdf", physical_pages=(1,), excerpt="来源", source_type="annual_report", authority_level="primary",
    )
    secondary = FinancialFactSource.create(
        source_id="secondary", logical_document_id="doc-b", document_version_id="version-b",
        source_file="b.pdf", physical_pages=(1,), excerpt="来源", source_type="secondary", authority_level="secondary",
    )

    decision = FinancialFactConflictService().compare(
        _fact("fact-a", "100"), _fact("fact-b", "106"),
        reference_source=primary, candidate_source=secondary,
    )

    assert decision.status == "pending_review"
    assert decision.preferred_fact_id == "fact-a"


def test_explainable_unit_conversion_does_not_create_value_conflict():
    from src.financial_fact import FinancialFact
    from src.financial_fact_conflict_service import FinancialFactConflictService

    reference = FinancialFact.create(
        fact_id="fact-yuan", metric_key="operating_revenue", company_name="中国移动",
        raw_value="100", raw_unit="亿元", normalized_value="10000000000", normalized_unit="元",
        currency="CNY", period="FY2024", scope="consolidated", source_file="a.pdf",
        physical_pages=(1,), excerpt="营业收入 100 亿元",
    )
    candidate = FinancialFact.create(
        fact_id="fact-million", metric_key="operating_revenue", company_name="中国移动",
        raw_value="10000", raw_unit="百万元", normalized_value="10000000000", normalized_unit="元",
        currency="CNY", period="FY2024", scope="consolidated", source_file="b.pdf",
        physical_pages=(1,), excerpt="营业收入 10000 百万元",
    )

    decision = FinancialFactConflictService().compare(reference, candidate)

    assert decision.status == "consistent"
    assert decision.conflict_type is None
    assert decision.relative_difference == "0"
