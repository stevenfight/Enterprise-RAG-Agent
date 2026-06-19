# -*- coding: utf-8 -*-
"""集成验证脚本: 测试模型升级后的完整 RAG 流程"""
import sys
import os
import ssl
import time
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pathlib import Path
from retrieval import RAGGenerator, HybridRetriever, VectorRetriever
from query_processor import QueryProcessor

project_root = Path(__file__).resolve().parent.parent
vector_db_dir = project_root / "data" / "stock_data" / "databases" / "vector_dbs"

print("=" * 60)
print("集成验证: 模型升级后完整 RAG 流程")
print("=" * 60)

# T-E4: FAISS 索引维度验证
print("\n--- T-E4: FAISS 索引维度验证 ---")
from retrieval import get_api_key
api_key = get_api_key()
for cn in ["中芯国际", "中国电信", "中国移动", "中国联通"]:
    company_dir = vector_db_dir / cn
    vr = VectorRetriever(company_dir, api_key)
    vr.load()
    status = "PASS" if vr.index.d == 1024 else f"FAIL (dim={vr.index.d})"
    print(f"  {cn}: 维度={vr.index.d} [{status}]")

# T-INT1: 单公司财务数据查询
print("\n--- T-INT1: 单公司财务数据查询 ---")
rag = RAGGenerator(str(vector_db_dir))
qp = QueryProcessor()

query1 = "中芯国际2024年营收情况"
t0 = time.time()
qp_result = qp.process(query1)
print(f"  意图: {qp_result['intent']}, 置信度: {qp_result['intent_confidence']}")
print(f"  提取公司: {qp_result.get('extracted_companies', [])}")

result1 = rag.query(query1, company_name="中芯国际", top_n=5)
elapsed1 = time.time() - t0
print(f"  耗时: {elapsed1:.1f}s")
print(f"  检索结果数: {result1['retrieved_count']}")
print(f"  来源数: {len(result1['sources'])}")
print(f"  答案前200字: {result1['answer'][:200]}")
has_ref = "[来源" in result1["answer"]
print(f"  包含来源引用: {has_ref} [{'PASS' if has_ref else 'FAIL'}]")

# T-INT2: 三家对比查询
print("\n--- T-INT2: 三家对比查询 ---")
query2 = "中国移动和中国联通和中国电信2024年的营收对比"
t0 = time.time()
result2 = rag.query(query2, mentioned_companies=["中国移动", "中国联通", "中国电信"], intent="comparison", top_n=5)
elapsed2 = time.time() - t0
companies_in_sources = set(s["company_name"] for s in result2["sources"])
print(f"  耗时: {elapsed2:.1f}s")
print(f"  来源公司: {companies_in_sources}")
print(f"  公司覆盖数: {len(companies_in_sources)} [{'PASS' if len(companies_in_sources) >= 2 else 'FAIL'}]")
print(f"  答案前300字: {result2['answer'][:300]}")

# T-INT3: 域外问题拦截
print("\n--- T-INT3: 域外问题拦截 ---")
query3 = "今天天气怎么样"
qp_result3 = qp.process(query3)
print(f"  意图: {qp_result3['intent']}")
print(f"  拦截: {qp_result3.get('should_reject', False)} [{'PASS' if qp_result3['intent'] == 'out_of_domain' else 'FAIL'}]")

# 重排耗时验证
print("\n--- T-R5: 重排耗时验证 ---")
print(f"  单公司查询总耗时: {elapsed1:.1f}s (含检索+重排+生成)")
print(f"  对比查询总耗时: {elapsed2:.1f}s (含检索+重排+生成)")

print("\n" + "=" * 60)
print("集成验证完成!")
print("=" * 60)
