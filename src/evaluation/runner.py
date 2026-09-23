"""评测运行器和基线差异。"""

import json
from collections.abc import Callable
from numbers import Number
from pathlib import Path
from typing import Any

from .evaluators import evaluate_case
from .coverage import build_coverage_report, require_release_ready
from .models import EvaluationCase, EvaluationReport
from .schema import validate_cases


_VERSION_METADATA_KEYS = (
    "code_sha",
    "model_id",
    "prompt_version",
    "index_version",
    "dataset_version",
)


def _numeric_mapping(value: Any) -> dict[str, Number]:
    """提取显式数字映射，忽略布尔值和非数字值。"""
    if not isinstance(value, dict):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, Number) and not isinstance(item, bool)
    }


def _metric_changes(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    field_name: str,
) -> list[dict[str, Any]]:
    """比较两个结果中的显式数字指标，并保留可审计的变化值。"""
    changes = []
    case_ids = sorted(set(baseline) & set(candidate))
    for case_id in case_ids:
        before = _numeric_mapping(baseline[case_id].get(field_name))
        after = _numeric_mapping(candidate[case_id].get(field_name))
        for metric in sorted(set(before) & set(after)):
            if before[metric] == after[metric]:
                continue
            changes.append(
                {
                    "case_id": case_id,
                    "metric": metric,
                    "baseline": before[metric],
                    "candidate": after[metric],
                    "delta": round(after[metric] - before[metric], 12),
                }
            )
    return changes


def _pass_rate(report: EvaluationReport) -> float:
    """计算报告通过率；空报告按 0 处理，避免空集合伪装成通过。"""
    if not report.results:
        return 0.0
    return sum(result.passed for result in report.results) / len(report.results)


class EvaluationRunner:
    """支持固定夹具的离线运行器，不在 offline-core 调用外部 provider。"""

    def __init__(
        self,
        mode: str = "offline-core",
        provider: Callable[[EvaluationCase], dict[str, Any]] | None = None,
        code_sha: str = "unknown",
        model_id: str = "fixture",
        prompt_version: str = "unknown",
        index_version: str = "unknown",
        dataset_version: str = "unknown",
    ) -> None:
        if mode not in {"offline-core", "local-full", "release-full"}:
            raise ValueError("不支持的评测模式")
        self.mode = mode
        self.provider = provider
        self.metadata = {
            "mode": mode,
            "code_sha": code_sha,
            "model_id": model_id,
            "prompt_version": prompt_version,
            "index_version": index_version,
            "dataset_version": dataset_version,
            "external_service_called": False,
        }

    def run(self, cases: list[EvaluationCase], fixtures: dict[str, dict[str, Any]]) -> EvaluationReport:
        cases = validate_cases(cases)
        if self.metadata["dataset_version"] == "unknown":
            versions = {case.dataset_version for case in cases}
            if len(versions) == 1:
                self.metadata["dataset_version"] = versions.pop()
        coverage = build_coverage_report(cases)
        if self.mode == "release-full":
            require_release_ready(cases)
        self.metadata["coverage"] = coverage
        results = []
        for case in cases:
            if case.case_id in fixtures:
                actual = fixtures[case.case_id]
            elif self.mode == "offline-core":
                raise ValueError(f"offline-core 缺少固定夹具: {case.case_id}")
            elif self.provider is not None:
                self.metadata["external_service_called"] = True
                actual = self.provider(case)
            else:
                raise ValueError(f"模式 {self.mode} 未配置 provider: {case.case_id}")
            results.append(evaluate_case(case, actual))
        return EvaluationReport(self.mode, dict(self.metadata), results)

    @staticmethod
    def diff(baseline: dict[str, dict[str, Any]], candidate: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """比较基线与候选结果，列出状态、分数和显式性能变化。"""
        baseline_ids = set(baseline)
        candidate_ids = set(candidate)
        common_ids = baseline_ids & candidate_ids
        repaired = sorted(
            case_id for case_id, before in baseline.items()
            if not before.get("passed") and candidate.get(case_id, {}).get("passed")
        )
        new_failures = sorted(
            case_id for case_id, after in candidate.items()
            if not after.get("passed") and baseline.get(case_id, {}).get("passed")
        )
        score_changes = _metric_changes(baseline, candidate, "metrics")
        performance_changes = _metric_changes(baseline, candidate, "performance")
        changed_case_ids = {
            change["case_id"]
            for change in score_changes + performance_changes
        }
        unchanged = sorted(
            case_id
            for case_id in common_ids
            if baseline[case_id].get("passed") == candidate[case_id].get("passed")
            and case_id not in changed_case_ids
        )
        return {
            "repaired": repaired,
            "new_failures": new_failures,
            "added_cases": sorted(candidate_ids - baseline_ids),
            "removed_cases": sorted(baseline_ids - candidate_ids),
            "unchanged_cases": unchanged,
            "score_changes": score_changes,
            "performance_changes": performance_changes,
        }

    @staticmethod
    def compare_reports(
        baseline: EvaluationReport,
        candidate: EvaluationReport,
    ) -> dict[str, Any]:
        """比较两个完整报告，并保留发布所需版本元数据。"""
        baseline_results = {
            result.case_id: {
                "passed": result.passed,
                "metrics": dict(result.metrics),
            }
            for result in baseline.results
        }
        candidate_results = {
            result.case_id: {
                "passed": result.passed,
                "metrics": dict(result.metrics),
            }
            for result in candidate.results
        }
        comparison = EvaluationRunner.diff(baseline_results, candidate_results)
        comparison["metadata"] = {
            "baseline": {
                key: baseline.metadata.get(key)
                for key in _VERSION_METADATA_KEYS
            },
            "candidate": {
                key: candidate.metadata.get(key)
                for key in _VERSION_METADATA_KEYS
            },
        }
        baseline_rate = _pass_rate(baseline)
        candidate_rate = _pass_rate(candidate)
        comparison["pass_rate"] = {
            "baseline": baseline_rate,
            "candidate": candidate_rate,
            "delta": round(candidate_rate - baseline_rate, 12),
        }
        return comparison

    @staticmethod
    def passes_quality_gate(
        report: EvaluationReport,
        minimum_pass_rate: float = 0.98,
        thresholds: dict[str, Any] | None = None,
    ) -> bool:
        """执行硬门禁：高风险失败、总体通过率与启用的声明级证据门禁任一不足均失败。

        thresholds 提供且 claim_level_evidence_support 为 enabled 时，答案类样本
        必须携带 claim_level_evidence_support=1.0；缺失或不足都直接失败，
        调低 minimum_pass_rate 无法弥补该门禁。
        """
        if not report.results:
            return False
        high_risk_failures = [
            result for result in report.results
            if result.risk_level == "high" and not result.passed
        ]
        pass_rate = sum(result.passed for result in report.results) / len(report.results)
        configured_minimum_pass_rate = (
            thresholds.get("minimum_pass_rate", minimum_pass_rate)
            if thresholds is not None
            else minimum_pass_rate
        )
        high_risk_failure_limit = (
            thresholds.get("high_risk_failure_limit", 0)
            if thresholds is not None
            else 0
        )
        if len(high_risk_failures) > high_risk_failure_limit or pass_rate < configured_minimum_pass_rate:
            return False
        if thresholds and thresholds.get("claim_level_evidence_support") == "enabled":
            for result in report.results:
                # 拒答类样本没有期望声明，不适用声明级证据门禁。
                is_refusal = "refusal_accuracy" in result.metrics
                if not is_refusal and result.metrics.get("claim_level_evidence_support") != 1.0:
                    return False
        return True

    @staticmethod
    def write_reports(report: EvaluationReport, output_dir: str | Path) -> tuple[Path, Path]:
        """同时写 JSON 与 Markdown 报告。"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "evaluation-report.json"
        markdown_path = output_dir / "evaluation-report.md"
        json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(report.to_markdown(), encoding="utf-8")
        return json_path, markdown_path
