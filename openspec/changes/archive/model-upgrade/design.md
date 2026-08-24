# 技术方案设计: 模型升级与检索精准度提升

> 编码: UTF-8
> 变更: model-upgrade
> 状态: 待审核

---

## 1. 总体架构

本次变更涉及 RAG 管线的三个核心环节,按依赖关系分步执行:

```
步骤1: Embedding 升级 (v1 -> v3)     [需重建索引,后续步骤依赖新索引]
  |
步骤2: 重排模型替换 (qwen-plus -> gte-rerank)  [独立于步骤1,但建议在新索引上验证]
  |
步骤3: 生成模型升级 (qwen-plus -> qwen-max)    [依赖步骤1+2的输出质量]
```

## 2. 步骤1: Embedding 模型升级

### 2.1 变更点

**文件: `src/retrieval.py`**

```python
# 变更前
EMBEDDING_MODEL = "text-embedding-v1"
EMBEDDING_DIM = 1536

# 变更后
EMBEDDING_MODEL = "text-embedding-v3"
EMBEDDING_DIM = 1024
```

**文件: `src/ingestion.py`**

```python
# 变更前
EMBEDDING_MODEL = "text-embedding-v1"
EMBEDDING_DIM = 1536

# 变更后
EMBEDDING_MODEL = "text-embedding-v3"
EMBEDDING_DIM = 1024
```

### 2.2 API 兼容性

`text-embedding-v3` 的 DashScope 调用方式与 `v1` 相同,均使用 `dashscope.TextEmbedding.call()`:

```python
resp = dashscope.TextEmbedding.call(
    model=EMBEDDING_MODEL,
    input=texts,
)
```

唯一差异是返回的 Embedding 维度从 1536 变为 1024。

### 2.3 索引重建流程

1. 备份现有索引目录 `data/stock_data/databases/vector_dbs/`
2. 修改常量后执行 `python src/ingestion.py --rebuild`
3. 验证新索引的 FAISS 向量维度为 1024
4. 执行测试用例验证检索功能

### 2.4 回滚方案

如果 v3 效果不佳,将常量改回 v1/1536 并从备份恢复旧索引。

## 3. 步骤2: 重排模型替换

### 3.1 变更点

**文件: `src/retrieval.py` - `_llm_rerank` 方法**

整体重写,从逐条 LLM 调用改为批量 gte-rerank 调用。

### 3.2 gte-rerank API 调用方式

```python
import dashscope

resp = dashscope.TextReRank.call(
    model="gte-rerank-v2",
    query=query,
    documents=[cand["parent_text"] for cand in candidates],
    top_n=top_n,
    return_documents=True,
)
```

返回结构:
```json
{
    "status_code": 200,
    "output": {
        "results": [
            {
                "index": 0,
                "relevance_score": 0.95,
                "document": {"text": "..."}
            },
            ...
        ]
    }
}
```

### 3.3 分数归一化

gte-rerank 返回的 `relevance_score` 范围为 0.0-1.0,需要映射到 0-10 以兼容现有置信度逻辑:

```python
rerank_score = result["relevance_score"] * 10.0
```

这样:
- `relevance_score >= 0.8` -> `rerank >= 8.0` -> confidence = "high"
- `relevance_score >= 0.5` -> `rerank >= 5.0` -> confidence = "medium"
- 其余 -> confidence = "low" 或 "medium"(取决于 hybrid 分数)

与现有 `_compute_confidence` 逻辑完全兼容。

### 3.4 字段兼容性处理

| 字段 | 当前来源 | 变更后来源 |
|------|----------|-----------|
| `scores.rerank` | LLM JSON score 字段 | gte-rerank relevance_score * 10 |
| `scores.rerank_reasoning` | LLM JSON reasoning 字段 | 置空(gte-rerank 不提供推理) |
| `scores.rerank_key_info` | LLM JSON key_info 字段 | 置空(gte-rerank 不提供关键信息) |

### 3.5 回退机制

```python
def _llm_rerank(self, query, candidates, top_n=RERANK_TOP_N):
    if not candidates:
        return ([], [])

    try:
        return self._gte_rerank(query, candidates, top_n)
    except Exception as e:
        logger.warning("[HybridRetriever] gte-rerank 调用失败: %s, 回退到 hybrid 排序", str(e))
        return self._fallback_rerank(candidates, top_n)
```

回退逻辑: 按 hybrid 分数降序排序,取 top_n。

### 3.6 方法签名变更

```python
# 变更前
def _llm_rerank(self, query, candidates, top_n=RERANK_TOP_N):
    # ... 逐条调用 LLM ...
    if not candidates:
        return []  # 不一致: 空列表 vs 元组
    # ...
    return top_results, scored_candidates

# 变更后
def _llm_rerank(self, query, candidates, top_n=RERANK_TOP_N):
    if not candidates:
        return ([], [])  # 统一返回元组,修复 ISSUE-004
    # ... gte-rerank 批量调用 ...
    return top_results, scored_candidates
```

## 4. 步骤3: 生成模型升级

### 4.1 变更点

**文件: `src/retrieval.py` - `RAGGenerator` 类**

```python
# 变更前
GENERATION_MODEL = "qwen-plus"

# 变更后
GENERATION_MODEL = "qwen-max"
```

**文件: `src/query_processor.py` - 保持不变**

```python
MODEL_NAME = "qwen-plus"  # 意图识别和查询改写保持 qwen-plus
```

### 4.2 API 兼容性

`qwen-max` 与 `qwen-plus` 使用相同的 `dashscope.Generation.call()` 接口,参数完全兼容:

```python
resp = dashscope.Generation.call(
    model=self.GENERATION_MODEL,  # 只改这个值
    prompt=prompt,
    max_tokens=2048,
    temperature=0.3,
    result_format="message",
)
```

### 4.3 注意事项

- `qwen-max` 的 max_tokens 上限可能不同,需确认是否支持 2048
- `qwen-max` 的 temperature 参数行为可能略有差异,建议先保持 0.3
- API 调用费用约为 qwen-plus 的 3-5 倍

## 5. 文件变更清单

| 文件 | 变更类型 | 变更内容 |
|------|----------|----------|
| `src/retrieval.py` | 修改 | EMBEDDING_MODEL, EMBEDDING_DIM 常量 |
| `src/retrieval.py` | 重写 | `_llm_rerank` 方法 |
| `src/retrieval.py` | 新增 | `_gte_rerank` 方法(批量重排) |
| `src/retrieval.py` | 新增 | `_fallback_rerank` 方法(回退排序) |
| `src/retrieval.py` | 修改 | GENERATION_MODEL 常量 |
| `src/ingestion.py` | 修改 | EMBEDDING_MODEL, EMBEDDING_DIM 常量 |
| `src/query_processor.py` | 不变 | MODEL_NAME 保持 qwen-plus |
| `app_streamlit.py` | 不变 | 无需修改 |
| `src/api_service.py` | 不变 | 无需修改 |
| `src/pdf_mineru.py` | 不变 | 无需修改 |
| `src/text_splitter.py` | 不变 | 无需修改 |

## 6. 版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | -- | 初始技术方案 |
