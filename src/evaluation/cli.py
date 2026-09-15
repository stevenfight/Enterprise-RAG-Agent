"""离线评测命令行入口。"""

import argparse
import json
from pathlib import Path

from .runner import EvaluationRunner
from .schema import load_jsonl_cases
from .source_audit import audit_source_files
from .source_integrity import audit_source_integrity
from .thresholds import load_thresholds


def main() -> int:
    parser = argparse.ArgumentParser(description="运行金融 Agent 确定性评测")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--minimum-pass-rate", type=float, default=None)
    parser.add_argument(
        "--source-root",
        action="append",
        type=Path,
        default=[],
        help="来源文件审计根目录，可重复传入",
    )
    parser.add_argument(
        "--source-inventory",
        type=Path,
        default=None,
        help="冻结来源清单；与 --source-root 同时传入时启用哈希/大小/物理页绑定",
    )
    args = parser.parse_args()
    cases = load_jsonl_cases(args.dataset)
    fixtures = json.loads(args.fixtures.read_text(encoding="utf-8"))
    report = EvaluationRunner().run(cases, fixtures)
    thresholds = load_thresholds()
    minimum_pass_rate = (
        args.minimum_pass_rate
        if args.minimum_pass_rate is not None
        else thresholds["minimum_pass_rate"]
    )
    quality_gate_passed = EvaluationRunner.passes_quality_gate(
        report,
        minimum_pass_rate,
        thresholds=thresholds,
    )
    source_audit = None
    source_integrity = None
    if args.source_root:
        source_audit = audit_source_files(cases, args.source_root)
        report.metadata["source_audit"] = source_audit
    if args.source_inventory is not None:
        source_integrity = audit_source_integrity(
            cases,
            args.source_root,
            args.source_inventory,
        )
        report.metadata["source_integrity"] = source_integrity
    EvaluationRunner.write_reports(report, args.output_dir)
    return 0 if quality_gate_passed and (
        source_audit is None or source_audit["ready"]
    ) and (source_integrity is None or source_integrity["ready"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
