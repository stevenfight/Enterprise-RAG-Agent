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
    expected_keywords: list[str] = field(default_factory=list)
    source_document_id: str | None = None
    region_id: str | None = None
    region_type: str | None = None
    modality: str | None = None
    dataset_split: str | None = None
    source_sha256: str | None = None
    physical_page_number: int | None = None

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
        expected_keywords = raw.get("expected_keywords", [])
        if not isinstance(expected_keywords, list) or any(
            not isinstance(keyword, str) or not keyword.strip() for keyword in expected_keywords
        ):
            raise ValidationError("expected_keywords 必须是非空字符串列表")
        if behavior == "answer" and (not sources or not expected_pages):
            raise ValidationError("回答样本必须包含来源和页码")
        tolerance = raw["numeric_tolerance"]
        if not isinstance(tolerance, (int, float)) or tolerance < 0:
            raise ValidationError("numeric_tolerance 必须是非负数字")
        region_values = {
            key: raw.get(key)
            for key in ("source_document_id", "region_id", "region_type", "modality", "dataset_split")
        }
        has_region_fields = any(value is not None for value in region_values.values())
        if has_region_fields and any(not isinstance(value, str) or not value.strip() for value in region_values.values()):
            raise ValidationError("区域级样本必须完整提供文档、区域、模态和数据集分区")
        if has_region_fields and region_values["dataset_split"] not in {"development", "holdout"}:
            raise ValidationError("区域级样本 dataset_split 必须为 development 或 holdout")
        source_sha256 = raw.get("source_sha256")
        physical_page_number = raw.get("physical_page_number")
        if has_region_fields and (source_sha256 is None or physical_page_number is None):
            raise ValidationError("区域级样本必须提供来源 hash 与物理页")
        if (source_sha256 is None) != (physical_page_number is None):
            raise ValidationError("来源 hash 与物理页必须同时提供")
        if source_sha256 is not None and (
            not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)
        ):
            raise ValidationError("source_sha256 必须是小写 SHA-256")
        if physical_page_number is not None and (
            type(physical_page_number) is not int or physical_page_number <= 0
        ):
            raise ValidationError("physical_page_number 必须为正整数")
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
            expected_keywords=list(expected_keywords),
            source_document_id=region_values["source_document_id"],
            region_id=region_values["region_id"],
            region_type=region_values["region_type"],
            modality=region_values["modality"],
            dataset_split=region_values["dataset_split"],
            source_sha256=source_sha256,
            physical_page_number=physical_page_number,
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
