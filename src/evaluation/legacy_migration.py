"""将旧版 generation/retrieval 样本迁移为 v7 JSONL。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ValidationError


DATASET_VERSION = "legacy-v1-migrated"
SMIC_ANNUAL_REPORT = "【财报】中芯国际：中芯国际2024年年度报告.pdf"
MOBILE_ANNUAL_REPORT = "移动2024年度报告.pdf"
TELECOM_ANNUAL_REPORT = "电信2024年度报告.pdf"
UNICOM_ANNUAL_REPORT = "联通2024年度报告.pdf"
EASTERN_RESEARCH_REPORT = "【东方证券】产能利用率提升，持续推进工艺迭代和产品性能升级.pdf"
ZHONGYUAN_RESEARCH_REPORT = "【中原证券】产能利用率显著提升，持续推进工艺迭代升级——中芯国际(688981)季报点评.pdf"
HUATAI_RESEARCH_REPORT = "【华泰证券】中芯国际（688981）：上调港股目标价到63港币，看好DeepSeek推动代工需求强劲增长.pdf"


def _source(source_file: str, pages: list[int]) -> dict[str, Any]:
    return {"source_file": source_file, "pages": pages}


def _fact(metric_key: str, value: float, unit: str, period: str, currency: str = "") -> dict[str, Any]:
    return {
        "metric_key": metric_key,
        "value": value,
        "unit": unit,
        "currency": currency,
        "period": period,
    }


# 这里的映射必须显式维护，避免迁移器根据查询文本猜测来源或页码。
GENERATION_MAPPINGS: dict[str, dict[str, Any]] = {
    "gen-001": {"sources": [_source(SMIC_ANNUAL_REPORT, [8])], "facts": [_fact("revenue", 577.96, "亿元", "2024", "CNY")]},
    "gen-002": {"sources": [_source(SMIC_ANNUAL_REPORT, [6])], "facts": [_fact("capacity_utilization", 85.6, "%", "2024")]},
    "gen-003": {"sources": [_source(MOBILE_ANNUAL_REPORT, [12])], "facts": [_fact("revenue", 10408, "亿元", "2024", "CNY")]},
    "gen-004": {"sources": [_source(TELECOM_ANNUAL_REPORT, [11])], "facts": [_fact("net_profit_attributable_to_parent", 330, "亿元", "2024", "CNY")]},
    "gen-005": {"sources": [_source(UNICOM_ANNUAL_REPORT, [10])], "facts": [_fact("revenue", 3896, "亿元", "2024", "CNY")]},
    "gen-006": {
        "sources": [_source(SMIC_ANNUAL_REPORT, [9])],
        "facts": [
            _fact("gross_margin", 18.6, "%", "2024"),
            _fact("net_margin", 9.3, "%", "2024"),
        ],
    },
    "gen-007": {
        "sources": [_source(SMIC_ANNUAL_REPORT, [8])],
        "facts": [
            _fact("revenue", 577.96, "亿元", "2024", "CNY"),
            _fact("revenue", 452.50, "亿元", "2023", "CNY"),
            _fact("revenue_growth", 27.7, "%", "2024"),
        ],
    },
    "gen-008": {
        "companies": ["中国移动", "中国电信", "中国联通"],
        "sources": [
            _source(MOBILE_ANNUAL_REPORT, [12]),
            _source(TELECOM_ANNUAL_REPORT, [11]),
            _source(UNICOM_ANNUAL_REPORT, [10]),
        ],
        "facts": [
            _fact("revenue", 10408, "亿元", "2024", "CNY") | {"company": "中国移动"},
            _fact("revenue", 5236, "亿元", "2024", "CNY") | {"company": "中国电信"},
            _fact("revenue", 3896, "亿元", "2024", "CNY") | {"company": "中国联通"},
        ],
    },
    "gen-009": {
        "sources": [_source(SMIC_ANNUAL_REPORT, [9])],
        "facts": [
            _fact("rd_revenue_ratio", 9.4, "%", "2024"),
            _fact("rd_revenue_ratio", 11.0, "%", "2023"),
        ],
    },
    "gen-010": {
        "sources": [_source(UNICOM_ANNUAL_REPORT, [10])],
        "facts": [
            _fact("profit_total", 251, "亿元", "2024", "CNY"),
            _fact("net_profit_attributable_to_parent", 90, "亿元", "2024", "CNY"),
            _fact("net_profit_growth", 10.5, "%", "2024"),
            _fact("roe", 5.5, "%", "2024"),
        ],
    },
}


RETRIEVAL_MAPPINGS: dict[str, dict[str, Any]] = {
    "ret-001": {"sources": [_source(SMIC_ANNUAL_REPORT, [8])]},
    "ret-002": {"sources": [_source(SMIC_ANNUAL_REPORT, [6])]},
    "ret-003": {"sources": [_source(MOBILE_ANNUAL_REPORT, [12])]},
    "ret-004": {"sources": [_source(TELECOM_ANNUAL_REPORT, [11])]},
    "ret-005": {"sources": [_source(UNICOM_ANNUAL_REPORT, [10])]},
    "ret-006": {"sources": [_source(SMIC_ANNUAL_REPORT, [9])]},
    "ret-007": {"sources": [_source(SMIC_ANNUAL_REPORT, [8])]},
    "ret-008": {
        "companies": ["中芯国际"],
        "sources": [
            _source(EASTERN_RESEARCH_REPORT, [1]),
            _source(ZHONGYUAN_RESEARCH_REPORT, [1]),
        ],
    },
    "ret-009": {
        "companies": ["中国移动", "中国电信", "中国联通"],
        "sources": [
            _source(MOBILE_ANNUAL_REPORT, [12]),
            _source(TELECOM_ANNUAL_REPORT, [11]),
            _source(UNICOM_ANNUAL_REPORT, [10]),
        ],
    },
    "ret-010": {"sources": [_source(HUATAI_RESEARCH_REPORT, [1])]},
}


def _load_legacy_records(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"无法读取旧版评测数据集: {path}") from exc
    if not isinstance(raw, list) or not raw:
        raise ValidationError(f"旧版评测数据集必须是非空数组: {path}")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in raw:
        if not isinstance(record, dict):
            raise ValidationError(f"旧版评测样本必须是对象: {path}")
        case_id = str(record.get("id", "")).strip()
        if not case_id:
            raise ValidationError(f"旧版评测样本缺少 ID: {path}")
        if case_id in seen:
            raise ValidationError(f"旧版评测数据集存在重复 ID: {case_id}")
        seen.add(case_id)
        records.append(record)
    return records


def _mapping_for(case_id: str, mappings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    try:
        return mappings[case_id]
    except KeyError as exc:
        raise ValidationError(f"未配置迁移映射: {case_id}") from exc


def _companies(record: dict[str, Any], mapping: dict[str, Any]) -> list[str]:
    mapped = mapping.get("companies")
    if mapped is not None:
        return list(mapped)
    company_name = record.get("company_name")
    if not isinstance(company_name, str) or not company_name.strip():
        raise ValidationError(f"样本缺少公司映射: {record.get('id', '')}")
    return [company_name.strip()]


def _expected_pages(sources: list[dict[str, Any]]) -> list[int]:
    return sorted({page for source in sources for page in source["pages"]})


def _case_from_legacy(
    record: dict[str, Any],
    mapping: dict[str, Any],
    *,
    retrieval: bool,
) -> dict[str, Any]:
    case_id = str(record["id"])
    sources = [
        {"source_file": str(source["source_file"]), "pages": list(source["pages"])}
        for source in mapping["sources"]
    ]
    keywords_key = "expected_keywords" if retrieval else "should_contain"
    keywords = record.get(keywords_key, [])
    if not isinstance(keywords, list) or any(not isinstance(keyword, str) or not keyword.strip() for keyword in keywords):
        raise ValidationError(f"旧版样本关键词字段无效: {case_id}")
    query = str(record.get("query", "")).strip()
    if not query:
        raise ValidationError(f"旧版样本缺少查询: {case_id}")
    expected_answer = "" if retrieval else str(record.get("reference_answer", ""))
    facts = [] if retrieval else [dict(fact) for fact in mapping.get("facts", [])]
    return {
        "id": case_id,
        "category": str(record.get("category", "")).strip(),
        "query": query,
        "companies": _companies(record, mapping),
        "expected_answer": expected_answer,
        "expected_facts": facts,
        "expected_sources": sources,
        "expected_pages": _expected_pages(sources),
        "numeric_tolerance": 0.01,
        "expected_behavior": "answer",
        "expected_tools": ["retrieve"],
        "risk_level": "medium" if retrieval and str(record.get("category")) == "research_report" else "high",
        "review_status": "draft",
        "dataset_version": DATASET_VERSION,
        "expected_keywords": list(keywords),
    }


def _validate_source_files(cases: list[dict[str, Any]], source_dir: Path) -> None:
    missing = sorted({
        source["source_file"]
        for case in cases
        for source in case["expected_sources"]
        if not (source_dir / source["source_file"]).is_file()
    })
    if missing:
        raise ValidationError(f"迁移来源文件不存在: {', '.join(missing)}")


def _write_jsonl(path: Path, cases: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False, sort_keys=True) for case in cases) + "\n",
        encoding="utf-8",
    )


def migrate_legacy_datasets(
    generation_path: str | Path,
    retrieval_path: str | Path,
    output_dir: str | Path,
    source_dir: str | Path | None = None,
) -> dict[str, Path]:
    """迁移旧版两组样本，并返回生成文件路径；旧文件只读保留。"""
    generation_records = _load_legacy_records(Path(generation_path))
    retrieval_records = _load_legacy_records(Path(retrieval_path))
    generation_cases = [
        _case_from_legacy(record, _mapping_for(str(record["id"]), GENERATION_MAPPINGS), retrieval=False)
        for record in generation_records
    ]
    retrieval_cases = [
        _case_from_legacy(record, _mapping_for(str(record["id"]), RETRIEVAL_MAPPINGS), retrieval=True)
        for record in retrieval_records
    ]
    resolved_source_dir = Path(source_dir) if source_dir is not None else Path(__file__).resolve().parents[2] / "data" / "stock_data" / "pdf_reports"
    _validate_source_files(generation_cases + retrieval_cases, resolved_source_dir)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    generation_output = output_path / "legacy-generation.jsonl"
    retrieval_output = output_path / "legacy-retrieval.jsonl"
    manifest_output = output_path / "legacy-migration-manifest.json"
    _write_jsonl(generation_output, generation_cases)
    _write_jsonl(retrieval_output, retrieval_cases)
    manifest = {
        "source_format": "legacy-generation-retrieval-v1",
        "dataset_version": DATASET_VERSION,
        "case_count": {"generation": len(generation_cases), "retrieval": len(retrieval_cases)},
        "outputs": {
            "generation": generation_output.name,
            "retrieval": retrieval_output.name,
        },
        "generation_criteria": {
            str(record["id"]): {
                "reference_answer": record.get("reference_answer", ""),
                "should_contain": record.get("should_contain", []),
                "description": record.get("description", ""),
            }
            for record in generation_records
        },
        "retrieval_criteria": {
            str(record["id"]): {
                "expected_sources": record.get("expected_sources", []),
                "expected_keywords": record.get("expected_keywords", []),
                "description": record.get("description", ""),
            }
            for record in retrieval_records
        },
        "source_mapping": {
            "generation": GENERATION_MAPPINGS,
            "retrieval": RETRIEVAL_MAPPINGS,
        },
        "review_note": "所有迁移样本均为 draft；来源页码已基于本地 PDF 只读核对，仍需人工逐条复核后才能进入 release-full。",
    }
    manifest_output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"generation": generation_output, "retrieval": retrieval_output, "manifest": manifest_output}
