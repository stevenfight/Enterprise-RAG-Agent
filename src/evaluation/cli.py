"""离线评测命令行入口。"""

import argparse
import json
from pathlib import Path

from .runner import EvaluationRunner
from .schema import load_jsonl_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="运行金融 Agent 确定性评测")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--minimum-pass-rate", type=float, default=0.98)
    args = parser.parse_args()
    cases = load_jsonl_cases(args.dataset)
    fixtures = json.loads(args.fixtures.read_text(encoding="utf-8"))
    report = EvaluationRunner().run(cases, fixtures)
    EvaluationRunner.write_reports(report, args.output_dir)
    return 0 if EvaluationRunner.passes_quality_gate(report, args.minimum_pass_rate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
