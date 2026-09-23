# -*- coding: utf-8 -*-
"""M1.7 来源视觉定位字段的兼容契约测试。"""

from src.api_service import SourceInfo, _build_agent_answer_sources


def test_source_info_visual_locator_is_optional_and_old_payload_is_unchanged():
    source = SourceInfo(
        index=1,
        source_file="示例报告.pdf",
        pages=[3],
        company_name="示例公司",
        scores={},
        excerpt="原有摘要",
    )

    expected_payload = {
        "index": 1,
        "source_file": "示例报告.pdf",
        "pages": [3],
        "document_pages": [],
        "company_name": "示例公司",
        "scores": {},
        "excerpt": "原有摘要",
    }
    assert source.model_dump() == expected_payload
    from fastapi.encoders import jsonable_encoder

    assert jsonable_encoder(source) == expected_payload


def test_source_info_preserves_only_complete_visual_locator_from_retrieved_source():
    sources = _build_agent_answer_sources([
        {
            "source_file": "示例报告.pdf",
            "pages": [3],
            "company_name": "示例公司",
            "content": "表格正文",
            "visual_locator": {
                "manifest_id": "manifest-1",
                "page_artifact_id": "page-1",
                "visual_region_id": "region-1",
                "normalized_bbox": [0.1, 0.2, 0.8, 0.9],
                "artifact_status": "complete",
            },
        },
        {
            "source_file": "不完整报告.pdf",
            "pages": [4],
            "company_name": "示例公司",
            "visual_locator": {
                "manifest_id": "manifest-2",
                "page_artifact_id": "page-2",
                "visual_region_id": "region-2",
                "normalized_bbox": [0.1, 0.2, 0.8, 0.9],
                "artifact_status": "incomplete",
            },
        },
    ])

    assert sources[0]["visual_locator"] == {
        "manifest_id": "manifest-1",
        "page_artifact_id": "page-1",
        "visual_region_id": "region-1",
        "normalized_bbox": [0.1, 0.2, 0.8, 0.9],
        "artifact_status": "complete",
    }
    assert "visual_locator" not in sources[1]
    assert sources[1]["visual_preview_status"] == "incomplete"
