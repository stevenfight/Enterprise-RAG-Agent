"""旧版 generation/retrieval 评测样本迁移契约。"""

import hashlib
import json
from pathlib import Path

import pytest

from src.evaluation import ValidationError, load_jsonl_cases
from src.evaluation.legacy_migration import migrate_legacy_datasets


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_GENERATION = PROJECT_ROOT / "tests" / "eval_datasets" / "generation_queries.json"
LEGACY_RETRIEVAL = PROJECT_ROOT / "tests" / "eval_datasets" / "retrieval_queries.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_migration_generates_v7_cases_and_preserves_legacy_criteria(tmp_path: Path):
    generation_hash = _sha256(LEGACY_GENERATION)
    retrieval_hash = _sha256(LEGACY_RETRIEVAL)

    outputs = migrate_legacy_datasets(
        generation_path=LEGACY_GENERATION,
        retrieval_path=LEGACY_RETRIEVAL,
        output_dir=tmp_path,
    )

    generation_cases = load_jsonl_cases(outputs["generation"])
    retrieval_cases = load_jsonl_cases(outputs["retrieval"])
    assert len(generation_cases) == 10
    assert len(retrieval_cases) == 10
    assert {case.case_id for case in generation_cases} == {f"gen-{index:03d}" for index in range(1, 11)}
    assert {case.case_id for case in retrieval_cases} == {f"ret-{index:03d}" for index in range(1, 11)}
    assert all(case.review_status == "draft" for case in generation_cases + retrieval_cases)
    assert all(case.dataset_version == "legacy-v1-migrated" for case in generation_cases + retrieval_cases)

    revenue_case = next(case for case in generation_cases if case.case_id == "gen-001")
    assert revenue_case.expected_keywords == ["577", "578", "营业收入", "亿元"]
    assert revenue_case.expected_sources[0].source_file == "【财报】中芯国际：中芯国际2024年年度报告.pdf"
    assert revenue_case.expected_sources[0].pages == [8]
    assert revenue_case.expected_facts[0]["value"] == 577.96

    research_case = next(case for case in retrieval_cases if case.case_id == "ret-010")
    assert research_case.expected_keywords == ["DeepSeek", "代工", "需求"]
    assert research_case.expected_sources[0].source_file.startswith("【华泰证券】")
    assert research_case.expected_sources[0].pages == [1]

    manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
    assert manifest["source_format"] == "legacy-generation-retrieval-v1"
    assert manifest["case_count"] == {"generation": 10, "retrieval": 10}
    assert manifest["retrieval_criteria"]["ret-008"]["expected_sources"] == ["产能利用率", "中芯国际"]

    assert _sha256(LEGACY_GENERATION) == generation_hash
    assert _sha256(LEGACY_RETRIEVAL) == retrieval_hash


def test_migration_rejects_legacy_sample_without_explicit_mapping(tmp_path: Path):
    records = json.loads(LEGACY_GENERATION.read_text(encoding="utf-8"))
    records[0]["id"] = "gen-unknown"
    unknown_generation = tmp_path / "generation_queries.json"
    unknown_generation.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError, match="未配置迁移映射"):
        migrate_legacy_datasets(
            generation_path=unknown_generation,
            retrieval_path=LEGACY_RETRIEVAL,
            output_dir=tmp_path / "output",
        )
