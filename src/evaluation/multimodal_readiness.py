"""M4.4 多模态验收的证据完整性与 No-Go 报告。"""

from __future__ import annotations

from datetime import date
from typing import Any

from .coverage import build_multimodal_coverage_report
from .models import EvaluationCase


_VISION_METRIC_FIELDS = (
    "total_pages",
    "vision_routed_pages",
    "cache_hits",
    "vision_calls",
    "vision_failures",
    "document_p95_ms",
)
_COST_GATE_FIELDS = (
    "baseline",
    "target",
    "quality_floor",
    "price_version",
    "price_effective_date",
    "approval_id",
)


def build_m4_readiness_report(
    cases: list[EvaluationCase],
    run_ledger: dict[str, Any] | None,
    *,
    candidate_inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """汇总 M4.4 必需证据，缺失或不一致时始终返回 No-Go。"""
    ledger = run_ledger if isinstance(run_ledger, dict) else {}
    region_cases = [case for case in cases if case.dataset_split is not None]
    verified_cases = [case for case in region_cases if case.review_status == "verified"]
    holdout_cases = [case for case in region_cases if case.dataset_split == "holdout"]
    blockers: list[str] = []

    coverage = build_multimodal_coverage_report(cases)
    if not coverage["ready"]:
        blockers.append("区域级评测集未达到发布准入")
    unverified_ids = [case.case_id for case in region_cases if case.review_status != "verified"]
    if unverified_ids:
        blockers.append(f"存在未人工核验的区域样本: {len(unverified_ids)}")

    holdout = _validate_holdout(ledger.get("holdout"), holdout_cases, blockers)
    vision_metrics = _validate_vision_metrics(ledger.get("vision_metrics"), blockers)
    high_risk_errors = _validate_high_risk_errors(ledger.get("high_risk_verified_errors"), blockers)
    cost_gate = _validate_cost_gate(ledger.get("cost_gate"), blockers)

    inventory = dict(candidate_inventory) if isinstance(candidate_inventory, dict) else {}
    return {
        "ready": not blockers,
        "coverage": coverage,
        "region_case_count": len(region_cases),
        "verified_region_case_count": len(verified_cases),
        "candidate_inventory": inventory,
        "holdout": holdout,
        "high_risk_verified_errors": high_risk_errors,
        "vision_metrics": vision_metrics,
        "cost_gate": cost_gate,
        "blockers": blockers,
    }


def m4_readiness_to_markdown(report: dict[str, Any]) -> str:
    """将准入结果输出为不隐藏 No-Go 原因的审阅文本。"""
    status = "Go" if report.get("ready") else "No-Go"
    coverage = report.get("coverage", {})
    vision_metrics = report.get("vision_metrics", {})
    lines = [
        "# M4.4 多模态验收准入报告",
        "",
        f"- 决策：{status}",
        f"- 区域级样本：{report.get('region_case_count', 0)}",
        f"- 已人工核验区域样本：{report.get('verified_region_case_count', 0)}",
        f"- 冻结留出集样本：{report.get('holdout', {}).get('case_count', 0)}",
        f"- 高风险视觉数字误入 verified：{report.get('high_risk_verified_errors')}",
        f"- 视觉路由比例：{_format_ratio(vision_metrics.get('vision_routing_ratio'))}",
        f"- 缓存命中率：{_format_ratio(vision_metrics.get('cache_hit_ratio'))}",
        f"- 视觉调用失败率：{_format_ratio(vision_metrics.get('failure_rate'))}",
        f"- 单文档 P95：{vision_metrics.get('document_p95_ms', '缺失')} ms",
        "",
        "## 覆盖缺口",
        "",
        f"- {coverage.get('deficits', {}) or '无'}",
        "",
        "## No-Go 原因",
        "",
    ]
    blockers = report.get("blockers", [])
    lines.extend(f"- {blocker}" for blocker in blockers) if blockers else lines.append("- 无")
    return "\n".join(lines) + "\n"


def _validate_holdout(
    value: object,
    holdout_cases: list[EvaluationCase],
    blockers: list[str],
) -> dict[str, Any]:
    expected_ids = {case.case_id for case in holdout_cases}
    if not isinstance(value, dict):
        blockers.append("缺少冻结留出集运行结果")
        return {"frozen": False, "case_count": len(holdout_cases)}
    recorded_ids = value.get("case_ids")
    frozen = value.get("frozen") is True
    result_id = value.get("result_id")
    if not frozen or not isinstance(result_id, str) or not result_id.strip():
        blockers.append("冻结留出集结果缺少冻结标记或运行 ID")
    if not isinstance(recorded_ids, list) or set(recorded_ids) != expected_ids:
        blockers.append("冻结留出集结果与当前 holdout 样本不一致")
    return {
        "frozen": frozen,
        "case_count": len(holdout_cases),
        "case_ids": recorded_ids if isinstance(recorded_ids, list) else [],
        "result_id": result_id if isinstance(result_id, str) else None,
    }


def _validate_vision_metrics(value: object, blockers: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        blockers.append("缺少视觉运行账本")
        return {}
    missing = [field for field in _VISION_METRIC_FIELDS if not _is_nonnegative_number(value.get(field))]
    if missing:
        blockers.append(f"视觉运行账本缺少或非法字段: {', '.join(missing)}")
        return {}
    total_pages = value["total_pages"]
    vision_routed_pages = value["vision_routed_pages"]
    cache_hits = value["cache_hits"]
    vision_calls = value["vision_calls"]
    vision_failures = value["vision_failures"]
    if vision_routed_pages > total_pages:
        blockers.append("视觉路由页数不能超过总页数")
    if cache_hits > vision_calls:
        blockers.append("缓存命中数不能超过视觉调用数")
    if vision_failures > vision_calls:
        blockers.append("视觉失败数不能超过视觉调用数")
    return {
        **{field: value[field] for field in _VISION_METRIC_FIELDS},
        "vision_routing_ratio": vision_routed_pages / total_pages if total_pages else None,
        "cache_hit_ratio": cache_hits / vision_calls if vision_calls else None,
        "failure_rate": vision_failures / vision_calls if vision_calls else None,
    }


def _validate_high_risk_errors(value: object, blockers: list[str]) -> int | None:
    if type(value) is not int or value < 0:
        blockers.append("缺少高风险视觉误入 verified 统计")
        return None
    if value:
        blockers.append(f"高风险视觉数字误入 verified: {value}")
    return value


def _validate_cost_gate(value: object, blockers: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        blockers.append("缺少成本门禁批准记录")
        return {}
    missing = [field for field in _COST_GATE_FIELDS if not isinstance(value.get(field), str) or not value[field].strip()]
    if "price_effective_date" not in missing:
        try:
            date.fromisoformat(value["price_effective_date"])
        except ValueError:
            missing.append("price_effective_date")
    if missing:
        blockers.append(f"成本门禁缺少字段: {', '.join(sorted(set(missing)))}")
        return {}
    return {field: value[field] for field in _COST_GATE_FIELDS}


def _is_nonnegative_number(value: object) -> bool:
    return type(value) in {int, float} and value >= 0


def _format_ratio(value: object) -> str:
    return "缺失" if not isinstance(value, (int, float)) else f"{value:.2%}"
