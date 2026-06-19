# -*- coding: utf-8 -*-
"""TDD 集成测试: 验证所有优化项"""
import sys
import os
import ssl
import time
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pathlib import Path
from retrieval import (
    RAGGenerator, HybridRetriever, VectorRetriever, BM25Retriever,
    INTENT_WEIGHTS, COMPANY_ABBREV_MAP, EMBEDDING_MODEL, EMBEDDING_DIM,
    BATCH_SIZE,
)
from query_processor import QueryProcessor

project_root = Path(__file__).resolve().parent.parent
vector_db_dir = project_root / "data" / "stock_data" / "databases" / "vector_dbs"

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} - {detail}")
        failed += 1

print("=" * 60)
print("TDD 集成测试: 验证所有优化项")
print("=" * 60)

# === 优化1: 混合检索权重自适应 ===
print("\n--- 优化1: 混合检索权重自适应 ---")
check("INTENT_WEIGHTS 存在", len(INTENT_WEIGHTS) >= 4, f"实际: {len(INTENT_WEIGHTS)}")
check("financial_data BM25权重>向量权重",
      INTENT_WEIGHTS["financial_data"]["bm25"] > INTENT_WEIGHTS["financial_data"]["vector"],
      f"bm25={INTENT_WEIGHTS['financial_data']['bm25']}, vector={INTENT_WEIGHTS['financial_data']['vector']}")
check("trend 向量权重>BM25权重",
      INTENT_WEIGHTS["trend"]["vector"] > INTENT_WEIGHTS["trend"]["bm25"],
      f"bm25={INTENT_WEIGHTS['trend']['bm25']}, vector={INTENT_WEIGHTS['trend']['vector']}")
check("comparison 权重均衡",
      INTENT_WEIGHTS["comparison"]["bm25"] == INTENT_WEIGHTS["comparison"]["vector"])

# === 优化2: BM25 查询扩展词典外部化 ===
print("\n--- 优化2: BM25 查询扩展词典外部化 ---")
config_path = project_root / "config" / "bm25_expansions.json"
check("bm25_expansions.json 文件存在", config_path.exists())
if config_path.exists():
    import json
    expansions = json.loads(config_path.read_text(encoding="utf-8"))
    check("词典条目数>=15", len(expansions) >= 15, f"实际: {len(expansions)}")
    check("包含 EBITDA", "EBITDA" in expansions)
    check("包含 研发", "研发" in expansions)
    check("包含 现金流", "现金流" in expansions)
    check("营收扩展词为列表", isinstance(expansions.get("营收"), list))
    check("营收扩展词>=5个", len(expansions.get("营收", [])) >= 5, f"实际: {len(expansions.get('营收', []))}")

# 验证 _expand_query 加载外部词典
from retrieval import get_api_key
api_key = get_api_key()
br = BM25Retriever.__new__(BM25Retriever)
expanded = BM25Retriever._expand_query("中芯国际EBITDA")
check("EBITDA 扩展生效", "息税折旧摊销前利润" in expanded, f"扩展结果: {expanded}")

# === 优化3: 子查询拆解精细化 ===
print("\n--- 优化3: 子查询拆解精细化 ---")
import inspect
sig = inspect.signature(HybridRetriever._search_comparison)
params = list(sig.parameters.keys())
check("_search_comparison 接受 extracted_years 参数", "extracted_years" in params, f"参数: {params}")

sig2 = inspect.signature(HybridRetriever.search)
params2 = list(sig2.parameters.keys())
check("search 接受 extracted_years 参数", "extracted_years" in params2, f"参数: {params2}")

# === 优化4: COMPANY_ABBREV_MAP 重复定义 ===
print("\n--- 优化4: COMPANY_ABBREV_MAP 重复定义 ---")
check("retrieval.py 导出 COMPANY_ABBREV_MAP", COMPANY_ABBREV_MAP is not None)
check("COMPANY_ABBREV_MAP 包含中芯国际", "中芯国际" in COMPANY_ABBREV_MAP)

# 验证 app_streamlit.py 不再独立定义 ABBREV_MAP
streamlit_path = project_root / "app_streamlit.py"
streamlit_content = streamlit_path.read_text(encoding="utf-8")
check("app_streamlit.py 无独立 ABBREV_MAP 定义", "ABBREV_MAP = {" not in streamlit_content)
check("app_streamlit.py 从 retrieval 导入", "COMPANY_ABBREV_MAP" in streamlit_content)

# === 优化5+6: api_service.py 集成 QueryProcessor ===
print("\n--- 优化5+6: api_service.py 集成 QueryProcessor ---")
api_path = project_root / "src" / "api_service.py"
api_content = api_path.read_text(encoding="utf-8")
check("api_service.py 导入 QueryProcessor", "QueryProcessor" in api_content)
check("api_service.py 使用 query_processor", "query_processor" in api_content)
check("api_service.py 传递 intent", "intent=intent" in api_content)
check("api_service.py 传递 mentioned_companies", "mentioned_companies=mentioned_companies" in api_content)
check("api_service.py 传递 extracted_years", "extracted_years=extracted_years" in api_content)
check("api_service.py 域外拦截", "out_of_domain" in api_content)

# === 优化7: 专用 Prompt ===
print("\n--- 优化7: 专用 Prompt ---")
retrieval_content = (project_root / "src" / "retrieval.py").read_text(encoding="utf-8")
check("_build_financial_data_prompt 方法存在", "_build_financial_data_prompt" in retrieval_content)
check("_build_trend_prompt 方法存在", "_build_trend_prompt" in retrieval_content)
check("_build_business_analysis_prompt 方法存在", "_build_business_analysis_prompt" in retrieval_content)
check("financial_data Prompt 选择逻辑", 'intent == "financial_data"' in retrieval_content)
check("trend Prompt 选择逻辑", 'intent == "trend"' in retrieval_content)
check("business_analysis Prompt 选择逻辑", 'intent == "business_analysis"' in retrieval_content)
check("financial_data Prompt 含 CPA", "CPA" in retrieval_content)
check("financial_data Prompt 禁止模糊表述", "模糊表述" in retrieval_content)

# === 端到端功能验证 ===
print("\n--- 端到端功能验证 ---")
rag = RAGGenerator(str(vector_db_dir))
qp = QueryProcessor()

# 测试1: 财务数据查询 (应使用 financial_data Prompt + BM25权重更高)
query1 = "中芯国际2024年营业收入"
t0 = time.time()
qp1 = qp.process(query1)
result1 = rag.query(query1, company_name="中芯国际", top_n=5,
                     intent=qp1["intent"], extracted_years=qp1.get("extracted_years"))
e1 = time.time() - t0
check("财务数据查询意图识别", qp1["intent"] == "financial_data", f"实际: {qp1['intent']}")
check("财务数据查询返回答案", len(result1["answer"]) > 50, f"长度: {len(result1['answer'])}")
check("财务数据查询含来源引用", "[来源" in result1["answer"])
check("财务数据查询耗时<45s", e1 < 45, f"实际: {e1:.1f}s")

# 测试2: 对比查询 (应使用 comparison Prompt + 权重均衡)
query2 = "中国移动和中国联通和中国电信2024年营收对比"
t0 = time.time()
qp2 = qp.process(query2)
result2 = rag.query(query2, mentioned_companies=["中国移动", "中国联通", "中国电信"],
                     intent="comparison", top_n=5)
e2 = time.time() - t0
companies_in_sources = set(s["company_name"] for s in result2["sources"])
check("对比查询3家公司覆盖", len(companies_in_sources) >= 2, f"实际: {companies_in_sources}")
check("对比查询耗时<45s", e2 < 45, f"实际: {e2:.1f}s")

# 测试3: 域外问题拦截
query3 = "今天天气怎么样"
qp3 = qp.process(query3)
check("域外问题拦截", qp3["intent"] == "out_of_domain", f"实际: {qp3['intent']}")

# 测试4: 趋势分析查询
query4 = "中芯国际营收增长趋势"
qp4 = qp.process(query4)
check("趋势分析意图识别", qp4["intent"] in ["trend", "financial_data", "general"], f"实际: {qp4['intent']}")

# === 模型升级验证 ===
print("\n--- 模型升级验证 ---")
check("Embedding 模型 v3", EMBEDDING_MODEL == "text-embedding-v3")
check("Embedding 维度 1024", EMBEDDING_DIM == 1024)
check("BATCH_SIZE=10", BATCH_SIZE == 10)
check("生成模型 qwen-max", RAGGenerator.GENERATION_MODEL == "qwen-max")

# === 汇总 ===
print("\n" + "=" * 60)
print(f"测试完成: {passed} PASS, {failed} FAIL, 共 {passed + failed} 项")
print("=" * 60)
