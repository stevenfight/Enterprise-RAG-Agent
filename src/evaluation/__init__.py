"""金融 Agent 确定性评测平面。"""

from .models import EvaluationCase, EvaluationReport, CaseEvaluation, ValidationError
from .schema import load_jsonl_cases
from .evaluators import compare_numeric, evaluate_case
from .runner import EvaluationRunner
from .coverage import CoverageRequirements, build_coverage_report, require_release_ready
from .thresholds import load_thresholds

__all__ = [
    "CaseEvaluation",
    "EvaluationCase",
    "EvaluationReport",
    "EvaluationRunner",
    "ValidationError",
    "compare_numeric",
    "evaluate_case",
    "load_jsonl_cases",
    "CoverageRequirements",
    "build_coverage_report",
    "require_release_ready",
    "load_thresholds",
]
