"""评测运行器和基线差异。"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .evaluators import evaluate_case
from .coverage import build_coverage_report, require_release_ready
from .models import EvaluationCase, EvaluationReport
from .schema import validate_cases


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
    def diff(baseline: dict[str, dict[str, Any]], candidate: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
        """列出修复、新失败和未变化样本。"""
        repaired = sorted(
            case_id for case_id, before in baseline.items()
            if not before.get("passed") and candidate.get(case_id, {}).get("passed")
        )
        new_failures = sorted(
            case_id for case_id, after in candidate.items()
            if not after.get("passed") and baseline.get(case_id, {}).get("passed")
        )
        return {"repaired": repaired, "new_failures": new_failures}

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
        if high_risk_failures or pass_rate < minimum_pass_rate:
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
