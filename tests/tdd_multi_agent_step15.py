# -*- coding: utf-8 -*-
"""
TDD 测试: 多 Agent 升级 - 阶段十五 文档类型标签打标与检索加权

对应 TDD 规格: openspec/changes/multi-agent-step15/specs/tdd-step15.md
测试总计: 14 项
  - SP15-A classify_doc_tags 分类规则: 4 项
  - SP15-B ingestion 读 tags: 2 项
  - SP15-C 检索结果带 tags: 1 项
  - SP15-D _merge_results 保留 tags: 1 项
  - SP15-E _classify_doc_type 类型判定: 2 项
  - SP15-F _compute_source_authority_boost 年报加成: 1 项
  - SP15-G _ensure_annual_report_coverage 保底: 1 项
  - SP15-H _format_results 输出 doc_type: 1 项
  - SP15-I RetrieveResultItem 响应模型暴露 tags: 1 项

编码: UTF-8
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# 将项目根目录加入 sys.path，使直接运行本脚本时 `import src` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============================================================
# SP15-A: classify_doc_tags 分类规则（4 项）
# ============================================================


class TestClassifyDocTags(unittest.TestCase):
    """TC-15-A: 按文件名子串将文档分类为对应标签"""

    def test_a01_annual_report(self):
        from src.text_splitter import classify_doc_tags
        self.assertEqual(classify_doc_tags("移动2024年度报告.pdf"), ["annual_report"])

    def test_a02_research_report(self):
        from src.text_splitter import classify_doc_tags
        self.assertEqual(classify_doc_tags("国信证券_中芯国际.pdf"), ["research_report"])

    def test_a03_meeting_minutes(self):
        from src.text_splitter import classify_doc_tags
        self.assertEqual(classify_doc_tags("中芯国际机构调研纪要.pdf"), ["meeting_minutes"])

    def test_a04_other(self):
        from src.text_splitter import classify_doc_tags
        self.assertEqual(classify_doc_tags("某文件.pdf"), ["other"])


# ============================================================
# SP15-B: ingestion 读 tags（2 项）
# ============================================================


class TestIngestionTags(unittest.TestCase):
    """TC-15-B: chunked JSON 中的 metainfo.tags 应透传到子块与索引元数据"""

    def _make_chunked_json(self, chunked_dir, tags):
        data = {
            "metainfo": {
                "sha1": "abc",
                "company_name": "中国电信",
                "file_name": "电信2024年度报告.md",
                "tags": tags,
            },
            "content": {
                "parent_chunks": [
                    {
                        "id": 0,
                        "lines": [1, 2],
                        "tokens": 10,
                        "pages": [1, 2],
                        "source_file": "电信2024年度报告.pdf",
                        "text": "营业收入 500 亿元",
                        "child_chunks": [
                            {"id": "0-0", "parent_id": 0, "tokens": 5, "text": "营业收入"},
                        ],
                    }
                ]
            },
        }
        (Path(chunked_dir) / "电信2024年度报告.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def test_b01_collect_chunks_with_tags(self):
        from src.ingestion import collect_chunks_by_company
        with tempfile.TemporaryDirectory() as tmp:
            self._make_chunked_json(tmp, ["annual_report"])
            company_data = collect_chunks_by_company(tmp)
            child_chunks = company_data["中国电信"]["child_chunks"]
            self.assertTrue(child_chunks, "应收集到子块")
            for c in child_chunks:
                self.assertEqual(c["tags"], ["annual_report"])

    def test_b02_metadata_writes_tags(self):
        from src import ingestion
        import faiss

        child_chunks = [{
            "child_id": "0-0",
            "parent_key": "电信2024年度报告::0",
            "parent_id": 0,
            "source_file": "电信2024年度报告.pdf",
            "pages": [1, 2],
            "company_name": "中国电信",
            "hash": "abcdef",
            "tags": ["annual_report"],
        }]
        parent_texts = {"电信2024年度报告::0": "营业收入 500 亿元"}

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(ingestion, "build_faiss_index", return_value=faiss.IndexFlatIP(1)), \
                 mock.patch.object(ingestion, "build_bm25_index", return_value=object()):
                ingestion.build_company_index("中国电信", child_chunks, parent_texts, tmp, "dummy-key")

            metadata_path = Path(tmp) / "中国电信" / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata[0]["tags"], ["annual_report"])


# ============================================================
# SP15-C: 检索结果带 tags（1 项）
# ============================================================


class TestSearchResultTags(unittest.TestCase):
    """TC-15-C: VectorRetriever.search 返回的结果 dict 应包含 tags"""

    def test_c01_vector_search_result_has_tags(self):
        from src.retrieval import VectorRetriever
        import faiss
        import numpy as np

        dim = 8
        index = faiss.IndexFlatIP(dim)
        index.add(np.array([[1.0] * dim], dtype=np.float32))

        vr = VectorRetriever.__new__(VectorRetriever)
        vr._loaded = True
        vr.index = index
        vr.metadata = [{
            "parent_key": "k1",
            "source_file": "电信2024年度报告.pdf",
            "pages": [1, 2],
            "company_name": "中国电信",
            "child_id": "0-0",
            "tags": ["annual_report"],
        }]
        vr.parent_texts = {"k1": "营业收入 500 亿元"}

        with mock.patch.object(vr, "_get_query_embedding", return_value=[1.0] * dim):
            results = vr.search("测试查询", top_k=1)

        self.assertEqual(results[0]["tags"], ["annual_report"])


# ============================================================
# SP15-D: _merge_results 保留 tags（1 项）
# ============================================================


class TestMergePreservesTags(unittest.TestCase):
    """TC-15-D: 向量与 BM25 结果合并后应保留原 tags"""

    def test_d01_merge_preserves_tags(self):
        from src.retrieval import HybridRetriever

        hr = HybridRetriever.__new__(HybridRetriever)
        vector_results = [{
            "parent_key": "k1",
            "parent_text": "文本",
            "source_file": "f.pdf",
            "pages": [1],
            "company_name": "c",
            "tags": ["annual_report"],
            "scores": {"vector": 0.9},
        }]
        bm25_results = [{
            "parent_key": "k1",
            "parent_text": "文本",
            "source_file": "f.pdf",
            "pages": [1],
            "company_name": "c",
            "tags": ["annual_report"],
            "scores": {"bm25": 1.0},
        }]

        merged = hr._merge_results(vector_results, bm25_results)
        self.assertEqual(merged[0]["tags"], ["annual_report"])


# ============================================================
# SP15-E: _classify_doc_type 类型判定（2 项）
# ============================================================


class TestClassifyDocType(unittest.TestCase):
    """TC-15-E: tags 优先，缺省时回退文件名"""

    def test_e01_tags_priority(self):
        from src.text_splitter import _classify_doc_type
        self.assertEqual(_classify_doc_type("国信证券.pdf", ["annual_report"]), "annual_report")

    def test_e02_filename_fallback(self):
        from src.text_splitter import _classify_doc_type
        self.assertEqual(_classify_doc_type("国信证券.pdf", None), "research_report")


# ============================================================
# SP15-F: _compute_source_authority_boost 年报加成（1 项）
# ============================================================


class TestSourceAuthorityBoost(unittest.TestCase):
    """TC-15-F: 年报且含财务数字时返回 0.10 加成"""

    def test_f01_annual_with_financial_numbers(self):
        from src.retrieval import _compute_source_authority_boost
        result = {
            "source_file": "电信2024年度报告.pdf",
            "tags": ["annual_report"],
            "parent_text": "营业收入 500 亿元",
        }
        self.assertEqual(_compute_source_authority_boost(result), 0.10)


# ============================================================
# SP15-G: _ensure_annual_report_coverage 保底（1 项）
# ============================================================


class TestEnsureAnnualReportCoverage(unittest.TestCase):
    """TC-15-G: 结果无年报时从 all_scored 补入最高分年报"""

    def test_g01_adds_annual_report(self):
        from src.retrieval import HybridRetriever

        hr = HybridRetriever.__new__(HybridRetriever)
        results = [{
            "parent_key": "k1",
            "company_name": "中国电信",
            "source_file": "国信证券.pdf",
            "tags": ["research_report"],
            "scores": {"rerank": 9.0},
        }]
        all_scored = results + [{
            "parent_key": "k2",
            "company_name": "中国电信",
            "source_file": "电信2024年度报告.pdf",
            "tags": ["annual_report"],
            "scores": {"rerank": 8.0},
        }]

        out = hr._ensure_annual_report_coverage(results, all_scored, top_n=3)
        sources = [r.get("source_file") for r in out]
        self.assertIn("电信2024年度报告.pdf", sources)


# ============================================================
# SP15-H: _format_results 输出 doc_type（1 项）
# ============================================================


class TestFormatResultsDocType(unittest.TestCase):
    """TC-15-H: 格式化结果应包含中文 doc_type 标签"""

    def test_h01_doc_type_label(self):
        from src.tools.retrieve_tool import RetrieveTool

        tool = RetrieveTool()
        results = [{
            "parent_text": "营业收入 500 亿元",
            "source_file": "电信2024年度报告.pdf",
            "pages": [1, 2],
            "company_name": "中国电信",
            "tags": ["annual_report"],
            "scores": {"rerank": 8.0, "confidence": "high"},
        }]

        formatted = tool._format_results(results, "查询", None)
        self.assertEqual(formatted["results"][0]["doc_type"], "年报")


# ============================================================
# SP15-I: /api/retrieve 响应模型暴露 tags（1 项）
# ============================================================


class TestRetrieveResultItemTags(unittest.TestCase):
    """TC-15-I: RetrieveResultItem 响应模型应包含并透出 tags 字段"""

    def test_i01_retrieve_result_item_has_tags(self):
        from src.api_service import RetrieveResultItem

        data = {
            "parent_text": "营业收入 500 亿元",
            "source_file": "电信2024年度报告.pdf",
            "pages": [1, 2],
            "company_name": "中国电信",
            "child_id": "0-0",
            "parent_key": "k1",
            "tags": ["annual_report"],
            "scores": {"rerank": 8.0},
        }
        item = RetrieveResultItem.model_validate(data)
        self.assertEqual(item.tags, ["annual_report"])
        self.assertEqual(item.model_dump()["tags"], ["annual_report"])


if __name__ == "__main__":
    unittest.main()
