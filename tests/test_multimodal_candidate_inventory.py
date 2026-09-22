"""M1.1 区域候选清点测试。"""

from pathlib import Path

import pytest


def test_candidate_inventory_uses_real_pdf_pages_and_normalized_regions(tmp_path: Path):
    import fitz

    from src.evaluation.multimodal_candidates import build_region_candidates

    pdf_path = tmp_path / "示例.pdf"
    document = fitz.open()
    document.new_page(width=200, height=100)
    document.save(pdf_path)
    document.close()

    candidates = build_region_candidates(
        [pdf_path],
        region_detector=lambda _page: [("table", (20, 10, 180, 90))],
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["candidate_status"] == "pending_review"
    assert candidate["source_file"] == "示例.pdf"
    assert candidate["physical_page_number"] == 1
    assert candidate["normalized_bbox"] == [0.1, 0.1, 0.9, 0.9]
    assert candidate["region_type"] == "table"
    assert candidate["modality"] == "table"


def test_candidate_inventory_normalizes_unrotated_bbox_to_rotated_page_image_space(tmp_path: Path):
    """90 度页的检测坐标必须转换到页图使用的旋转后坐标空间。"""
    import fitz

    from src.evaluation.multimodal_candidates import build_region_candidates

    pdf_path = tmp_path / "旋转页.pdf"
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    page.set_rotation(90)
    document.save(pdf_path)
    document.close()

    candidates = build_region_candidates(
        [pdf_path],
        region_detector=lambda _page: [("table", (20, 10, 100, 60))],
    )

    assert candidates[0]["normalized_bbox"] == [0.4, 0.1, 0.9, 0.5]


def test_candidate_inventory_ignores_invalid_or_duplicate_regions(tmp_path: Path):
    import fitz

    from src.evaluation.multimodal_candidates import build_region_candidates

    pdf_path = tmp_path / "示例.pdf"
    document = fitz.open()
    document.new_page(width=100, height=100)
    document.save(pdf_path)
    document.close()

    candidates = build_region_candidates(
        [pdf_path],
        region_detector=lambda _page: [
            ("table", (10, 10, 90, 90)),
            ("table", (10, 10, 90, 90)),
            ("table", (20, 20, 20, 80)),
        ],
    )

    assert len(candidates) == 1


def test_candidate_inventory_write_is_atomic_and_diagnostic_only(tmp_path: Path):
    from src.evaluation.multimodal_candidates import write_region_candidates

    output_path = tmp_path / "candidates.jsonl"
    candidates = [{"candidate_id": "candidate-1", "candidate_status": "pending_review"}]

    write_region_candidates(candidates, output_path)

    assert not output_path.with_name(output_path.name + ".writing").exists()
    assert output_path.read_text(encoding="utf-8").strip().startswith('{"candidate_id": "candidate-1"')


def test_candidate_validation_rejects_source_hash_or_page_drift(tmp_path: Path):
    import fitz

    from src.evaluation.multimodal_candidates import build_region_candidates, validate_region_candidates

    pdf_path = tmp_path / "示例.pdf"
    document = fitz.open()
    document.new_page(width=100, height=100)
    document.save(pdf_path)
    document.close()
    candidates = build_region_candidates([pdf_path], region_detector=lambda _page: [("table", (10, 10, 90, 90))])

    assert validate_region_candidates(candidates, tmp_path) == []
    candidates[0]["physical_page_number"] = 2
    assert validate_region_candidates(candidates, tmp_path) == [candidates[0]["candidate_id"]]


def _review_candidate(candidate_id: str, source_file: str, page: int) -> dict:
    return {
        "candidate_id": candidate_id,
        "candidate_status": "pending_review",
        "source_file": source_file,
        "source_sha256": "a" * 64,
        "physical_page_number": page,
        "region_type": "table",
        "modality": "table",
        "normalized_bbox": [0.1, 0.1, 0.9, 0.9],
    }


def test_review_sample_rejects_company_cross_split_leakage():
    from src.evaluation.multimodal_candidates import build_review_sample

    candidates = [
        _review_candidate("dev-1", "development.pdf", 1),
        _review_candidate("holdout-1", "holdout.pdf", 1),
    ]

    with pytest.raises(ValueError, match="公司不能同时出现"):
        build_review_sample(
            candidates,
            document_splits={"development.pdf": "development", "holdout.pdf": "holdout"},
            company_by_document={"development.pdf": "同一公司", "holdout.pdf": "同一公司"},
            target_counts={"development": 1, "holdout": 1},
        )


def test_review_sample_rotates_documents_deduplicates_pages_and_stays_pending():
    from src.evaluation.multimodal_candidates import build_review_sample

    candidates = [
        _review_candidate("dev-b-2", "development-b.pdf", 2),
        _review_candidate("hold-2", "holdout.pdf", 2),
        _review_candidate("dev-a-1-second", "development-a.pdf", 1),
        _review_candidate("dev-a-1-first", "development-a.pdf", 1),
        _review_candidate("dev-a-3", "development-a.pdf", 3),
        _review_candidate("dev-b-1", "development-b.pdf", 1),
        _review_candidate("hold-1", "holdout.pdf", 1),
    ]

    sample, metadata = build_review_sample(
        candidates,
        document_splits={
            "development-a.pdf": "development",
            "development-b.pdf": "development",
            "holdout.pdf": "holdout",
        },
        company_by_document={
            "development-a.pdf": "公司甲",
            "development-b.pdf": "公司乙",
            "holdout.pdf": "公司丙",
        },
        target_counts={"development": 3, "holdout": 2},
    )

    assert [item["candidate_id"] for item in sample] == ["dev-a-1-first", "dev-b-1", "dev-a-3", "hold-1", "hold-2"]
    assert all(item["candidate_status"] == "pending_review" for item in sample)
    assert all(item["review_status"] == "pending_review" for item in sample)
    assert len({(item["source_file"], item["physical_page_number"]) for item in sample}) == len(sample)
    assert metadata["development"]["count"] == 3
    assert metadata["holdout"]["count"] == 2
    assert metadata["ready_for_verified_gate"] is False


def test_review_sample_rejects_insufficient_unique_pages_and_writes_atomic_packet(tmp_path: Path):
    from src.evaluation.multimodal_candidates import build_review_sample, write_review_sample

    candidates = [
        _review_candidate("dev-1", "development.pdf", 1),
        _review_candidate("hold-1", "holdout.pdf", 1),
    ]
    kwargs = {
        "document_splits": {"development.pdf": "development", "holdout.pdf": "holdout"},
        "company_by_document": {"development.pdf": "公司甲", "holdout.pdf": "公司乙"},
    }
    with pytest.raises(ValueError, match="可用的不同源页不足"):
        build_review_sample(candidates, target_counts={"development": 2, "holdout": 1}, **kwargs)

    sample, metadata = build_review_sample(candidates, target_counts={"development": 1, "holdout": 1}, **kwargs)
    packet_path, metadata_path = write_review_sample(sample, metadata, tmp_path / "review-packet.jsonl")

    assert packet_path.exists() and metadata_path.exists()
    assert not packet_path.with_name(packet_path.name + ".writing").exists()
    assert '"review_status": "pending_review"' in packet_path.read_text(encoding="utf-8")
