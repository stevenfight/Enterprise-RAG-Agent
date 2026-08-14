# 设计说明: 文档类型标签打标与检索加权（阶段十五）

> 编码: UTF-8

---

## 一、数据流

```
text_splitter.py  split_markdown_reports
        │  classify_doc_tags(file_name) → ["annual_report"]
        ▼
  chunked_reports/*.json  metainfo.tags = ["annual_report"]
        │
        ▼
ingestion.py  collect_chunks_by_company
        │  读 metainfo.tags → 每个 child_chunk.tags
        ▼
  child_chunks[].tags
        │  build_company_index
        ▼
  vector_dbs/<公司>/metadata.json[].tags
        │
        ▼
retrieval.py  VectorRetriever/BM25Retriever.search
        │  结果 dict 加 "tags": meta.get("tags", [])
        ▼
  _merge_results  保留 tags
        │
        ▼
  _compute_source_authority_boost（年报 + 财务数字 → hybrid +0.10）
        │
        ▼
  _gte_rerank / _fallback_rerank（年报 → rerank +1.5）
        │
        ▼
  _ensure_annual_report_coverage（某公司无年报 → 补最高分年报块）
        │
        ▼
retrieve_tool.py  _format_results → doc_type 中文标签（年报/研报/调研纪要/其他）
        │
        ▼
api_service.py  RetrieveResultItem.tags（/api/retrieve 响应透出 tags）
```

## 二、核心函数设计

### 1. `classify_doc_tags(file_name) -> list[str]`

位于 [src/text_splitter.py](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/text_splitter.py)，纯函数：

```python
TAG_RULES = [
    ("annual_report", ["年度报告", "年报", "【财报】"]),
    ("research_report", ["证券", "研报", "研究报"]),
    ("meeting_minutes", ["调研纪要", "会议纪要", "投资者关系"]),
]

def classify_doc_tags(file_name):
    name = file_name or ""
    for tag, keywords in TAG_RULES:
        if any(k in name for k in keywords):
            return [tag]
    return ["other"]
```

写入位置：`split_markdown_reports` 中构建 `result["metainfo"]` 时加 `"tags": classify_doc_tags(stem + ".pdf")`。

### 2. ingestion 读取 tags

[src/ingestion.py](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/ingestion.py)：

- `collect_chunks_by_company`：`tags = metainfo.get("tags", [])`，child_chunks.append 加 `"tags": tags`。
- `build_company_index`：metadata.append 加 `"tags": c.get("tags", [])`。

### 3. 检索结果带 tags

VectorRetriever / BM25Retriever 的 `search` 结果 dict 加：

```python
"tags": meta.get("tags", []),
```

### 4. `_merge_results` 保留 tags

两处 `merged[pk]` 构造加 `"tags": r.get("tags", [])`。

### 5. `_classify_doc_type(source_file, tags=None) -> str`

位于 HybridRetriever，优先 tags、回退文件名：

```python
def _classify_doc_type(self, source_file, tags=None):
    if tags:
        return tags[0]
    name = source_file or ""
    for tag, keywords in TAG_RULES:
        if any(k in name for k in keywords):
            return tag
    return "other"
```

### 6. `_compute_source_authority_boost(result) -> float`

年报 + 含财务数字 → `ANNUAL_REPORT_BOOST_HYBRID`（0.10），否则 0。复用 `_compute_data_richness_boost` 判断财务数字。

在 `_merge_results` 计算 hybrid 时叠加：

```python
authority_boost = self._compute_source_authority_boost(item)
hybrid_score = min(1.0, hybrid_score + data_boost + authority_boost)
```

### 7. rerank 阶段年报加分

`_gte_rerank` / `_fallback_rerank` 在写入 `rerank` 分后，对年报结果额外加 `ANNUAL_REPORT_BOOST_RERANK`（1.5），再排序。

### 8. `_ensure_annual_report_coverage(results, all_scored, top_n)`

当 `results` 中某公司无年报来源时，从 `all_scored` 中补充该公司最高分年报块（最多补到 top_n）。

在 [search 主流程](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/retrieval.py#L1126-L1132) rerank 之后、`_ensure_company_coverage` 之前或之后调用。

### 9. `_format_results` 输出 doc_type

[retrieve_tool.py](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/tools/retrieve_tool.py) 的 `_format_results` 加：

```python
"doc_type": DOC_TYPE_LABELS.get(_classify_doc_type(r.get("source_file"), r.get("tags")), "其他"),
```

其中 `DOC_TYPE_LABELS = {"annual_report": "年报", "research_report": "研报", "meeting_minutes": "调研纪要", "other": "其他"}`。

### 10. api_service 响应模型暴露 tags

[src/api_service.py](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/api_service.py) 的 `RetrieveResultItem`（`/api/retrieve` 响应项模型）新增：

```python
tags: List[str] = []
```

使检索接口直接透出 `tags` 打标结果（不再被 Pydantic 序列化丢弃）。

## 三、测试设计（不依赖 LLM）

| 规范 | 测试方式 |
|------|---------|
| SP15-A | 纯函数 `classify_doc_tags`，直接断言 |
| SP15-B | 构造临时 chunked JSON，调用 `collect_chunks_by_company`，断言 child_chunks 带 tags；构造 child_chunks 断言 `build_company_index` 不调用 API 部分（仅验证 metadata 结构，需 mock embedding） |
| SP15-C | 直接构造带 tags 的 meta，验证 search 结果 dict 组装（通过 mock metadata 列表） |
| SP15-D | 构造带 tags 的 vector/bm25 结果，调用 `_merge_results`，断言 tags 保留 |
| SP15-E | 纯函数 `_classify_doc_type`，断言 tags 优先与文件名回退 |
| SP15-F | 纯函数 `_compute_source_authority_boost`，断言年报+财务数字返回 0.10 |
| SP15-G | 构造 results/all_scored，断言无年报时补充年报块 |
| SP15-H | 直接调用 `_format_results`（mock 或纯函数），断言 doc_type 中文 |
| SP15-I | 构造含 tags 的 dict 用 `RetrieveResultItem.model_validate` 校验并 dump，断言 tags 透出 |

## 四、兼容性

- 无 tags 的旧 metadata → `meta.get("tags", [])` 返回空列表 → `_classify_doc_type` 回退文件名推断。
- `_ensure_annual_report_coverage` 在无年报候选时不改变结果（安全空操作）。
