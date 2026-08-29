"""B 阶段单指标事实链路的离线评测。"""

from src.evaluation import EvaluationCase, EvaluationRunner
from src.financial_fact_registry_adapter import FinancialFactRegistryAdapter
from src.financial_fact_repository import FinancialFactRepository
from src.v7_metadata_store import V7MetadataStore
from src.verified_financial_facts import VerifiedFinancialFactRegistry


def test_registered_revenue_can_pass_existing_evaluation_gate_with_source_pages(tmp_path):
    """旧营业收入事实经新存储读取后，仍能满足既有答案级评测约束。"""
    legacy = VerifiedFinancialFactRegistry()
    adapter = FinancialFactRegistryAdapter(
        legacy_registry=legacy,
        repository=FinancialFactRepository(V7MetadataStore(tmp_path / "metadata.sqlite3")),
    )
    adapter.import_registered_revenue_facts()
    comparison = adapter.get_comparison(
        "operating_revenue", 2024, ["中国移动", "中国联通", "中国电信"]
    )
    mobile = comparison["items"][0]
    case = EvaluationCase.from_dict(
        {
            "id": "b-revenue-mobile-2024",
            "category": "numeric",
            "query": "中国移动 2024 年营业收入是多少？",
            "companies": ["中国移动"],
            "expected_answer": "中国移动 2024 年营业收入为 10,408 亿元。",
            "expected_facts": [{
                "metric_key": "operating_revenue",
                "value": 10408,
                "unit": "亿元",
                "currency": "CNY",
                "period": "2024",
            }],
            "expected_sources": [{"source_file": "移动2024年度报告.pdf", "pages": [3]}],
            "expected_pages": [3],
            "numeric_tolerance": 0,
            "expected_behavior": "answer",
            "expected_tools": ["registry", "financial_fact_repository"],
            "risk_level": "high",
            "review_status": "verified",
            "dataset_version": "v7-b0",
        }
    )
    fixture = {
        "answer": legacy.build_comparison_answer(comparison),
        "facts": [{
            "metric_key": mobile["metric_key"],
            "value": mobile["value"],
            "unit": mobile["unit"],
            "currency": "CNY",
            "period": str(mobile["fiscal_year"]),
        }],
        "sources": [{"source_file": mobile["source_file"], "pages": mobile["pages"]}],
        "tools": ["registry", "financial_fact_repository"],
    }

    report = EvaluationRunner(mode="offline-core").run([case], {case.case_id: fixture})

    assert report.passed is True
    assert EvaluationRunner.passes_quality_gate(report) is True
