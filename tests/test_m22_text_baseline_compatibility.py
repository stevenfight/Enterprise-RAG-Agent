# -*- coding: utf-8 -*-
"""M-T22 纯文本检索与问答的本地非回归边界测试。"""

from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

from src.retrieval import HybridRetriever, RAGGenerator


def _text_result(*, artifact_refs=None) -> dict:
    """构造同一条纯文本检索结果，可选附加视觉制品引用。"""
    result = {
        "parent_text": "2024 年营业收入为 100 亿元，经营活动现金流为 20 亿元。",
        "source_file": "纯文本年报.pdf",
        "pages": [3],
        "document_pages": 10,
        "company_name": "测试公司",
        "parent_key": "text-parent-1",
        "tags": ["financial"],
        "scores": {"vector": 0.8, "bm25": 0.7},
    }
    if artifact_refs is not None:
        result["artifact_refs"] = artifact_refs
    return result


def test_hybrid_merge_keeps_pure_text_ranking_when_visual_reference_is_present():
    """纯文本结果附带视觉引用时，HybridRetriever 融合输出保持不变。"""
    retriever = HybridRetriever.__new__(HybridRetriever)
    base_vector = [_text_result()]
    base_bm25 = [deepcopy(_text_result())]
    visual_vector = [_text_result(artifact_refs=["page-artifact-1"])]
    visual_bm25 = [deepcopy(_text_result(artifact_refs=["page-artifact-1"]))]

    base = retriever._merge_results(
        base_vector,
        base_bm25,
        metadata=[{"source_file": "纯文本年报.pdf", "pages": [3]}],
    )
    with_visual_reference = retriever._merge_results(
        visual_vector,
        visual_bm25,
        metadata=[
            {
                "source_file": "纯文本年报.pdf",
                "pages": [3],
                "artifact_refs": ["page-artifact-1"],
            }
        ],
    )

    assert with_visual_reference == base


def _run_text_query(tmp_path: Path, *, artifact_refs=None) -> dict:
    """使用固定检索和生成替身，隔离纯文本 RAG 输出对照。"""
    generator = RAGGenerator(tmp_path, api_key="offline-test-key")
    retriever = MagicMock()
    retriever.search.return_value = [
        _text_result(artifact_refs=artifact_refs)
    ]
    generator._get_retriever = MagicMock(return_value=retriever)
    generator._generate_answer = MagicMock(return_value="固定纯文本回答")

    return generator.query(
        "测试纯文本基线问题",
        company_name="测试公司",
        top_n=1,
    )


def test_rag_output_keeps_legacy_text_answer_and_sources_with_visual_reference(
    tmp_path: Path,
):
    """附带视觉引用不改变 RAG 上下文、答案和来源摘要。"""
    without_visual_reference = _run_text_query(tmp_path / "legacy")
    with_visual_reference = _run_text_query(
        tmp_path / "multimodal",
        artifact_refs=["page-artifact-1"],
    )

    assert with_visual_reference == without_visual_reference
