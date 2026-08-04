# -*- coding: utf-8 -*-
"""
运行时间诊断脚本 - 全链路耗时拆解
编码: UTF-8
用途: 对 RAG + Agent 全链路各环节进行独立计时，输出耗时构成报告
用法: cd 项目根目录 && python tests/diagnose_timing.py
"""

import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.query_processor import QueryProcessor
from src.retrieval import HybridRetriever, RAGGenerator
from src.retrieval import VECTOR_TOP_K, BM25_TOP_K, HYBRID_TOP_K, RERANK_TOP_N
from src.utils import get_api_key

# ---------- 配置 ----------
VECTOR_DB_DIR = PROJECT_ROOT / "data" / "stock_data" / "databases" / "vector_dbs"

TEST_QUERIES = [
    ("中国移动 2024 年营业收入是多少", "中国移动"),
    ("5G 业务发展怎么样", "中国移动"),
    ("中国移动和中国电信 2024 年营收对比", None),
]

WARMUP = 1   # 预热轮数（不计入统计）
ROUNDS = 2   # 测量轮数


# ---------- 计时工具 ----------
class Timing:
    def __init__(self, name):
        self.name = name
        self.vals = []
        self.extras = []

    def record(self, ms, extra=""):
        self.vals.append(ms)
        if extra:
            self.extras.append(extra)

    @property
    def avg(self):
        return sum(self.vals) / len(self.vals) if self.vals else 0

    @property
    def min(self):
        return min(self.vals) if self.vals else 0

    @property
    def max(self):
        return max(self.vals) if self.vals else 0


# ---------- 单查询计时 ----------
def time_one_query(retriever: HybridRetriever, generator: RAGGenerator,
                   processor: QueryProcessor, query_text: str, company: str):
    """对一条查询做 ROUNDS 次计时，返回各环节 Timing 字典"""

    timings = {}

    # --- 1) 意图识别 ---
    t = Timing("意图识别")
    for r in range(WARMUP + ROUNDS):
        t0 = time.time()
        result = processor.process(query_text)
        ms = (time.time() - t0) * 1000
        intent = result.get("intent", "?")
        if r >= WARMUP:
            t.record(ms, f"intent={intent}")
        else:
            time.sleep(0.05)
    timings["意图识别"] = t
    intent = t.extras[0].split("=")[1] if t.extras else "general"

    # --- 2) Embedding 生成 ---
    cn0 = list(retriever._company_registry["companies"].keys())[0]
    vr, _ = retriever._get_retrievers(cn0)
    t = Timing("Embedding生成")
    for r in range(WARMUP + ROUNDS):
        t0 = time.time()
        emb = vr._get_query_embedding(query_text)
        ms = (time.time() - t0) * 1000
        dim = len(emb) if emb else 0
        if r >= WARMUP:
            t.record(ms, f"dim={dim}")
    timings["Embedding生成"] = t

    # --- 3) 向量检索 (API+FAISS) ---
    vr, _ = retriever._get_retrievers(company)
    t = Timing("向量检索")
    for r in range(WARMUP + ROUNDS):
        t0 = time.time()
        vec_res = vr.search(query_text, top_k=VECTOR_TOP_K)
        ms = (time.time() - t0) * 1000
        if r >= WARMUP:
            t.record(ms, f"hits={len(vec_res)}")
    timings["向量检索"] = t

    # --- 4) BM25 检索 ---
    _, br = retriever._get_retrievers(company)
    t = Timing("BM25检索")
    for r in range(WARMUP + ROUNDS):
        t0 = time.time()
        bm25_res = br.search(query_text, top_k=BM25_TOP_K)
        ms = (time.time() - t0) * 1000
        if r >= WARMUP:
            t.record(ms, f"hits={len(bm25_res)}")
    timings["BM25检索"] = t

    # --- 5) 归一化 + 合并 + 加权融合 ---
    vec_res = vr.search(query_text, top_k=VECTOR_TOP_K)
    bm25_res = br.search(query_text, top_k=BM25_TOP_K)
    t = Timing("合并+融合")
    for _ in range(ROUNDS):
        t0 = time.time()
        merged = retriever._merge_results(vec_res, bm25_res, intent=intent)
        ms = (time.time() - t0) * 1000
        t.record(ms, f"merged={len(merged)}")
    timings["合并+融合"] = t
    merged_count = len(merged)

    # --- 6) Rerank 重排 ---
    sorted_list = sorted(merged, key=lambda x: x.get("scores", {}).get("hybrid", 0), reverse=True)
    candidates = sorted_list[:HYBRID_TOP_K]
    t = Timing("Rerank重排")
    for _ in range(ROUNDS):
        t0 = time.time()
        try:
            reranked, _ = retriever._gte_rerank(query_text, candidates, top_n=RERANK_TOP_N)
            ok = f"reranked={len(reranked)}"
        except Exception as e:
            ok = f"err={str(e)[:30]}"
        ms = (time.time() - t0) * 1000
        t.record(ms, ok)
    timings["Rerank重排"] = t

    # --- 7) 完整检索流水线 ---
    t = Timing("检索流水线合计")
    for _ in range(ROUNDS):
        t0 = time.time()
        results = retriever.search(query_text, company_name=company, intent=intent)
        ms = (time.time() - t0) * 1000
        t.record(ms, f"results={len(results)}")
    timings["检索流水线合计"] = t

    # --- 8) LLM 生成 ---
    results = retriever.search(query_text, company_name=company, intent=intent)
    t = Timing("LLM生成答案")
    for _ in range(ROUNDS):
        ctx, _ = generator._build_context(results)
        prompt = generator._build_prompt(query_text, ctx)
        t0 = time.time()
        answer = generator._generate_answer(prompt)
        ms = (time.time() - t0) * 1000
        t.record(ms, f"len={len(answer)}")
    timings["LLM生成答案"] = t

    # --- 9) 完整 RAG 端到端 ---
    t = Timing("RAG端到端")
    for _ in range(ROUNDS):
        t0 = time.time()
        result = generator.query(query_text, company_name=company, intent=intent)
        ms = (time.time() - t0) * 1000
        t.record(ms, f"sources={len(result.get('sources',[]))}")
    timings["RAG端到端"] = t

    return timings, merged_count


# ---------- 输出 ----------

def print_report(query_text, timings, merged_count):
    s = []
    total = 0
    for label in ["意图识别", "Embedding生成", "向量检索", "BM25检索",
                  "合并+融合", "Rerank重排", "检索流水线合计", "LLM生成答案", "RAG端到端"]:
        t = timings.get(label)
        if not t:
            continue
        s.append(f"  {label:<20s}  avg={t.avg:>7.0f}ms  [{t.min:.0f}-{t.max:.0f}]  ({t.extras[0] if t.extras else ''})")
        total += t.avg
    s.append(f"  {'─'*55}")
    s.append(f"  {'RAG端到端合计':20s}  avg={timings['RAG端到端'].avg:>7.0f}ms")
    return s


# ---------- main ----------

def main():
    if not VECTOR_DB_DIR.exists():
        print(f"[错误] 向量数据库目录不存在: {VECTOR_DB_DIR}")
        return

    api_key = get_api_key()
    print(f"向量库: {VECTOR_DB_DIR}")
    print(f"预热{ WARMUP}轮 + 测量{ROUNDS}轮 = {len(TEST_QUERIES)} 条查询\n")

    t0 = time.time()
    retriever = HybridRetriever(VECTOR_DB_DIR, api_key)
    generator = RAGGenerator(VECTOR_DB_DIR, api_key)
    processor = QueryProcessor(api_key)
    print(f"组件初始化: {(time.time()-t0)*1000:.0f}ms\n")

    retriever._load_company_registry()
    companies = list(retriever._company_registry["companies"].keys())
    print(f"可用公司: {companies}\n")

    all_timings = []

    for query_text, specified_company in TEST_QUERIES:
        company = specified_company or companies[0]
        print(f"{'='*60}")
        print(f"  查询: {query_text}")
        print(f"  公司: {company}")
        print(f"{'='*60}")

        timings, merged_count = time_one_query(retriever, generator, processor,
                                                query_text, company)
        all_timings.append((query_text, company, timings))

        lines = print_report(query_text, timings, merged_count)
        for ln in lines:
            print(ln)
        print()

    # ---- 跨查询汇总 ----
    print(f"{'='*60}")
    print(f"  跨查询汇总 (平均值)")
    print(f"{'='*60}")
    labels = ["意图识别", "Embedding生成", "向量检索", "BM25检索",
              "合并+融合", "Rerank重排", "检索流水线合计", "LLM生成答案", "RAG端到端"]
    for label in labels:
        all_vals = []
        for _, _, t in all_timings:
            if label in t:
                all_vals.extend(t[label].vals)
        if all_vals:
            avg = sum(all_vals) / len(all_vals)
            print(f"  {label:<20s}  avg={avg:>7.0f}ms  min={min(all_vals):.0f}ms  max={max(all_vals):.0f}ms  n={len(all_vals)}")

    print(f"\n诊断完成。")


if __name__ == "__main__":
    main()
