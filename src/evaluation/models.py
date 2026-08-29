"""评测平面使用的数据模型。"""

from dataclasses import dataclass, field
from typing import Any


class ValidationError(ValueError):
    """评测样本不符合规范。"""


@dataclass(frozen=True)
class ExpectedSource:
    source_file: str
    pages: list[int]


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    category: str
    query: str
    companies: list[str]
    expected_answer: str
    expected_facts: list[dict[str, Any]]
    expected_sources: list[ExpectedSource]
    expected_pages: list[int]
    numeric_tolerance: float
    expected_behavior: str
    expected_tools: list[str]
    risk_level: str
    review_status: str
    dataset_version: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EvaluationCase":
        if not isinstance(raw, dict):
            raise ValidationError("样本必须是对象")
        required = (
            "id", "category", "query", "companies", "expected_answer",
            "expected_facts", "expected_sources", "expected_pages",
            "numeric_tolerance", "expected_behavior", "expected_tools",
            "risk_level", "review_status", "dataset_version",
        )
        missing = [key for key in required if key not in raw]
        if missing:
            raise ValidationError(f"缺少必填字段: {', '.join(missing)}")
        case_id = str(raw["id"]).strip()
        if not case_id:
            raise ValidationError("样本 ID 不能为空")
        behavior = str(raw["expected_behavior"]).strip()
        if behavior not in {"answer", "refuse"}:
            raise ValidationError("expected_behavior 必须为 answer 或 refuse")
        sources = []
        for source in raw["expected_sources"]:
            if not isinstance(source, dict):
                raise ValidationError("expected_sources 必须是对象列表")
            filename = str(source.get("source_file", "")).strip()
            pages = source.get("pages", [])
            if not filename or not isinstance(pages, list) or not pages:
                raise ValidationError("来源必须包含 source_file 和 pages")
            if any(not isinstance(page, int) or page < 1 for page in pages):
                raise ValidationError("来源页码必须是正整数")
            sources.append(ExpectedSource(filename, list(dict.fromkeys(pages))))
        expected_pages = raw["expected_pages"]
        if not isinstance(expected_pages, list) or any(
            not isinstance(page, int) or page < 1 for page in expected_pages
        ):
            raise ValidationError("expected_pages 必须是正整数列表")
        if behavior == "answer" and (not sources or not expected_pages):
            raise ValidationError("回答样本必须包含来源和页码")
        tolerance = raw["numeric_tolerance"]
        if not isinstance(tolerance, (int, float)) or tolerance < 0:
            raise ValidationError("numeric_tolerance 必须是非负数字")
        return cls(
            case_id=case_id,
            category=str(raw["category"]),
            query=str(raw["query"]),
            companies=list(raw["companies"]),
            expected_answer=str(raw["expected_answer"]),
            expected_facts=list(raw["expected_facts"]),
            expected_sources=sources,
            expected_pages=list(dict.fromkeys(expected_pages)),
            numeric_tolerance=float(tolerance),
            expected_behavior=behavior,
            expected_tools=list(raw["expected_tools"]),
            risk_level=str(raw["risk_level"]),
            review_status=str(raw["review_status"]),
            dataset_version=str(raw["dataset_version"]),
        )


@dataclass(frozen=True)
class NumericComparison:
    passed: bool
    reason: str


@dataclass
class CaseEvaluation:
    case_id: str
    passed: bool
    metrics: dict[str, float] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    risk_level: str = "medium"


@dataclass
class EvaluationReport:
    mode: str
    metadata: dict[str, Any]
    results: list[CaseEvaluation]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "metadata": self.metadata,
            "passed": self.passed,
            "results": [
                {
                    "case_id": result.case_id,
                    "passed": result.passed,
                    "metrics": result.metrics,
                    "failures": result.failures,
                    "risk_level": result.risk_level,
                }
                for result in self.results
            ],
        }

    def to_markdown(self) -> str:
        """生成便于审阅的短报告，不隐藏失败样本。"""
        lines = [
            "# 金融 Agent 评测报告",
            "",
            f"- 模式：{self.mode}",
            f"- 结果：{'通过' if self.passed else '失败'}",
            f"- 样本数：{len(self.results)}",
            "",
            "| 样本 ID | 结果 | 指标 | 失败原因 |",
            "|---|---|---|---|",
        ]
        for result in self.results:
            metrics = ", ".join(f"{key}={value:.3f}" for key, value in result.metrics.items())
            failures = ", ".join(result.failures) or "无"
            lines.append(f"| {result.case_id} | {'通过' if result.passed else '失败'} | {metrics} | {failures} |")
        return "\n".join(lines) + "\n"
