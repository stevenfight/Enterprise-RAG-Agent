# -*- coding: utf-8 -*-
"""从真实 PDF 页面生成待人工复核的区域候选，不生成事实真值。"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


RegionDetector = Callable[[object], Iterable[tuple[str, tuple[float, float, float, float]]]]


def detect_table_regions(page: object) -> list[tuple[str, tuple[float, float, float, float]]]:
    """使用 PyMuPDF 已检测到的表格边界建立候选，仍须人工复核内容。"""
    return [("table", tuple(table.bbox)) for table in page.find_tables().tables]


def build_region_candidates(
    pdf_paths: Iterable[Path],
    *,
    region_detector: RegionDetector = detect_table_regions,
) -> list[dict]:
    """从受控 PDF 文件产生可追溯的 pending_review 区域候选。"""
    import fitz

    candidates: list[dict] = []
    seen_ids: set[str] = set()
    for pdf_path in sorted((Path(path) for path in pdf_paths), key=lambda item: item.name):
        source_sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        document = fitz.open(pdf_path)
        try:
            for page_index, page in enumerate(document, start=1):
                for region_type, bbox in region_detector(page):
                    normalized = _normalize_bbox(
                        _to_rendered_page_bbox(bbox, page),
                        page.rect.width,
                        page.rect.height,
                    )
                    if normalized is None:
                        continue
                    candidate_id = _candidate_id(source_sha256, page_index, region_type, normalized)
                    if candidate_id in seen_ids:
                        continue
                    seen_ids.add(candidate_id)
                    candidates.append({
                        "candidate_id": candidate_id,
                        "candidate_status": "pending_review",
                        "source_document_id": source_sha256,
                        "source_file": pdf_path.name,
                        "source_sha256": source_sha256,
                        "physical_page_number": page_index,
                        "region_type": region_type,
                        "modality": region_type,
                        "normalized_bbox": normalized,
                    })
        finally:
            document.close()
    return candidates


def write_region_candidates(candidates: Iterable[dict], output_path: Path) -> None:
    """以原子替换写入诊断候选；候选不等同于 verified 评测样本。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(output_path.name + ".writing")
    lines = [json.dumps(candidate, ensure_ascii=False, sort_keys=True) for candidate in candidates]
    temporary_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.replace(temporary_path, output_path)


def validate_region_candidates(candidates: Iterable[dict], pdf_root: Path) -> list[str]:
    """核对候选仍对应原始 PDF 哈希、物理页和受控归一化区域。"""
    import fitz

    pdf_root = Path(pdf_root).resolve()
    invalid_ids: list[str] = []
    document_cache: dict[Path, tuple[str, int]] = {}
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id", ""))
        source_file = str(candidate.get("source_file", ""))
        pdf_path = (pdf_root / source_file).resolve()
        if not candidate_id or pdf_path.name != source_file or not pdf_path.is_file():
            invalid_ids.append(candidate_id)
            continue
        if pdf_path not in document_cache:
            source_sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            document = fitz.open(pdf_path)
            try:
                document_cache[pdf_path] = (source_sha256, len(document))
            finally:
                document.close()
        source_sha256, page_count = document_cache[pdf_path]
        page_number = candidate.get("physical_page_number")
        bbox = candidate.get("normalized_bbox")
        if (
            candidate.get("source_sha256") != source_sha256
            or not isinstance(page_number, int)
            or page_number < 1
            or page_number > page_count
            or not _is_normalized_bbox(bbox)
        ):
            invalid_ids.append(candidate_id)
    return invalid_ids


def build_review_sample(
    candidates: Iterable[dict],
    *,
    document_splits: Mapping[str, str],
    company_by_document: Mapping[str, str],
    target_counts: Mapping[str, int] | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    """从待复核候选稳定抽取按文档和公司隔离的人工审核包。"""
    target_counts = dict(target_counts or {"development": 30, "holdout": 10})
    _validate_review_targets(target_counts)
    normalized_candidates = [_validate_review_candidate(candidate) for candidate in candidates]
    source_files = {candidate["source_file"] for candidate in normalized_candidates}
    missing_splits = sorted(source_files - set(document_splits))
    missing_companies = sorted(source_files - set(company_by_document))
    if missing_splits:
        raise ValueError(f"候选缺少文档分区: {', '.join(missing_splits)}")
    if missing_companies:
        raise ValueError(f"候选缺少公司映射: {', '.join(missing_companies)}")
    invalid_splits = sorted({document_splits[source_file] for source_file in source_files} - {"development", "holdout"})
    if invalid_splits:
        raise ValueError(f"文档分区不合法: {', '.join(invalid_splits)}")
    development_companies = {
        company_by_document[source_file]
        for source_file in source_files
        if document_splits[source_file] == "development"
    }
    holdout_companies = {
        company_by_document[source_file]
        for source_file in source_files
        if document_splits[source_file] == "holdout"
    }
    overlap = sorted(development_companies & holdout_companies)
    if overlap:
        raise ValueError(f"公司不能同时出现于 development 与 holdout: {', '.join(overlap)}")

    selected: list[dict] = []
    metadata: dict[str, Any] = {
        "packet_version": "v7-m1-review-packet-1",
        "packet_status": "pending_review",
        "ready_for_verified_gate": False,
        "selection_rules": [
            "同一 source_file 与 physical_page_number 最多保留一条候选",
            "按 source_file 轮转抽样，避免单一文档主导",
            "development 与 holdout 的公司和文档必须隔离",
            "候选不含人工真值，不能直接写入 verified",
        ],
    }
    for split in ("development", "holdout"):
        split_candidates = [
            candidate
            for candidate in normalized_candidates
            if document_splits[candidate["source_file"]] == split
        ]
        split_sample = _round_robin_unique_page_sample(split_candidates, target_counts[split], split)
        for candidate in split_sample:
            candidate.update({
                "candidate_status": "pending_review",
                "review_status": "pending_review",
                "dataset_split": split,
                "company": company_by_document[candidate["source_file"]],
                "suggested_category": "ordinary_financial_table",
            })
        selected.extend(split_sample)
        metadata[split] = {
            "count": len(split_sample),
            "source_files": sorted({candidate["source_file"] for candidate in split_sample}),
            "companies": sorted({candidate["company"] for candidate in split_sample}),
            "source_pages": [
                {"source_file": candidate["source_file"], "physical_page_number": candidate["physical_page_number"]}
                for candidate in split_sample
            ],
        }
    metadata["sample_count"] = len(selected)
    return selected, metadata


def write_review_sample(
    sample: Iterable[dict],
    metadata: Mapping[str, Any],
    output_path: Path,
) -> tuple[Path, Path]:
    """原子写入待人工复核 JSONL 与同名元数据，不改变原始候选库存。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(sample)
    if any(row.get("candidate_status") != "pending_review" or row.get("review_status") != "pending_review" for row in rows):
        raise ValueError("审核包只能写入 pending_review 候选")
    _write_jsonl_atomic(rows, output_path)
    metadata_path = output_path.with_suffix(".metadata.json")
    _write_json_atomic(dict(metadata), metadata_path)
    return output_path, metadata_path


def _normalize_bbox(
    bbox: tuple[float, float, float, float],
    page_width: float,
    page_height: float,
) -> list[float] | None:
    if page_width <= 0 or page_height <= 0 or len(bbox) != 4:
        return None
    x0, y0, x1, y1 = (float(value) for value in bbox)
    if not (0 <= x0 < x1 <= page_width and 0 <= y0 < y1 <= page_height):
        return None
    return [round(x0 / page_width, 6), round(y0 / page_height, 6), round(x1 / page_width, 6), round(y1 / page_height, 6)]


def _to_rendered_page_bbox(
    bbox: tuple[float, float, float, float],
    page: object,
) -> tuple[float, float, float, float]:
    """将解析器提供的未旋转 PDF 坐标转换为页图的旋转后坐标。"""
    import fitz

    return tuple(fitz.Rect(bbox) * page.rotation_matrix)


def _candidate_id(
    source_sha256: str,
    page_number: int,
    region_type: str,
    normalized_bbox: list[float],
) -> str:
    canonical = f"{source_sha256}:{page_number}:{region_type}:{','.join(map(str, normalized_bbox))}"
    return "region-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _is_normalized_bbox(value: object) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    x0, y0, x1, y1 = value
    return all(isinstance(item, (int, float)) for item in value) and 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1


def _validate_review_targets(target_counts: Mapping[str, int]) -> None:
    if set(target_counts) != {"development", "holdout"}:
        raise ValueError("抽样目标必须同时包含 development 和 holdout")
    if any(type(count) is not int or count <= 0 for count in target_counts.values()):
        raise ValueError("抽样目标必须为正整数")


def _validate_review_candidate(candidate: dict) -> dict:
    source_file = candidate.get("source_file")
    page_number = candidate.get("physical_page_number")
    candidate_id = candidate.get("candidate_id")
    if not isinstance(source_file, str) or not source_file.strip():
        raise ValueError("候选缺少 source_file")
    if type(page_number) is not int or page_number <= 0:
        raise ValueError("候选缺少合法 physical_page_number")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("候选缺少 candidate_id")
    if not _is_normalized_bbox(candidate.get("normalized_bbox")):
        raise ValueError("候选缺少合法 normalized_bbox")
    return dict(candidate)


def _round_robin_unique_page_sample(candidates: list[dict], target_count: int, split: str) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for candidate in sorted(candidates, key=lambda item: (item["source_file"], item["physical_page_number"], item["candidate_id"])):
        grouped.setdefault(candidate["source_file"], []).append(candidate)
    selected: list[dict] = []
    seen_pages: set[tuple[str, int]] = set()
    positions = {source_file: 0 for source_file in grouped}
    while len(selected) < target_count:
        progressed = False
        for source_file in sorted(grouped):
            rows = grouped[source_file]
            while positions[source_file] < len(rows):
                candidate = rows[positions[source_file]]
                positions[source_file] += 1
                page_key = (source_file, candidate["physical_page_number"])
                if page_key in seen_pages:
                    continue
                selected.append(dict(candidate))
                seen_pages.add(page_key)
                progressed = True
                break
            if len(selected) == target_count:
                break
        if not progressed:
            raise ValueError(f"{split} 可用的不同源页不足，无法抽取 {target_count} 条候选")
    return selected


def _write_jsonl_atomic(rows: list[dict], output_path: Path) -> None:
    temporary_path = output_path.with_name(output_path.name + ".writing")
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    temporary_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.replace(temporary_path, output_path)


def _write_json_atomic(payload: dict[str, Any], output_path: Path) -> None:
    temporary_path = output_path.with_name(output_path.name + ".writing")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary_path, output_path)
