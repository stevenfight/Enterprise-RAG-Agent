"""离线评测命令行入口。"""

import argparse
import hashlib
import json
import platform
from pathlib import Path

from .coverage import build_baseline_readiness_report
from .runner import EvaluationRunner
from .schema import load_jsonl_cases
from .source_audit import audit_source_files
from .source_binding import audit_source_binding
from .source_integrity import audit_source_integrity
from .thresholds import DEFAULT_THRESHOLDS_PATH, load_thresholds


_EVALUATION_MODES = ("offline-core", "local-full", "release-full")
_EXECUTION_CONTEXTS = ("pr", "local", "release")
_BASELINE_PROVENANCE_FIELDS = (
    "code_sha",
    "model_id",
    "prompt_version",
    "index_version",
    "dataset_version",
)


def _file_sha256(path: Path) -> str:
    """计算评测输入文件内容指纹，供报告复现时核对。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_execution_context(mode: str, context: str | None) -> None:
    """阻止全量评测从 PR 或未授权上下文误触发。"""
    if mode == "offline-core" and context not in {None, "pr"}:
        raise ValueError("offline-core 仅允许 pr 或未声明执行上下文")
    if mode == "local-full" and context != "local":
        raise ValueError("local-full 必须使用 local 执行上下文")
    if mode == "release-full" and context != "release":
        raise ValueError("release-full 必须使用 release 执行上下文")


def _validate_local_full_provenance(args: argparse.Namespace) -> None:
    """阻止缺少版本来源的本地全量报告被误作可复现基线。"""
    if args.mode != "local-full":
        return
    missing_fields = [
        field_name
        for field_name in _BASELINE_PROVENANCE_FIELDS
        if not getattr(args, field_name) or not getattr(args, field_name).strip()
    ]
    if missing_fields:
        raise ValueError(
            "local-full 基线候选运行缺少可追溯元数据: "
            + ", ".join(missing_fields)
        )


def _write_json_report(report: dict[str, object], output_path: Path) -> None:
    """写入只读就绪报告，不创建评测结果或调用外部服务。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="运行金融 Agent 确定性评测")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--baseline-readiness-output", type=Path)
    parser.add_argument("--mode", choices=_EVALUATION_MODES, default="offline-core")
    parser.add_argument("--execution-context", choices=_EXECUTION_CONTEXTS, default=None)
    parser.add_argument("--code-sha", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--prompt-version", default=None)
    parser.add_argument("--index-version", default=None)
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS_PATH)
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
    parser.add_argument(
        "--source-binding-manifest",
        type=Path,
        default=None,
        help="数据集与来源清单的路径及 SHA-256 绑定清单",
    )
    args = parser.parse_args()
    if args.baseline_readiness_output is not None:
        cases = load_jsonl_cases(args.dataset)
        readiness = build_baseline_readiness_report(cases)
        _write_json_report(readiness, args.baseline_readiness_output)
        return 0 if readiness["ready"] else 1
    if args.fixtures is None or args.output_dir is None:
        parser.error("常规评测必须提供 --fixtures 和 --output-dir")
    _validate_execution_context(args.mode, args.execution_context)
    _validate_local_full_provenance(args)
    cases = load_jsonl_cases(args.dataset)
    fixtures = json.loads(args.fixtures.read_text(encoding="utf-8"))
    thresholds = load_thresholds(args.thresholds)
    if args.minimum_pass_rate is not None:
        thresholds = {**thresholds, "minimum_pass_rate": args.minimum_pass_rate}
    report = EvaluationRunner(
        mode=args.mode,
        code_sha=args.code_sha or "unknown",
        model_id=args.model_id or "fixture",
        prompt_version=args.prompt_version or "unknown",
        index_version=args.index_version or "unknown",
        dataset_version=args.dataset_version or "unknown",
    ).run(cases, fixtures)
    report.metadata["execution_context"] = args.execution_context or "unspecified"
    report.metadata["input_sha256"] = {
        "dataset": _file_sha256(args.dataset),
        "fixtures": _file_sha256(args.fixtures),
        "thresholds": _file_sha256(args.thresholds),
    }
    report.metadata["quality_gate_thresholds"] = dict(thresholds)
    report.metadata["python_runtime"] = {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
    }
    source_audit = None
    source_integrity = None
    source_binding = None
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
    if args.source_binding_manifest is not None:
        if args.source_inventory is None:
            source_binding = {
                "manifest_path": str(args.source_binding_manifest),
                "manifest_error": "绑定清单审计需要同时传入 --source-inventory",
                "path_mismatches": [],
                "missing_files": [],
                "hash_mismatches": [],
                "actual_sha256": {},
                "ready": False,
            }
        else:
            source_binding = audit_source_binding(
                args.dataset,
                args.source_inventory,
                args.source_binding_manifest,
            )
        report.metadata["source_binding"] = source_binding
    EvaluationRunner.write_reports(report, args.output_dir)
    return 0 if (
        EvaluationRunner.passes_quality_gate(report, thresholds=thresholds)
        and (source_audit is None or source_audit["ready"])
        and (source_integrity is None or source_integrity["ready"])
        and (source_binding is None or source_binding["ready"])
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
