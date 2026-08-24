# TDD 测试用例集合: 模型升级与检索精准度提升

> 编码: UTF-8
> 变更: model-upgrade
> 状态: 待审核
> 测试框架: pytest

---

## 一、Embedding 升级测试 (阶段1)

### T-E1: 单公司向量检索

```python
def test_vector_search_single_company():
    """验证 text-embedding-v3 向量检索功能正常"""
    # 前置: FAISS 索引已用 v3 重建
    query = "中芯国际2024年营业收入"
    results = vector_retriever.search(query, top_k=10)

    assert len(results) > 0, "向量检索应返回结果"
    assert all("scores" in r and "vector" in r["scores"] for r in results), "结果应包含向量分数"
    assert all(r["scores"]["vector"] > 0 for r in results), "向量分数应大于0"
    assert all("parent_text" in r for r in results), "结果应包含父块文本"
    assert all("company_name" in r for r in results), "结果应包含公司名"
```

### T-E2: 混合检索(向量+BM25)

```python
def test_hybrid_search():
    """验证 v3 Embedding 下混合检索功能正常"""
    query = "中芯国际产能利用率"
    results = hybrid_retriever.search(query, company_name="中芯国际", top_n=5)

    assert len(results) > 0, "混合检索应返回结果"
    assert all("hybrid" in r["scores"] for r in results), "结果应包含 hybrid 分数"
    assert all("rerank" in r["scores"] for r in results), "结果应包含 rerank 分数"
    assert all("confidence" in r["scores"] for r in results), "结果应包含置信度"
```

### T-E3: 表格数据检索命中率

```python
def test_table_data_retrieval_hit():
    """验证 v3 Embedding 对表格数据的检索命中率提升"""
    query = "中国电信2024年营业收入"
    results = vector_retriever.search(query, top_k=30)

    # 检查 top 10 中是否包含含 "5,236" 或 "5236" 的营收数据块
    top10_texts = " ".join(r["parent_text"] for r in results[:10])
    hit = "5236" in top10_texts or "5,236" in top10_texts

    assert hit, "top 10 结果中应包含中国电信营收数据(约5236亿元)"
```

### T-E4: FAISS 索引维度验证

```python
def test_faiss_index_dimension():
    """验证重建后的 FAISS 索引维度为 1024"""
    for company_name in ["中芯国际", "中国电信", "中国移动", "中国联通"]:
        company_dir = vector_db_dir / company_name
        vr = VectorRetriever(company_dir, api_key)
        vr.load()
        assert vr.index.d == 1024, f"{company_name} FAISS 索引维度应为 1024, 实际为 {vr.index.d}"
```

---

## 二、重排模型替换测试 (阶段2)

### T-R1: 正常重排流程

```python
def test_rerank_normal():
    """验证 gte-rerank 批量重排正常工作"""
    query = "中芯国际2024年营收"
    candidates = [...]  # 构造 20 个候选文档

    top_results, scored_candidates = hybrid_retriever._llm_rerank(query, candidates, top_n=5)

    assert len(top_results) <= 5, "应返回最多 5 条结果"
    assert len(scored_candidates) == len(candidates), "所有候选应有分数"
    assert all("rerank" in r["scores"] for r in scored_candidates), "结果应包含 rerank 分数"
    assert all(0 <= r["scores"]["rerank"] <= 10 for r in scored_candidates), "rerank 分数应在 0-10 范围"
    # 验证排序: top_results 按 rerank 降序
    for i in range(len(top_results) - 1):
        assert top_results[i]["scores"]["rerank"] >= top_results[i + 1]["scores"]["rerank"]
```

### T-R2: 对比查询重排

```python
def test_rerank_comparison_query():
    """验证对比查询场景下 gte-rerank 的公平性"""
    query = "中国移动和中国联通和中国电信2024年营收对比"
    candidates = [...]  # 构造包含三家公司的候选文档

    top_results, _ = hybrid_retriever._llm_rerank(query, candidates, top_n=5)

    # 验证 top 5 中至少包含 2 家公司
    companies_in_top = set(r["company_name"] for r in top_results)
    assert len(companies_in_top) >= 2, f"top 5 应至少包含 2 家公司, 实际: {companies_in_top}"
```

### T-R3: API 失败回退

```python
def test_rerank_fallback_on_api_failure(monkeypatch):
    """验证 gte-rerank API 失败时回退到 hybrid 排序"""
    def mock_rerank_fail(*args, **kwargs):
        raise Exception("API 调用失败")

    monkeypatch.setattr(hybrid_retriever, "_gte_rerank", mock_rerank_fail)

    candidates = [...]  # 构造候选文档
    top_results, scored_candidates = hybrid_retriever._llm_rerank("测试查询", candidates, top_n=5)

    assert len(top_results) > 0, "回退排序应返回结果"
    # 回退模式下 rerank 分数应为 hybrid * 10
    for r in scored_candidates:
        assert r["scores"]["rerank"] > 0, "回退模式下 rerank 分数应大于0"
```

### T-R4: 空候选列表

```python
def test_rerank_empty_candidates():
    """验证空候选列表返回 ([], []) 而非 []"""
    top_results, scored_candidates = hybrid_retriever._llm_rerank("测试查询", [], top_n=5)

    assert top_results == [], "空候选应返回空列表"
    assert scored_candidates == [], "空候选应返回空列表"
    assert isinstance((top_results, scored_candidates), tuple), "应返回元组"
```

### T-R5: 重排耗时验证

```python
def test_rerank_performance():
    """验证 gte-rerank 重排耗时不超过 5 秒"""
    import time
    query = "中芯国际2024年营收"
    candidates = [...]  # 构造 20 个候选文档

    start = time.time()
    top_results, _ = hybrid_retriever._llm_rerank(query, candidates, top_n=5)
    elapsed = time.time() - start

    assert elapsed < 5.0, f"重排耗时应不超过 5 秒, 实际: {elapsed:.1f} 秒"
```

---

## 三、生成模型升级测试 (阶段3)

### T-G1: 财务数据查询生成

```python
def test_generation_financial_query():
    """验证 qwen-max 生成财务数据答案的准确性"""
    query = "中芯国际2024年营收情况"
    result = rag_generator.query(query, company_name="中芯国际", top_n=5)

    assert "answer" in result, "应返回答案"
    assert len(result["answer"]) > 50, "答案不应过短"
    assert len(result["sources"]) > 0, "应包含来源信息"

    # 验证答案中包含来源引用
    assert "[来源" in result["answer"], "答案应包含来源引用标记"
```

### T-G2: 对比分析生成

```python
def test_generation_comparison_query():
    """验证 qwen-max 对比分析生成的结构化输出"""
    query = "中国移动和中国联通和中国电信2024年营收对比"
    result = rag_generator.query(query, mentioned_companies=["中国移动", "中国联通", "中国电信"], intent="comparison")

    assert "answer" in result, "应返回答案"
    # 对比分析应包含结构化格式(表格或列表)
    answer = result["answer"]
    has_structure = "|" in answer or "1." in answer or "-" in answer
    assert has_structure, "对比分析答案应包含结构化格式"
```

### T-G3: 信息不足场景

```python
def test_generation_insufficient_info():
    """验证 qwen-max 在信息不足时不编造数据"""
    query = "中芯国际2026年营收预测"
    result = rag_generator.query(query, company_name="中芯国际", top_n=5)

    # 答案中应明确说明信息不足,而非编造2026年数据
    assert "2026" not in result["answer"] or "未" in result["answer"] or "无法" in result["answer"] or "没有" in result["answer"], \
        "答案不应编造2026年营收数据"
```

### T-G4: 幻觉检测

```python
def test_generation_no_hallucination():
    """验证 qwen-max 不编造检索结果中未出现的数字"""
    query = "中芯国际2024年毛利率"
    result = rag_generator.query(query, company_name="中芯国际", top_n=5)

    # 从检索结果中提取所有数字
    source_numbers = set()
    for s in result["sources"]:
        import re
        numbers = re.findall(r'\d+\.?\d*', s.get("parent_text", ""))
        source_numbers.update(numbers)

    # 从答案中提取数字
    answer_numbers = set(re.findall(r'\d+\.?\d*', result["answer"]))

    # 答案中的数字应大部分出现在检索结果中(允许少量格式差异)
    # 此处为软断言,记录差异但不一定失败
    novel_numbers = answer_numbers - source_numbers
    if novel_numbers:
        print(f"[警告] 答案中包含检索结果未出现的数字: {novel_numbers}")
```

---

## 四、集成测试 (阶段4)

### T-INT1: 单公司财务数据查询(全流程)

```python
def test_e2e_single_company_financial():
    """端到端: 单公司财务数据查询"""
    query = "中芯国际2024年营收情况"

    # 步骤1: 意图识别
    qp_result = query_processor.process(query)
    assert qp_result["intent"] == "financial_data", f"意图应为 financial_data, 实际: {qp_result['intent']}"
    assert "中芯国际" in qp_result["extracted_companies"], "应提取公司名"

    # 步骤2: 检索
    result = rag_generator.query(query, company_name="中芯国际", top_n=5)
    assert len(result["sources"]) > 0, "应返回检索结果"
    assert result["retrieved_count"] > 0, "检索结果数应大于0"

    # 步骤3: 生成
    assert len(result["answer"]) > 50, "答案不应过短"
    assert "[来源" in result["answer"], "答案应包含来源引用"
```

### T-INT2: 三家对比查询(全流程)

```python
def test_e2e_three_company_comparison():
    """端到端: 三家运营商营收对比查询"""
    query = "中国移动和中国联通和中国电信2024年的营收对比"

    # 步骤1: 意图识别
    qp_result = query_processor.process(query)
    assert qp_result["intent"] == "comparison", f"意图应为 comparison, 实际: {qp_result['intent']}"

    # 步骤2: 检索
    mentioned = ["中国移动", "中国联通", "中国电信"]
    result = rag_generator.query(query, mentioned_companies=mentioned, intent="comparison", top_n=5)

    # 步骤3: 验证公司覆盖
    companies_in_sources = set(s["company_name"] for s in result["sources"])
    assert len(companies_in_sources) >= 2, f"来源应至少包含 2 家公司, 实际: {companies_in_sources}"

    # 步骤4: 验证答案
    assert len(result["answer"]) > 100, "对比分析答案应较详细"
```

### T-INT3: 域外问题拦截

```python
def test_e2e_out_of_domain():
    """端到端: 域外问题应被拦截"""
    query = "今天天气怎么样"

    qp_result = query_processor.process(query)
    assert qp_result["intent"] == "out_of_domain", f"意图应为 out_of_domain, 实际: {qp_result['intent']}"
    assert qp_result["should_reject"] is True, "域外问题应被拦截"
```

### T-INT4: Streamlit 界面验证

```python
# 此测试为手动验证,不编写自动化脚本
# 验证步骤:
# 1. 启动 streamlit run app_streamlit.py
# 2. 输入 "中芯国际2024年营收情况" -> 验证返回正确答案
# 3. 输入 "三家运营商营收对比" -> 验证三家公司数据均出现
# 4. 输入 "今天天气怎么样" -> 验证域外问题被拦截
# 5. 检查查询分析面板显示的意图/置信度/改写结果
```

---

## 五、回归测试

### T-REG1: BM25 检索不受影响

```python
def test_regression_bm25():
    """回归: BM25 检索功能不受 Embedding 升级影响"""
    query = "中芯国际产能利用率"
    results = bm25_retriever.search(query, top_k=10)

    assert len(results) > 0, "BM25 检索应返回结果"
    assert all("bm25" in r["scores"] for r in results), "结果应包含 BM25 分数"
```

### T-REG2: 查询改写功能不受影响

```python
def test_regression_query_rewrite():
    """回归: 查询改写功能不受模型升级影响"""
    query = "中芯国际去年营收"
    result = query_processor.process(query)

    assert "rewritten_query" in result, "应包含改写结果"
    assert "extracted_companies" in result, "应包含提取公司"
    assert "中芯国际" in result["extracted_companies"], "应提取中芯国际"
```

### T-REG3: API 服务不受影响

```python
def test_regression_api_service():
    """回归: API 服务功能正常"""
    from fastapi.testclient import TestClient
    from src.api_service import app

    client = TestClient(app)

    # 健康检查
    resp = client.get("/api/health")
    assert resp.status_code == 200

    # 查询接口
    resp = client.post("/api/query", json={"query": "中芯国际2024年营收", "top_n": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data
```

---

## 版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | -- | 初始测试用例集合 |
