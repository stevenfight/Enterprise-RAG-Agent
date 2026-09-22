"""M4.4 多模态验收准入报告的 fail-closed 测试。"""

from datetime import date


def _case(index: int, split: str):
    from src.evaluation import EvaluationCase

    return EvaluationCase.from_dict({
        "id": f"m4-region-{index:02d}",
        "category": "multimodal_region",
        "query": "该区域的结论是什么？",
        "companies": [f"公司-{split}-{index}"],
        "expected_answer": "已核验的区域结论。",
        "expected_facts": [],
        "expected_sources": [{"source_file": f"文档-{index}.pdf", "pages": [1]}],
        "expected_pages": [1],
        "numeric_tolerance": 0.01,
        "expected_behavior": "answer",
        "expected_tools": ["retrieve"],
        "risk_level": "high",
        "review_status": "verified",
        "dataset_version": "v7-m4-fixture",
        "source_document_id": f"document-{split}-{index}",
        "region_id": f"region-{index}",
        "region_type": "table",
        "modality": "table",
        "dataset_split": split,
        "source_sha256": f"{index:064x}",
        "physical_page_number": 1,
    })


def _verified_cases():
    return [_case(index, "development" if index < 30 else "holdout") for index in range(40)]


def _complete_ledger(cases):
    holdout_ids = [case.case_id for case in cases if case.dataset_split == "holdout"]
    return {
        "holdout": {"frozen": True, "case_ids": holdout_ids, "result_id": "run-20260830-01"},
        "high_risk_verified_errors": 0,
        "vision_metrics": {
            "total_pages": 100,
            "vision_routed_pages": 25,
            "cache_hits": 10,
            "vision_calls": 25,
            "vision_failures": 1,
            "document_p95_ms": 800,
        },
        "cost_gate": {
            "baseline": "M4 baseline 2026-08-30",
            "target": "批准后目标",
            "quality_floor": "高风险视觉误入库为 0",
            "price_version": "provider-price-2026-08",
            "price_effective_date": date.today().isoformat(),
            "approval_id": "cost-approval-001",
        },
    }


def test_readiness_report_blocks_missing_real_evidence():
    from src.evaluation.multimodal_readiness import build_m4_readiness_report

    report = build_m4_readiness_report([], {}, candidate_inventory={"candidate_count": 385, "status": "pending_review"})

    assert report["ready"] is False
    assert "缺少冻结留出集运行结果" in report["blockers"]
    assert report["candidate_inventory"]["candidate_count"] == 385
    assert "pending_review" in report["candidate_inventory"]["status"]


def test_readiness_report_accepts_complete_verified_holdout_and_run_ledger():
    from src.evaluation.multimodal_readiness import build_m4_readiness_report

    cases = _verified_cases()
    report = build_m4_readiness_report(cases, _complete_ledger(cases))

    assert report["ready"] is True
    assert report["holdout"]["case_count"] == 10
    assert report["vision_metrics"]["vision_routing_ratio"] == 0.25
    assert report["vision_metrics"]["cache_hit_ratio"] == 0.4
    assert report["vision_metrics"]["failure_rate"] == 0.04


def test_readiness_report_blocks_any_high_risk_verified_error():
    from src.evaluation.multimodal_readiness import build_m4_readiness_report

    cases = _verified_cases()
    ledger = _complete_ledger(cases)
    ledger["high_risk_verified_errors"] = 1

    report = build_m4_readiness_report(cases, ledger)

    assert report["ready"] is False
    assert "高风险视觉数字误入 verified: 1" in report["blockers"]


def test_readiness_report_blocks_incomplete_cost_gate_and_exposes_markdown():
    from src.evaluation.multimodal_readiness import build_m4_readiness_report, m4_readiness_to_markdown

    cases = _verified_cases()
    ledger = _complete_ledger(cases)
    del ledger["cost_gate"]["approval_id"]

    report = build_m4_readiness_report(cases, ledger)
    markdown = m4_readiness_to_markdown(report)

    assert report["ready"] is False
    assert "成本门禁缺少字段: approval_id" in report["blockers"]
    assert "# M4.4 多模态验收准入报告" in markdown
    assert "No-Go" in markdown
