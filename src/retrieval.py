"""
混合检索与 RAG 生成模块

实现 Small-to-Big 检索策略 + RAG 答案生成：
  1. 向量检索（FAISS + DashScope text-embedding-v3）
  2. BM25 关键词检索（jieba 分词 + rank_bm25）
  3. 混合检索：0.5*BM25 + 0.5*向量，归一化后加权融合
  4. gte-rerank-v2 重排（DashScope 专用重排模型批量评分）
  5. RAG 生成（检索结果 + 来源信息送入 qwen-max 生成最终答案）

检索结果包含：来源文件、页码、公司名、各项打分、置信度
生成结果包含：答案正文、引用来源、置信度汇总
"""

import json
import logging
import os
import pickle
import sys
import tempfile
import time
from pathlib import Path

import faiss
import jieba
import numpy as np
import tiktoken
from rank_bm25 import BM25Okapi

from utils import get_api_key

logger = logging.getLogger("retrieval")
logger.setLevel(logging.INFO)

if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)

ENCODING = tiktoken.get_encoding("cl100k_base")
MAX_INPUT_TOKENS = 2048

EMBEDDING_MODEL = "text-embedding-v3"
EMBEDDING_DIM = 1024
BATCH_SIZE = 10

BM25_WEIGHT = 0.5
VECTOR_WEIGHT = 0.5

INTENT_WEIGHTS = {
    "financial_data": {"bm25": 0.6, "vector": 0.4},
    "comparison": {"bm25": 0.5, "vector": 0.5},
    "business_analysis": {"bm25": 0.4, "vector": 0.6},
    "trend": {"bm25": 0.3, "vector": 0.7},
    "general": {"bm25": 0.5, "vector": 0.5},
}

BM25_TOP_K = 30
VECTOR_TOP_K = 30
HYBRID_TOP_K = 20
RERANK_TOP_N = 5

COMPANY_ABBREV_MAP = {
    "中芯国际": ["中芯"],
    "中国电信": ["电信"],
    "中国移动": ["移动"],
    "中国联通": ["联通"],
}


def truncate_text_to_tokens(text, max_tokens=MAX_INPUT_TOKENS):
    tokens = ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = ENCODING.decode(tokens[:max_tokens])
    return truncated


def preprocess_table_text(text):
    import re
    if not re.search(r'\|[\s\-:]+\|', text):
        return text
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^[\|\s\-:]+$', stripped):
            continue
        if '|' in stripped:
            cleaned = re.sub(r'\|', ' ', stripped)
            result.append(cleaned)
        else:
            result.append(line)
    return '\n'.join(result)


class VectorRetriever:
    """向量检索器：FAISS + DashScope Embedding"""

    def __init__(self, company_dir, api_key):
        self.company_dir = Path(company_dir)
        self.api_key = api_key
        self.index = None
        self.metadata = None
        self.parent_texts = None
        self._loaded = False

        logger.info("[VectorRetriever] 初始化，公司目录: %s", self.company_dir)

    def load(self):
        faiss_path = self.company_dir / "index.faiss"
        metadata_path = self.company_dir / "metadata.json"
        parent_texts_path = self.company_dir / "parent_texts.json"

        if not faiss_path.exists():
            logger.error("[VectorRetriever] FAISS 索引文件不存在: %s", faiss_path)
            raise FileNotFoundError(f"FAISS 索引文件不存在: {faiss_path}")

        logger.info("[VectorRetriever] 开始加载 FAISS 索引: %s（中文路径兼容中转）", faiss_path)
        import shutil
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_faiss = os.path.join(tmp_dir, "index.faiss")
            shutil.copy2(str(faiss_path), tmp_faiss)
            self.index = faiss.read_index(tmp_faiss)
        logger.info("[VectorRetriever] FAISS 索引加载完成，向量数: %d，维度: %d",
                     self.index.ntotal, self.index.d)

        logger.info("[VectorRetriever] 开始加载元数据: %s", metadata_path)
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        logger.info("[VectorRetriever] 元数据加载完成，子块数: %d", len(self.metadata))

        logger.info("[VectorRetriever] 开始加载父块文本: %s", parent_texts_path)
        self.parent_texts = json.loads(parent_texts_path.read_text(encoding="utf-8"))
        logger.info("[VectorRetriever] 父块文本加载完成，父块数: %d", len(self.parent_texts))

        self._loaded = True
        logger.info("[VectorRetriever] 全部数据加载完成")

    def _get_query_embedding(self, query):
        import dashscope
        dashscope.api_key = self.api_key

        processed = preprocess_table_text(query)
        truncated = truncate_text_to_tokens(processed)
        logger.info("[VectorRetriever] 查询文本: '%s'（截断后 %d 字符）",
                     query[:50] + "..." if len(query) > 50 else query, len(truncated))

        resp = dashscope.TextEmbedding.call(
            model=EMBEDDING_MODEL,
            input=[truncated],
            timeout=30,
        )

        if resp.status_code != 200:
            logger.error("[VectorRetriever] Embedding API 调用失败: %s - %s",
                         resp.status_code, resp.message)
            raise Exception(f"Embedding API 调用失败: {resp.status_code} - {resp.message}")

        embedding = resp.output["embeddings"][0]["embedding"]
        logger.info("[VectorRetriever] 查询 Embedding 获取成功，维度: %d", len(embedding))
        return embedding

    def search(self, query, top_k=VECTOR_TOP_K):
        if not self._loaded:
            self.load()

        logger.info("[VectorRetriever] 开始向量检索，查询: '%s'，top_k: %d",
                     query[:80] + "..." if len(query) > 80 else query, top_k)

        query_embedding = self._get_query_embedding(query)
        query_vec = np.array([query_embedding], dtype=np.float32)
        norms = np.linalg.norm(query_vec, axis=1, keepdims=True)
        norms[norms == 0] = 1
        query_vec = query_vec / norms

        scores, indices = self.index.search(query_vec, top_k)

        results = []
        for i in range(top_k):
            idx = int(indices[0][i])
            score = float(scores[0][i])
            if idx < 0 or idx >= len(self.metadata):
                logger.warning("[VectorRetriever] 跳过无效索引: %d（元数据总数: %d）",
                               idx, len(self.metadata))
                continue

            meta = self.metadata[idx]
            parent_key = meta["parent_key"]
            parent_text = self.parent_texts.get(parent_key, "")

            if not parent_text:
                logger.warning("[VectorRetriever] 父块文本为空，parent_key: %s", parent_key)

            results.append({
                "parent_text": parent_text,
                "source_file": meta["source_file"],
                "pages": meta.get("pages", []),
                "company_name": meta["company_name"],
                "child_id": meta["child_id"],
                "parent_key": parent_key,
                "scores": {
                    "vector": round(score, 4),
                },
            })

        logger.info("[VectorRetriever] 向量检索完成，返回 %d 条结果", len(results))
        for i, r in enumerate(results[:5]):
            logger.info("[VectorRetriever]   #%d 向量分: %.4f | 来源: %s | 页码: %s",
                         i + 1, r["scores"]["vector"], r["source_file"], r["pages"])

        return results


class BM25Retriever:
    """BM25 关键词检索器：jieba 分词 + rank_bm25"""

    def __init__(self, company_dir):
        self.company_dir = Path(company_dir)
        self.bm25 = None
        self.metadata = None
        self.parent_texts = None
        self._loaded = False

        logger.info("[BM25Retriever] 初始化，公司目录: %s", self.company_dir)

    def load(self):
        dict_path = Path(__file__).resolve().parent.parent / "config" / "financial_dict.txt"
        jieba.load_userdict(str(dict_path))

        bm25_path = self.company_dir / "bm25_index.pkl"
        metadata_path = self.company_dir / "metadata.json"
        parent_texts_path = self.company_dir / "parent_texts.json"

        if not bm25_path.exists():
            logger.error("[BM25Retriever] BM25 索引文件不存在: %s", bm25_path)
            raise FileNotFoundError(f"BM25 索引文件不存在: {bm25_path}")

        logger.info("[BM25Retriever] 开始加载 BM25 索引: %s", bm25_path)
        with open(str(bm25_path), "rb") as f:
            self.bm25 = pickle.load(f)
        logger.info("[BM25Retriever] BM25 索引加载完成，语料库大小: %d", self.bm25.corpus_size)

        logger.info("[BM25Retriever] 开始加载元数据: %s", metadata_path)
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        logger.info("[BM25Retriever] 元数据加载完成，子块数: %d", len(self.metadata))

        logger.info("[BM25Retriever] 开始加载父块文本: %s", parent_texts_path)
        self.parent_texts = json.loads(parent_texts_path.read_text(encoding="utf-8"))
        logger.info("[BM25Retriever] 父块文本加载完成，父块数: %d", len(self.parent_texts))

        self._loaded = True
        logger.info("[BM25Retriever] 全部数据加载完成")

    @staticmethod
    def _load_expansions():
        expansions_path = Path(__file__).resolve().parent.parent / "config" / "bm25_expansions.json"
        if expansions_path.exists():
            try:
                return json.loads(expansions_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("[BM25Retriever] 加载扩展词典失败: %s，使用内置词典", str(e))
        return {
            "营收": "营收 营业收入 收入",
            "收入": "收入 营业收入 营收",
            "利润": "利润 净利润 归属母公司净利润",
            "增长": "增长 同比增长 增速",
            "对比": "对比 比较 对比分析",
            "产能": "产能 产能利用率 产能利用",
        }

    @staticmethod
    def _expand_query(query):
        expansions_dict = BM25Retriever._load_expansions()
        parts = query
        # 按 key 长度降序排列，优先匹配长 key（如"营收对比"优先于"营收"）
        sorted_keys = sorted(expansions_dict.keys(), key=len, reverse=True)
        expanded_regions = []  # 记录已扩展的区间，防止子串被重复扩展
        for key in sorted_keys:
            if key not in parts:
                continue
            expanded_list = expansions_dict[key]
            if isinstance(expanded_list, list):
                expanded = " ".join(expanded_list)
            else:
                expanded = expanded_list
            if expanded in parts:
                continue
            # 检查 key 是否在已扩展区间内，避免重复扩展
            idx = parts.find(key)
            while idx != -1:
                # 检查此位置是否已被之前的扩展覆盖
                in_expanded = False
                for start, end in expanded_regions:
                    if start <= idx < end:
                        in_expanded = True
                        break
                if not in_expanded:
                    parts = parts[:idx] + expanded + parts[idx + len(key):]
                    # 记录扩展后的区间
                    expanded_regions.append((idx, idx + len(expanded)))
                    logger.info("[BM25Retriever] 查询扩展: '%s' -> '%s'", key, expanded)
                    # 重新搜索（因为字符串已变化）
                    idx = parts.find(key, idx + len(expanded))
                else:
                    idx = parts.find(key, idx + 1)
        return parts

    def search(self, query, top_k=BM25_TOP_K):
        if not self._loaded:
            self.load()

        logger.info("[BM25Retriever] 开始 BM25 检索，查询: '%s'，top_k: %d",
                     query[:80] + "..." if len(query) > 80 else query, top_k)

        expanded_query = self._expand_query(query)
        # 确保查询分词时财务词典已加载
        dict_path = Path(__file__).resolve().parent.parent / "config" / "financial_dict.txt"
        jieba.load_userdict(str(dict_path))
        tokenized_query_raw = list(jieba.cut(expanded_query))
        # 分词后去重：避免扩展导致重复词，使 BM25 分数失真
        seen = set()
        tokenized_query = []
        for t in tokenized_query_raw:
            t_stripped = t.strip()
            if t_stripped and t_stripped not in seen:
                seen.add(t_stripped)
                tokenized_query.append(t)
        if len(tokenized_query) != len(tokenized_query_raw):
            logger.info("[BM25Retriever] 分词去重: %d -> %d tokens", len(tokenized_query_raw), len(tokenized_query))
        logger.info("[BM25Retriever] 查询分词结果: %s",
                     " ".join(tokenized_query[:20]) + "..." if len(tokenized_query) > 20
                     else " ".join(tokenized_query))

        bm25_scores = self.bm25.get_scores(tokenized_query)
        logger.info("[BM25Retriever] BM25 原始分数范围: [%.4f, %.4f]",
                     float(bm25_scores.min()), float(bm25_scores.max()))

        top_indices = np.argsort(bm25_scores)[::-1][:top_k * 3]  # 多取一些，因为同一父块有多个子块

        results = []
        seen_parent_keys = set()
        for idx in top_indices:
            idx = int(idx)
            score = float(bm25_scores[idx])
            if score <= 0:
                continue

            if idx >= len(self.metadata):
                logger.warning("[BM25Retriever] 跳过无效索引: %d（元数据总数: %d）",
                               idx, len(self.metadata))
                continue

            meta = self.metadata[idx]
            parent_key = meta["parent_key"]
            parent_text = self.parent_texts.get(parent_key, "")

            if not parent_text:
                logger.warning("[BM25Retriever] 父块文本为空，parent_key: %s", parent_key)

            # 按 parent_key 去重，只保留每个父块的最高分
            if parent_key in seen_parent_keys:
                continue
            seen_parent_keys.add(parent_key)

            results.append({
                "parent_text": parent_text,
                "source_file": meta["source_file"],
                "pages": meta.get("pages", []),
                "company_name": meta["company_name"],
                "child_id": meta["child_id"],
                "parent_key": parent_key,
                "scores": {
                    "bm25": round(score, 4),
                },
            })

            if len(results) >= top_k:
                break

        logger.info("[BM25Retriever] BM25 检索完成，返回 %d 条结果", len(results))
        for i, r in enumerate(results[:5]):
            logger.info("[BM25Retriever]   #%d BM25分: %.4f | pk: %s | 来源: %s | 页码: %s",
                         i + 1, r["scores"]["bm25"], r["parent_key"], r["source_file"], r["pages"])

        return results


class HybridRetriever:
    """混合检索器：0.5*BM25 + 0.5*向量，归一化后加权融合，再 gte-rerank-v2 重排"""

    def __init__(self, vector_db_dir, api_key=None):
        self.vector_db_dir = Path(vector_db_dir)
        self._api_key = api_key
        self._vector_retrievers = {}
        self._bm25_retrievers = {}
        self._company_registry = None

        logger.info("[HybridRetriever] 初始化，向量数据库目录: %s", self.vector_db_dir)

    def _ensure_api_key(self):
        if not self._api_key:
            self._api_key = get_api_key()
            logger.info("[HybridRetriever] API Key 获取成功 (长度: %d)", len(self._api_key))
        return self._api_key

    def _load_company_registry(self):
        registry_path = self.vector_db_dir / "company_registry.json"
        if not registry_path.exists():
            logger.error("[HybridRetriever] 公司注册表不存在: %s", registry_path)
            raise FileNotFoundError(f"公司注册表不存在: {registry_path}")

        self._company_registry = json.loads(registry_path.read_text(encoding="utf-8"))
        companies = list(self._company_registry.get("companies", {}).keys())
        logger.info("[HybridRetriever] 公司注册表加载完成，已注册公司: %s", ", ".join(companies))
        return self._company_registry

    def _get_retrievers(self, company_name):
        company_dir = self.vector_db_dir / company_name
        if not company_dir.exists():
            logger.error("[HybridRetriever] 公司目录不存在: %s", company_dir)
            raise FileNotFoundError(f"公司目录不存在: {company_dir}")

        if company_name not in self._vector_retrievers:
            api_key = self._ensure_api_key()
            logger.info("[HybridRetriever] 首次加载公司 '%s' 的向量检索器", company_name)
            vr = VectorRetriever(company_dir, api_key)
            vr.load()
            self._vector_retrievers[company_name] = vr

        if company_name not in self._bm25_retrievers:
            logger.info("[HybridRetriever] 首次加载公司 '%s' 的 BM25 检索器", company_name)
            br = BM25Retriever(company_dir)
            br.load()
            self._bm25_retrievers[company_name] = br

        return self._vector_retrievers[company_name], self._bm25_retrievers[company_name]

    def _ensure_company_coverage(self, reranked, all_scored, company_set, top_n, query=None, key_terms=None):
        covered = set(r["company_name"] for r in reranked)
        missing = company_set - covered

        if not missing:
            logger.info("[HybridRetriever] 公司覆盖检查通过: %s 已全部覆盖", ", ".join(covered))
            return reranked

        logger.info("[HybridRetriever] 公司覆盖不足! 已覆盖: %s, 缺失: %s",
                     ", ".join(covered), ", ".join(missing))

        reranked_keys = set(r["parent_key"] for r in reranked)
        result = list(reranked)

        for cn in missing:
            best = None

            for cand in all_scored:
                if cand["company_name"] == cn and cand["parent_key"] not in reranked_keys:
                    if best is None or cand["scores"]["rerank"] > best["scores"]["rerank"]:
                        best = cand

            if (not best or best["scores"]["rerank"] < 5.0) and query and key_terms:
                re_query = f"{cn} {key_terms}"
                logger.info("[HybridRetriever] 保底重新检索: '%s'", re_query)
                re_merged = self._search_single_company(re_query, cn)
                if re_merged:
                    re_top = re_merged[:3]
                    re_reranked, _ = self._llm_rerank(re_query, re_top, top_n=1)
                    if re_reranked:
                        # 重新检索到结果，即使 rerank 分数低于5.0也使用
                        if not best or re_reranked[0]["scores"]["rerank"] > best["scores"]["rerank"]:
                            best = re_reranked[0]
                        logger.info("[HybridRetriever] 重新检索到 %s 结果: rerank=%.1f",
                                     cn, best["scores"]["rerank"])
                    else:
                        # rerank 失败时，直接用 hybrid 分数最高的结果
                        logger.info("[HybridRetriever] %s 重新检索 rerank 失败，使用 hybrid 排序结果", cn)
                        if not best:
                            best = re_top[0]
                            logger.info("[HybridRetriever] %s 使用 hybrid 保底结果: hybrid=%.4f",
                                         cn, best["scores"]["hybrid"])

            if not best:
                logger.warning("[HybridRetriever] 缺失公司 '%s' 无法补入", cn)
                continue

            company_counts = {}
            for r in result:
                company_counts[r["company_name"]] = company_counts.get(r["company_name"], 0) + 1

            over_represented = [c for c, cnt in company_counts.items() if cnt > 1]

            if over_represented:
                lowest_idx = None
                lowest_score = float('inf')
                for i, r in enumerate(result):
                    if r["company_name"] in over_represented and r["scores"]["rerank"] < lowest_score:
                        lowest_score = r["scores"]["rerank"]
                        lowest_idx = i
                if lowest_idx is not None:
                    removed = result.pop(lowest_idx)
                    logger.info("[HybridRetriever] 替换: 移除 %s (rerank=%.1f), 补入 %s (rerank=%.1f)",
                                removed["company_name"], removed["scores"]["rerank"],
                                best["company_name"], best["scores"]["rerank"])
            else:
                result.sort(key=lambda x: x["scores"]["rerank"])
                removed = result.pop(0)
                logger.info("[HybridRetriever] 替换最低分: 移除 %s (rerank=%.1f), 补入 %s (rerank=%.1f)",
                            removed["company_name"], removed["scores"]["rerank"],
                            best["company_name"], best["scores"]["rerank"])

            result.append(best)
            reranked_keys.add(best["parent_key"])

        result.sort(key=lambda x: x["scores"]["rerank"], reverse=True)

        final_covered = set(r["company_name"] for r in result)
        logger.info("[HybridRetriever] 保底后最终覆盖: %s", ", ".join(final_covered))
        return result[:top_n]

    def _ensure_numeric_data_coverage(self, reranked, all_scored, mentioned_companies):
        """确保每家公司的结果中至少有一条包含数字型财务数据

        对于对比查询，如果某家公司的所有结果都不含关键财务数字（如'亿元'+'数字'），
        则从 all_scored 中补充含数据的文档块。
        """
        if not mentioned_companies:
            return reranked

        # 营收相关关键词（更精确，避免匹配到利润总额等非营收数据）
        revenue_keywords = ["营业收入为", "营业收入达", "营收为", "营收达",
                            "营业收入人民币", "营业收入达到", "全年营业收入"]

        # 按公司分组检查
        company_results = {}
        for r in reranked:
            cn = r["company_name"]
            if cn not in company_results:
                company_results[cn] = []
            company_results[cn].append(r)

        reranked_keys = set(r["parent_key"] for r in reranked)
        supplements = []

        for cn in mentioned_companies:
            results_for_company = company_results.get(cn, [])
            if not results_for_company:
                continue

            # 检查是否已有含营收数据的结果
            has_revenue_data = False
            for r in results_for_company:
                text = r.get("parent_text", "")
                if any(kw in text for kw in revenue_keywords):
                    has_revenue_data = True
                    break

            if not has_revenue_data:
                # 从 all_scored 中查找含营收数据的文档块
                logger.info("[HybridRetriever] 公司 '%s' 结果中无营收数据，尝试补充", cn)
                for cand in all_scored:
                    if cand["company_name"] != cn or cand["parent_key"] in reranked_keys:
                        continue
                    text = cand.get("parent_text", "")
                    if any(kw in text for kw in revenue_keywords):
                        supplements.append(cand)
                        reranked_keys.add(cand["parent_key"])
                        logger.info("[HybridRetriever] 公司 '%s' 补充含营收数据文档块: rerank=%.1f | pk=%s",
                                     cn, cand["scores"].get("rerank", 0), cand["parent_key"])
                        break

        if supplements:
            reranked = list(reranked) + supplements
            logger.info("[HybridRetriever] 营收数据保底补充 %d 条", len(supplements))

        return reranked

    @staticmethod
    def _normalize_scores(results, score_key):
        if not results:
            logger.info("[HybridRetriever] 归一化跳过：结果列表为空 (score_key=%s)", score_key)
            return results

        scores = [r["scores"].get(score_key, 0.0) for r in results]
        min_s = min(scores)
        max_s = max(scores)
        range_s = max_s - min_s

        logger.info("[HybridRetriever] 归一化 %s 分数: min=%.4f, max=%.4f, range=%.4f",
                     score_key, min_s, max_s, range_s)

        if range_s == 0:
            for r in results:
                r["scores"][f"{score_key}_norm"] = 1.0 if max_s > 0 else 0.0
            logger.info("[HybridRetriever] %s 分数范围为 0，统一设为 %.1f", score_key,
                         1.0 if max_s > 0 else 0.0)
        else:
            for r in results:
                r["scores"][f"{score_key}_norm"] = round(
                    (r["scores"].get(score_key, 0.0) - min_s) / range_s, 4
                )

        return results

    def _merge_results(self, vector_results, bm25_results, intent=None):
        logger.info("[HybridRetriever] 开始合并向量与 BM25 结果")
        logger.info("[HybridRetriever] 向量结果数: %d, BM25 结果数: %d",
                     len(vector_results), len(bm25_results))

        weights = INTENT_WEIGHTS.get(intent, {"bm25": BM25_WEIGHT, "vector": VECTOR_WEIGHT}) if intent else {"bm25": BM25_WEIGHT, "vector": VECTOR_WEIGHT}
        bm25_w = weights["bm25"]
        vector_w = weights["vector"]
        logger.info("[HybridRetriever] 检索权重: intent=%s, bm25=%.1f, vector=%.1f",
                     intent or "default", bm25_w, vector_w)
        logger.info("[HybridRetriever] 向量检索结果数: %d, BM25检索结果数: %d",
                     len(vector_results), len(bm25_results))
        # 详细输出 BM25 检索结果
        for i, r in enumerate(bm25_results[:3]):
            logger.info("[HybridRetriever]   BM25原始 #%d: bm25=%.4f | pk=%s | 来源: %s | 页码: %s",
                         i + 1, r["scores"].get("bm25", 0), r["parent_key"], r["source_file"], r["pages"])

        vector_results = self._normalize_scores(vector_results, "vector")
        bm25_results = self._normalize_scores(bm25_results, "bm25")

        merged = {}
        for r in vector_results:
            pk = r["parent_key"]
            if pk not in merged:
                merged[pk] = {
                    "parent_text": r["parent_text"],
                    "source_file": r["source_file"],
                    "pages": r["pages"],
                    "company_name": r["company_name"],
                    "parent_key": pk,
                    "scores": {},
                }
            new_vec = r["scores"].get("vector", 0.0)
            new_vec_norm = r["scores"].get("vector_norm", 0.0)
            old_vec = merged[pk]["scores"].get("vector", 0.0)
            old_vec_norm = merged[pk]["scores"].get("vector_norm", 0.0)
            if new_vec > old_vec:
                merged[pk]["scores"]["vector"] = new_vec
                merged[pk]["scores"]["vector_norm"] = new_vec_norm

        for r in bm25_results:
            pk = r["parent_key"]
            if pk not in merged:
                merged[pk] = {
                    "parent_text": r["parent_text"],
                    "source_file": r["source_file"],
                    "pages": r["pages"],
                    "company_name": r["company_name"],
                    "parent_key": pk,
                    "scores": {},
                }
            new_bm25 = r["scores"].get("bm25", 0.0)
            new_bm25_norm = r["scores"].get("bm25_norm", 0.0)
            old_bm25 = merged[pk]["scores"].get("bm25", 0.0)
            old_bm25_norm = merged[pk]["scores"].get("bm25_norm", 0.0)
            if new_bm25 > old_bm25:
                merged[pk]["scores"]["bm25"] = new_bm25
                merged[pk]["scores"]["bm25_norm"] = new_bm25_norm

        logger.info("[HybridRetriever] 去重后合并结果数: %d", len(merged))

        # 统计重叠情况
        vec_only = sum(1 for item in merged.values() if item["scores"].get("vector_norm", 0) > 0 and item["scores"].get("bm25_norm", 0) == 0)
        bm25_only = sum(1 for item in merged.values() if item["scores"].get("bm25_norm", 0) > 0 and item["scores"].get("vector_norm", 0) == 0)
        both = sum(1 for item in merged.values() if item["scores"].get("vector_norm", 0) > 0 and item["scores"].get("bm25_norm", 0) > 0)
        logger.info("[HybridRetriever] 合并统计: 仅向量=%d, 仅BM25=%d, 双重叠=%d", vec_only, bm25_only, both)

        for pk, item in merged.items():
            v_norm = item["scores"].get("vector_norm", 0.0)
            b_norm = item["scores"].get("bm25_norm", 0.0)
            hybrid_score = vector_w * v_norm + bm25_w * b_norm
            item["scores"]["hybrid"] = round(hybrid_score, 4)

        sorted_results = sorted(merged.values(), key=lambda x: x["scores"]["hybrid"], reverse=True)

        # 确保仅 BM25 的结果不被完全截断：至少保留 top 3 条仅 BM25 结果
        top_results = sorted_results[:HYBRID_TOP_K]
        bm25_only_in_top = sum(1 for r in top_results if r["scores"].get("bm25_norm", 0) > 0 and r["scores"].get("vector_norm", 0) == 0)
        logger.info("[HybridRetriever] top_%d 中仅BM25结果数: %d (总仅BM25: %d)", HYBRID_TOP_K, bm25_only_in_top, bm25_only)
        if bm25_only_in_top == 0 and bm25_only > 0:
            # 从剩余结果中补充 top 3 条仅 BM25 结果
            bm25_only_results = [r for r in sorted_results[HYBRID_TOP_K:] if r["scores"].get("bm25_norm", 0) > 0 and r["scores"].get("vector_norm", 0) == 0]
            for r in bm25_only_results[:3]:
                top_results.append(r)
            logger.info("[HybridRetriever] 补充 %d 条仅 BM25 结果（防止 BM25 贡献被截断）", min(3, len(bm25_only_results)))
        elif bm25_only_in_top > 0:
            logger.info("[HybridRetriever] top_%d 中已有 %d 条仅 BM25 结果，无需补充", HYBRID_TOP_K, bm25_only_in_top)

        logger.info("[HybridRetriever] 混合融合完成，取 top_%d 结果", HYBRID_TOP_K)
        for i, r in enumerate(top_results):
            logger.info("[HybridRetriever]   #%d hybrid=%.4f (vec_norm=%.4f, bm25_norm=%.4f) | 来源: %s | 页码: %s",
                         i + 1,
                         r["scores"]["hybrid"],
                         r["scores"].get("vector_norm", 0.0),
                         r["scores"].get("bm25_norm", 0.0),
                         r["source_file"],
                         r["pages"])

        return top_results

    def _gte_rerank(self, query, candidates, top_n=RERANK_TOP_N):
        logger.info("[HybridRetriever] 开始 gte-rerank-v2 批量重排，查询: '%s'，候选数: %d，取 top_%d",
                     query[:80] + "..." if len(query) > 80 else query,
                     len(candidates), top_n)

        import dashscope
        api_key = self._ensure_api_key()
        dashscope.api_key = api_key

        documents = []
        for cand in candidates:
            text = cand["parent_text"]
            if len(text) > 800:
                text = text[:800] + "..."
            documents.append(text)

        logger.info("[HybridRetriever] 调用 gte-rerank-v2，文档数: %d", len(documents))

        resp = dashscope.TextReRank.call(
            model="gte-rerank-v2",
            query=query,
            documents=documents,
            top_n=top_n,
            return_documents=True,
            timeout=15,
        )

        if resp.status_code != 200:
            raise Exception(f"gte-rerank-v2 API 调用失败: {resp.status_code} - {resp.message}")

        rerank_results = resp.output["results"]
        logger.info("[HybridRetriever] gte-rerank-v2 返回 %d 条结果", len(rerank_results))

        scored_candidates = list(candidates)
        for r in rerank_results:
            idx = r["index"]
            relevance_score = r["relevance_score"]
            rerank_score = round(relevance_score * 10.0, 1)

            if idx < len(scored_candidates):
                scored_candidates[idx]["scores"]["rerank"] = rerank_score
                logger.info("[HybridRetriever]   idx=%d rerank=%.1f (raw=%.4f) | 来源: %s",
                             idx, rerank_score, relevance_score, scored_candidates[idx]["source_file"])

        for cand in scored_candidates:
            if "rerank" not in cand["scores"]:
                cand["scores"]["rerank"] = 0.0

        scored_candidates.sort(key=lambda x: x["scores"]["rerank"], reverse=True)
        top_results = scored_candidates[:top_n]

        logger.info("[HybridRetriever] gte-rerank-v2 重排完成，返回 top_%d 结果", len(top_results))
        for i, r in enumerate(top_results):
            logger.info("[HybridRetriever]   #%d rerank=%.1f | hybrid=%.4f | 来源: %s | 页码: %s",
                         i + 1,
                         r["scores"]["rerank"],
                         r["scores"]["hybrid"],
                         r["source_file"],
                         r["pages"])

        return top_results, scored_candidates

    def _fallback_rerank(self, candidates, top_n=RERANK_TOP_N):
        logger.info("[HybridRetriever] 使用 hybrid 分数回退排序，候选数: %d", len(candidates))

        scored_candidates = list(candidates)
        for cand in scored_candidates:
            hybrid = cand["scores"].get("hybrid", 0.0)
            cand["scores"]["rerank"] = round(hybrid * 10.0, 1)

        scored_candidates.sort(key=lambda x: x["scores"]["rerank"], reverse=True)
        top_results = scored_candidates[:top_n]

        logger.info("[HybridRetriever] 回退排序完成，返回 top_%d 结果", len(top_results))
        for i, r in enumerate(top_results):
            logger.info("[HybridRetriever]   #%d rerank=%.1f (fallback) | hybrid=%.4f | 来源: %s",
                         i + 1,
                         r["scores"]["rerank"],
                         r["scores"]["hybrid"],
                         r["source_file"])

        return top_results, scored_candidates

    def _llm_rerank(self, query, candidates, top_n=RERANK_TOP_N):
        if not candidates:
            logger.info("[HybridRetriever] 重排跳过：候选列表为空")
            return ([], [])

        logger.info("[HybridRetriever] 开始重排，查询: '%s'，候选数: %d，取 top_%d",
                     query[:80] + "..." if len(query) > 80 else query,
                     len(candidates), top_n)

        try:
            return self._gte_rerank(query, candidates, top_n)
        except Exception as e:
            logger.warning("[HybridRetriever] gte-rerank-v2 调用失败: %s，回退到 hybrid 排序", str(e))
            return self._fallback_rerank(candidates, top_n)

    @staticmethod
    def _compute_confidence(scores):
        rerank = scores.get("rerank", 0.0)
        hybrid = scores.get("hybrid", 0.0)

        if rerank >= 8.0:
            confidence = "high"
        elif rerank >= 5.0:
            confidence = "medium"
        elif hybrid >= 0.3:
            confidence = "medium"
        else:
            confidence = "low"

        logger.info("[HybridRetriever] 置信度计算: rerank=%.1f, hybrid=%.4f -> confidence=%s",
                     rerank, hybrid, confidence)
        return confidence

    def _extract_key_terms(self, query, company_names):
        import re
        key_terms = query
        for cn in company_names:
            key_terms = key_terms.replace(cn, "")
        for cn in company_names:
            for abbr in COMPANY_ABBREV_MAP.get(cn, []):
                key_terms = key_terms.replace(abbr, "")
        key_terms = re.sub(r'[、，,和与及]', ' ', key_terms)
        key_terms = re.sub(r'\s+', ' ', key_terms).strip()
        logger.info("[HybridRetriever] 提取关键词: '%s' -> '%s'", query, key_terms)
        return key_terms

    def _search_single_company(self, query, company_name, intent=None):
        logger.info("[HybridRetriever] 单公司检索: '%s', 公司: %s",
                     query[:80] + "..." if len(query) > 80 else query, company_name)
        try:
            vr, br = self._get_retrievers(company_name)
        except Exception as e:
            logger.error("[HybridRetriever] 加载公司 '%s' 检索器失败: %s", company_name, str(e))
            return []
        try:
            vector_results = vr.search(query, top_k=VECTOR_TOP_K)
        except Exception as e:
            logger.error("[HybridRetriever] 公司 '%s' 向量检索失败: %s", company_name, str(e))
            vector_results = []
        try:
            bm25_results = br.search(query, top_k=BM25_TOP_K)
        except Exception as e:
            logger.error("[HybridRetriever] 公司 '%s' BM25 检索失败: %s", company_name, str(e))
            bm25_results = []
        if not vector_results and not bm25_results:
            logger.warning("[HybridRetriever] 公司 '%s' 两种检索均无结果", company_name)
            return []
        merged = self._merge_results(vector_results, bm25_results, intent=intent)
        return merged

    def _search_comparison(self, query, mentioned_companies, top_n, extracted_years=None):
        logger.info("[HybridRetriever] ===== 对比查询模式 =====")
        key_terms = self._extract_key_terms(query, mentioned_companies)
        if extracted_years:
            year_str = " ".join(extracted_years)
            key_terms = f"{year_str} {key_terms}".strip()
            logger.info("[HybridRetriever] 子查询加入年份信息: '%s'", year_str)
        all_merged = []
        # 对比查询每家公司取更多候选，避免含关键数据的文档块被截断
        per_company = max(10, HYBRID_TOP_K)
        companies_with_results = set()
        for cn in mentioned_companies:
            sub_query = f"{cn} {key_terms}"
            logger.info("[HybridRetriever] 对比子查询: '%s'", sub_query)
            merged = self._search_single_company(sub_query, cn, intent="comparison")
            if merged:
                # 统计截断前 BM25 独有条目数
                bm25_only_count = sum(1 for r in merged if r["scores"].get("bm25_norm", 0) > 0 and r["scores"].get("vector_norm", 0) == 0)
                vec_only_count = sum(1 for r in merged if r["scores"].get("vector_norm", 0) > 0 and r["scores"].get("bm25_norm", 0) == 0)
                both_count = sum(1 for r in merged if r["scores"].get("vector_norm", 0) > 0 and r["scores"].get("bm25_norm", 0) > 0)
                truncated = merged[:per_company]
                bm25_only_in_truncated = sum(1 for r in truncated if r["scores"].get("bm25_norm", 0) > 0 and r["scores"].get("vector_norm", 0) == 0)
                logger.info("[HybridRetriever] 公司 '%s' 合并统计: 总=%d, 仅向量=%d, 仅BM25=%d, 双重叠=%d",
                             cn, len(merged), vec_only_count, bm25_only_count, both_count)
                logger.info("[HybridRetriever] 公司 '%s' 截断取 %d 条: 仅BM25=%d",
                             cn, per_company, bm25_only_in_truncated)

                # 保底机制：检查截断结果是否包含关键财务数据
                # 如果截断结果中不含数字型数据，从后续结果中补充含数字的文档块
                has_numeric_data = any(
                    any(c.isdigit() for c in r.get("parent_text", "")[:500] if c)
                    and any(kw in r.get("parent_text", "") for kw in ["亿元", "万元", "人民币", "增长", "收入为", "收入达"])
                    for r in truncated
                )
                if not has_numeric_data and len(merged) > per_company:
                    # 从截断后的结果中查找含数字的文档块
                    numeric_supplements = []
                    for r in merged[per_company:]:
                        text = r.get("parent_text", "")
                        if any(c.isdigit() for c in text[:500]) and any(kw in text for kw in ["亿元", "万元", "人民币", "增长", "收入为", "收入达"]):
                            numeric_supplements.append(r)
                            if len(numeric_supplements) >= 2:
                                break
                    if numeric_supplements:
                        truncated.extend(numeric_supplements)
                        logger.info("[HybridRetriever] 公司 '%s' 补充 %d 条含关键财务数据的文档块",
                                     cn, len(numeric_supplements))

                all_merged.extend(truncated)
                companies_with_results.add(cn)
                logger.info("[HybridRetriever] 公司 '%s' 子查询返回 %d 条结果", cn, len(truncated))
            else:
                logger.warning("[HybridRetriever] 公司 '%s' 子查询无结果，尝试简化查询重试", cn)
                # 子查询无结果时，尝试用更简化的关键词重试
                simplified_terms = key_terms
                for year in (extracted_years or []):
                    simplified_terms = simplified_terms.replace(year, "").strip()
                if simplified_terms and simplified_terms != key_terms:
                    retry_query = f"{cn} {simplified_terms}"
                    logger.info("[HybridRetriever] 简化重试: '%s'", retry_query)
                    retry_merged = self._search_single_company(retry_query, cn, intent="comparison")
                    if retry_merged:
                        all_merged.extend(retry_merged[:per_company])
                        companies_with_results.add(cn)
                        logger.info("[HybridRetriever] 公司 '%s' 简化重试返回 %d 条结果", cn, len(retry_merged[:per_company]))
                    else:
                        logger.warning("[HybridRetriever] 公司 '%s' 简化重试仍无结果", cn)
                else:
                    logger.warning("[HybridRetriever] 公司 '%s' 无法简化查询", cn)
        if not all_merged:
            logger.warning("[HybridRetriever] 对比查询所有子查询均无结果")
            return []
        all_merged.sort(key=lambda x: x["scores"]["hybrid"], reverse=True)
        # 对比查询候选数量：每家公司至少保留 per_company 条，避免含关键数据的文档块被截断
        comparison_candidates_limit = max(HYBRID_TOP_K, len(mentioned_companies) * per_company)
        # 截断候选时确保每家已有结果的公司至少保留1条
        candidates = []
        seen_companies_in_candidates = set()
        # 先按分数取 top，但保证每家公司至少1条
        for r in all_merged:
            if len(candidates) >= comparison_candidates_limit:
                break
            cn = r["company_name"]
            if cn not in seen_companies_in_candidates:
                candidates.append(r)
                seen_companies_in_candidates.add(cn)
            elif len(candidates) < comparison_candidates_limit:
                candidates.append(r)
        logger.info("[HybridRetriever] 对比查询合并候选数: %d (覆盖公司: %s)", len(candidates), ", ".join(seen_companies_in_candidates))
        # 对比查询模式下，top_n 至少为 公司数*2，确保每家公司至少2条结果
        comparison_top_n = max(top_n, len(mentioned_companies) * 2)
        if comparison_top_n > top_n:
            logger.info("[HybridRetriever] 对比查询调整 top_n: %d -> %d (公司数=%d)", top_n, comparison_top_n, len(mentioned_companies))
        reranked, all_scored = self._llm_rerank(query, candidates, top_n=comparison_top_n)
        coverage_set = set(mentioned_companies)
        reranked = self._ensure_company_coverage(
            reranked, all_scored, coverage_set, top_n,
            query=query, key_terms=key_terms
        )

        # 关键数据保底补充：检查每家公司的结果中是否包含数字型财务数据
        # 如果某家公司所有结果都不含关键数据，从 all_scored 中补充含数据的文档块
        reranked = self._ensure_numeric_data_coverage(reranked, all_scored, mentioned_companies)
        for r in reranked:
            r["scores"]["confidence"] = self._compute_confidence(r["scores"])
        logger.info("[HybridRetriever] ===== 对比查询完成 =====")
        logger.info("[HybridRetriever] 最终返回 %d 条结果", len(reranked))
        for i, r in enumerate(reranked):
            logger.info("[HybridRetriever]   最终 #%d: rerank=%.1f | hybrid=%.4f | confidence=%s | 来源: %s | 页码: %s",
                         i + 1,
                         r["scores"]["rerank"],
                         r["scores"]["hybrid"],
                         r["scores"]["confidence"],
                         r["source_file"],
                         r["pages"])
        return reranked

    def search(self, query, company_name=None, top_n=RERANK_TOP_N, mentioned_companies=None, intent=None, extracted_years=None):
        logger.info("=" * 60)
        logger.info("[HybridRetriever] 开始混合检索")
        logger.info("[HybridRetriever] 查询: '%s'", query)
        logger.info("[HybridRetriever] 指定公司: %s", company_name or "全部")
        weights = INTENT_WEIGHTS.get(intent, {"bm25": BM25_WEIGHT, "vector": VECTOR_WEIGHT}) if intent else {"bm25": BM25_WEIGHT, "vector": VECTOR_WEIGHT}
        logger.info("[HybridRetriever] 参数: BM25权重=%.1f, 向量权重=%.1f, hybrid_top_k=%d, rerank_top_n=%d",
                     weights["bm25"], weights["vector"], HYBRID_TOP_K, top_n)
        if intent:
            logger.info("[HybridRetriever] 意图: %s", intent)
        if mentioned_companies:
            logger.info("[HybridRetriever] 提及公司: %s", ", ".join(mentioned_companies))
        logger.info("=" * 60)

        if not self._company_registry:
            self._load_company_registry()

        if intent == "comparison" and mentioned_companies and len(mentioned_companies) > 1:
            return self._search_comparison(query, mentioned_companies, top_n, extracted_years=extracted_years)

        if company_name:
            companies = [company_name]
            if company_name not in self._company_registry.get("companies", {}):
                logger.error("[HybridRetriever] 公司 '%s' 未在注册表中", company_name)
                available = list(self._company_registry.get("companies", {}).keys())
                logger.info("[HybridRetriever] 可用公司: %s", ", ".join(available))
                raise ValueError(f"公司 '{company_name}' 未在注册表中，可用: {available}")
        elif mentioned_companies:
            valid_companies = []
            for mc in mentioned_companies:
                if mc in self._company_registry.get("companies", {}):
                    valid_companies.append(mc)
                else:
                    logger.warning("[HybridRetriever] 提及公司 '%s' 未在注册表中，跳过", mc)
            companies = valid_companies if valid_companies else list(
                self._company_registry.get("companies", {}).keys())
            logger.info("[HybridRetriever] 根据提及公司限定检索范围: %s", ", ".join(companies))
        else:
            companies = list(self._company_registry.get("companies", {}).keys())

        logger.info("[HybridRetriever] 待检索公司: %s", ", ".join(companies))

        all_merged = []

        for cn in companies:
            logger.info("[HybridRetriever] >>> 检索公司: %s", cn)

            try:
                vr, br = self._get_retrievers(cn)
            except Exception as e:
                logger.error("[HybridRetriever] 加载公司 '%s' 检索器失败: %s", cn, str(e))
                continue

            try:
                vector_results = vr.search(query, top_k=VECTOR_TOP_K)
            except Exception as e:
                logger.error("[HybridRetriever] 公司 '%s' 向量检索失败: %s", cn, str(e))
                vector_results = []

            try:
                bm25_results = br.search(query, top_k=BM25_TOP_K)
            except Exception as e:
                logger.error("[HybridRetriever] 公司 '%s' BM25 检索失败: %s", cn, str(e))
                bm25_results = []

            if not vector_results and not bm25_results:
                logger.warning("[HybridRetriever] 公司 '%s' 两种检索均无结果，跳过", cn)
                continue

            merged = self._merge_results(vector_results, bm25_results, intent=intent)
            all_merged.extend(merged)

            logger.info("[HybridRetriever] 公司 '%s' 检索→融合完成: 向量=%d, BM25=%d → 融合=%d | 累计=%d",
                         cn, len(vector_results), len(bm25_results), len(merged), len(all_merged))

        if not all_merged:
            logger.warning("[HybridRetriever] 所有公司检索均无结果")
            return []

        all_merged.sort(key=lambda x: x["scores"]["hybrid"], reverse=True)

        company_set = set(r["company_name"] for r in all_merged)
        if len(company_set) > 1:
            per_company = max(5, HYBRID_TOP_K // len(company_set))
            company_buckets = {}
            for r in all_merged:
                cn = r["company_name"]
                if cn not in company_buckets:
                    company_buckets[cn] = []
                if len(company_buckets[cn]) < per_company:
                    company_buckets[cn].append(r)

            candidates = []
            for cn in company_buckets:
                candidates.extend(company_buckets[cn])
            candidates.sort(key=lambda x: x["scores"]["hybrid"], reverse=True)
            candidates = candidates[:HYBRID_TOP_K]

            logger.info("[HybridRetriever] 多公司公平分配: %s, 每家至少 %d 条",
                         ", ".join(f"{cn}={len(company_buckets[cn])}" for cn in company_buckets),
                         per_company)
        else:
            candidates = all_merged[:HYBRID_TOP_K]

        logger.info("[HybridRetriever] 跨公司合并后候选数: %d（取 top_%d）", len(all_merged), len(candidates))

        reranked, all_scored = self._llm_rerank(query, candidates, top_n=top_n)

        coverage_set = set(mentioned_companies) if mentioned_companies else company_set
        if len(coverage_set) > 1:
            search_key_terms = self._extract_key_terms(query, list(coverage_set)) if mentioned_companies else None
            reranked = self._ensure_company_coverage(reranked, all_scored, coverage_set, top_n,
                                                      query=query, key_terms=search_key_terms)

        for r in reranked:
            r["scores"]["confidence"] = self._compute_confidence(r["scores"])

        # ========================================================
        # 漏斗全景汇总
        # ========================================================
        logger.info("=" * 60)
        logger.info("[HybridRetriever] ====== 检索漏斗全景 ======")
        logger.info("[HybridRetriever] 待检索公司数: %d (%s)", len(companies), ", ".join(companies))
        logger.info("[HybridRetriever] 每家公司: 向量top_%d + BM25_top_%d", VECTOR_TOP_K, BM25_TOP_K)
        logger.info("[HybridRetriever] ↓ 融合后候选总数: %d 条", len(all_merged))
        logger.info("[HybridRetriever] ↓ 跨公司分配送入重排: %d 条 (HYBRID_TOP_K=%d)", len(candidates), HYBRID_TOP_K)
        logger.info("[HybridRetriever] ↓ gte-rerank 返回: %d 条 (top_n=%d)", len(reranked), top_n)
        coverage_after = set(r["company_name"] for r in reranked)
        logger.info("[HybridRetriever] ↓ 最终覆盖公司: %s", ", ".join(coverage_after) if coverage_after else "无")
        logger.info("[HybridRetriever] ====== 漏斗全景结束 ======")
        logger.info("=" * 60)
        logger.info("[HybridRetriever] 混合检索完成，最终返回 %d 条结果", len(reranked))
        for i, r in enumerate(reranked):
            logger.info("[HybridRetriever]   最终 #%d: rerank=%.1f | hybrid=%.4f | confidence=%s | 来源: %s | 页码: %s",
                         i + 1,
                         r["scores"]["rerank"],
                         r["scores"]["hybrid"],
                         r["scores"]["confidence"],
                         r["source_file"],
                         r["pages"])
        logger.info("=" * 60)

        return reranked


class RAGGenerator:
    """RAG 生成器：将检索结果 + 来源信息送入 LLM 生成最终答案"""

    GENERATION_MODEL = "qwen-max"
    MAX_CONTEXT_TOKENS = 6000

    def __init__(self, vector_db_dir, api_key=None, conversation_manager=None):
        self.vector_db_dir = Path(vector_db_dir)
        self._api_key = api_key
        self._retriever = None
        self.conversation_manager = conversation_manager

        logger.info("[RAGGenerator] 初始化，向量数据库目录: %s", self.vector_db_dir)

    def _ensure_api_key(self):
        if not self._api_key:
            self._api_key = get_api_key()
            logger.info("[RAGGenerator] API Key 获取成功 (长度: %d)", len(self._api_key))
        return self._api_key

    def _get_retriever(self):
        if not self._retriever:
            self._retriever = HybridRetriever(self.vector_db_dir, api_key=self._ensure_api_key())
        return self._retriever

    def _build_context(self, retrieved_results):
        logger.info("[RAGGenerator] 开始构建 LLM 上下文，检索结果数: %d", len(retrieved_results))

        # 识别所有涉及的公司
        all_companies = set(r.get("company_name", "未知公司") for r in retrieved_results)

        # 日志：打印每条检索结果的内容摘要
        for i, r in enumerate(retrieved_results):
            company = r.get("company_name", "未知公司")
            source_file = r.get("source_file", "未知来源")
            pages = r.get("pages", [])
            text = r.get("parent_text", "")
            pages_str = f"第{pages[0]}-{pages[-1]}页" if pages and len(pages) >= 2 else (
                f"第{pages[0]}页" if pages else "页码未知")
            text_preview = text[:150].replace("\n", " ") + ("..." if len(text) > 150 else "")
            logger.info("[RAGGenerator]   上下文片段 #%d: 公司=%s | 来源=%s | %s | 文本=%s",
                         i + 1, company, source_file, pages_str, text_preview)

        # 第一轮：确保每家公司至少1条内容进入上下文
        company_added = set()
        priority_parts = []
        remaining_parts = []
        total_tokens = 0

        for i, r in enumerate(retrieved_results):
            source_file = r.get("source_file", "未知来源")
            pages = r.get("pages", [])
            company = r.get("company_name", "未知公司")
            confidence = r.get("scores", {}).get("confidence", "unknown")
            rerank = r.get("scores", {}).get("rerank", 0.0)
            text = r.get("parent_text", "")

            pages_str = f"第{pages[0]}-{pages[-1]}页" if pages and len(pages) >= 2 else (
                f"第{pages[0]}页" if pages else "页码未知"
            )

            chunk_tokens = len(ENCODING.encode(text))
            header = f"\n【来源{i + 1}】{company} | {source_file} | {pages_str} | 置信度: {confidence} | 重排分: {rerank}\n"
            entry = {"header": header, "text": text, "tokens": chunk_tokens, "company": company, "index": i + 1}

            if company not in company_added:
                priority_parts.append(entry)
                company_added.add(company)
            else:
                remaining_parts.append(entry)

        # 第二轮：按优先级构建上下文（先保证每家公司至少1条，再填充剩余）
        context_parts = []
        used_count = 0
        all_entries = priority_parts + remaining_parts

        for entry in all_entries:
            chunk_tokens = entry["tokens"]
            if total_tokens + chunk_tokens > self.MAX_CONTEXT_TOKENS:
                remaining = self.MAX_CONTEXT_TOKENS - total_tokens
                if remaining > 200:
                    truncated = ENCODING.decode(ENCODING.encode(entry["text"])[:remaining])
                    context_parts.append(entry["header"] + truncated)
                    total_tokens = self.MAX_CONTEXT_TOKENS
                    used_count += 1
                    logger.info("[RAGGenerator]   片段 #%d 截断至 %d tokens（已达上限）", entry["index"], remaining)
                else:
                    logger.info("[RAGGenerator]   片段 #%d 跳过（剩余空间不足: %d tokens）", entry["index"], remaining)
                break
            else:
                context_parts.append(entry["header"] + entry["text"])
                total_tokens += chunk_tokens
                used_count += 1

        context = "\n---\n".join(context_parts)
        logger.info("[RAGGenerator] 上下文构建完成: 使用 %d/%d 个片段，总 tokens=%d，覆盖公司: %s",
                     used_count, len(retrieved_results), total_tokens, ", ".join(company_added))
        return context, used_count

    def _build_prompt(self, query, context, conversation_context=""):
        prompt = (
            "你是一个专业的企业年报分析助手。请根据以下检索到的文档内容，回答用户的问题。\n\n"
            "要求：\n"
            "1. 基于提供的文档内容作答，不要编造信息\n"
            "2. 在答案中标注信息来源，格式如：[来源1]、[来源2]\n"
            "3. 如果文档中没有足够信息回答问题，请明确说明\n"
            "4. 回答要准确、完整、有条理\n"
            "5. 如果用户问题省略了主语或上下文，请参考对话历史理解\n"
            "6. 涉及财务金额时注意单位换算：文档原始数据单位为「千元」，千元 ÷ 100,000 = 亿元，千元 ÷ 10 = 万元\n\n"
            f"{conversation_context}"
            f"用户问题：{query}\n\n"
            f"检索到的文档内容：\n{context}\n\n"
            "请基于以上文档内容回答用户问题："
        )
        return prompt

    def _build_comparison_prompt(self, query, context, conversation_context=""):
        prompt = (
            "你是一个专业的企业年报对比分析助手。请根据以下检索到的文档内容，对用户查询中涉及的公司进行横向对比分析。\n\n"
            "要求：\n"
            "1. 基于提供的文档内容作答，不要编造信息\n"
            "2. 对每家公司分别列出相关数据，然后进行横向对比\n"
            "3. 使用表格或结构化格式展示对比结果，便于直观比较\n"
            "4. 在答案中标注信息来源，格式如：[来源1]、[来源2]\n"
            "5. 如果某家公司的数据在文档中缺失，请明确说明「该公司的数据未在检索结果中找到」\n"
            "6. 回答要准确、完整、有条理\n"
            "7. 如果用户问题省略了主语或上下文，请参考对话历史理解\n"
            "8. 涉及财务金额时注意单位换算：文档原始数据单位为「千元」，千元 ÷ 100,000 = 亿元，千元 ÷ 10 = 万元\n\n"
            f"{conversation_context}"
            f"用户问题：{query}\n\n"
            f"检索到的文档内容：\n{context}\n\n"
            "请基于以上文档内容，对涉及的公司进行对比分析："
        )
        return prompt

    def _build_financial_data_prompt(self, query, context, conversation_context=""):
        prompt = (
            "你是一个持有CPA资质的专业财务分析师。请根据以下检索到的文档内容，精确回答用户的财务数据查询。\n\n"
            "要求：\n"
            "1. 必须基于提供的文档内容作答，严禁编造任何数字或数据\n"
            "2. 引用财务数据时，必须给出具体数值和单位（如亿元、%），禁止使用「大幅增长」「显著提升」等模糊表述\n"
            "3. 在答案中标注信息来源，格式如：[来源1]、[来源2]\n"
            "4. 如果同一指标在不同来源中有差异，请列出所有来源并标注差异\n"
            "5. 如果文档中没有用户查询的具体数据，请明确说明「检索结果中未包含该数据」\n"
            "6. 如有同比/环比数据，请一并给出变化幅度\n"
            "7. 如果用户问题省略了主语或上下文，请参考对话历史理解\n\n"
            "【重要 - 单位换算规则】\n"
            "检索文档中的财务数据原始单位为「千元」，用户通常以「亿元」或「万元」提问。你必须先读取文档中标示的原始单位，再按以下公式精确换算：\n"
            "  - 千元 → 亿元：数值 ÷ 100,000（即 数值 × 1000 ÷ 100,000,000）\n"
            "  - 千元 → 万元：数值 ÷ 10（即 数值 × 1000 ÷ 10,000）\n"
            "  示例：文档中写「营业收入 57,795,570」，单位是千元，则 57,795,570 ÷ 100,000 = 577.96 亿元，或 57,795,570 ÷ 10 = 5,779,557 万元。\n"
            "  严禁省略千位直接除以亿，严禁将千元数值当作元来换算。\n\n"
            f"{conversation_context}"
            f"用户问题：{query}\n\n"
            f"检索到的文档内容：\n{context}\n\n"
            "请基于以上文档内容，精确回答用户的财务数据查询："
        )
        return prompt

    def _build_trend_prompt(self, query, context, conversation_context=""):
        prompt = (
            "你是一个专业的企业财务趋势分析师。请根据以下检索到的文档内容，分析用户查询的趋势变化。\n\n"
            "要求：\n"
            "1. 基于提供的文档内容作答，不要编造信息\n"
            "2. 按时间顺序梳理关键数据点，标注具体年份和数值\n"
            "3. 指出关键拐点和变化原因（如有文档支持）\n"
            "4. 在答案中标注信息来源，格式如：[来源1]、[来源2]\n"
            "5. 如果文档中仅有一个时间点的数据，请说明「无法进行趋势分析，仅有单期数据」\n"
            "6. 禁止推测文档中未出现的未来趋势\n"
            "7. 如果用户问题省略了主语或上下文，请参考对话历史理解\n\n"
            f"{conversation_context}"
            f"用户问题：{query}\n\n"
            f"检索到的文档内容：\n{context}\n\n"
            "请基于以上文档内容，分析趋势变化："
        )
        return prompt

    def _build_business_analysis_prompt(self, query, context, conversation_context=""):
        prompt = (
            "你是一个专业的企业业务分析顾问。请根据以下检索到的文档内容，分析用户查询的业务运营情况。\n\n"
            "要求：\n"
            "1. 基于提供的文档内容作答，不要编造信息\n"
            "2. 从业务板块、市场份额、竞争优势等维度进行分析\n"
            "3. 引用具体数据支撑分析结论，标注信息来源如：[来源1]\n"
            "4. 如果文档中没有足够信息，请明确说明\n"
            "5. 回答要有条理，分点阐述\n"
            "6. 如果用户问题省略了主语或上下文，请参考对话历史理解\n\n"
            f"{conversation_context}"
            f"用户问题：{query}\n\n"
            f"检索到的文档内容：\n{context}\n\n"
            "请基于以上文档内容，分析业务运营情况："
        )
        return prompt

    def _generate_answer(self, prompt):
        import dashscope
        api_key = self._ensure_api_key()
        dashscope.api_key = api_key

        logger.info("[RAGGenerator] 开始调用 LLM 生成答案，模型: %s", self.GENERATION_MODEL)
        logger.info("[RAGGenerator] Prompt 长度: %d 字符", len(prompt))

        try:
            resp = dashscope.Generation.call(
                model=self.GENERATION_MODEL,
                prompt=prompt,
                max_tokens=2048,
                temperature=0.3,
                result_format="message",
                timeout=60,
            )

            if resp.status_code != 200:
                logger.error("[RAGGenerator] LLM 生成失败: %s - %s", resp.status_code, resp.message)
                raise Exception(f"LLM 生成失败: {resp.status_code} - {resp.message}")

            answer = resp.output["choices"][0]["message"]["content"].strip()
            usage = resp.usage
            logger.info("[RAGGenerator] LLM 生成成功，答案长度: %d 字符", len(answer))
            logger.info("[RAGGenerator] Token 用量: input=%d, output=%d, total=%d",
                         usage.get("input_tokens", 0),
                         usage.get("output_tokens", 0),
                         usage.get("total_tokens", 0))
            return answer

        except Exception as e:
            logger.error("[RAGGenerator] LLM 生成异常: %s", str(e))
            raise

    def _build_sources_summary(self, retrieved_results):
        sources = []
        for i, r in enumerate(retrieved_results):
            source_info = {
                "index": i + 1,
                "source_file": r.get("source_file", "未知来源"),
                "pages": r.get("pages", []),
                "company_name": r.get("company_name", "未知公司"),
                "scores": {
                    "hybrid": r.get("scores", {}).get("hybrid", 0.0),
                    "rerank": r.get("scores", {}).get("rerank", 0.0),
                    "confidence": r.get("scores", {}).get("confidence", "unknown"),
                },
            }
            if "vector" in r.get("scores", {}):
                source_info["scores"]["vector"] = r["scores"]["vector"]
            if "bm25" in r.get("scores", {}):
                source_info["scores"]["bm25"] = r["scores"]["bm25"]
            sources.append(source_info)

        logger.info("[RAGGenerator] 来源摘要构建完成，共 %d 条来源", len(sources))
        for s in sources:
            logger.info("[RAGGenerator]   来源#%d: %s | 页码: %s | rerank=%.1f | confidence=%s",
                         s["index"], s["source_file"], s["pages"],
                         s["scores"]["rerank"], s["scores"]["confidence"])

        return sources

    def query(self, query, company_name=None, top_n=RERANK_TOP_N, mentioned_companies=None, intent=None, extracted_years=None):
        logger.info("=" * 60)
        logger.info("[RAGGenerator] 开始 RAG 问答流程")
        logger.info("[RAGGenerator] 查询: '%s'", query)
        logger.info("[RAGGenerator] 指定公司: %s", company_name or "全部")
        logger.info("[RAGGenerator] 提及公司: %s", mentioned_companies or "未指定")
        logger.info("[RAGGenerator] 意图: %s", intent or "未指定")
        logger.info("[RAGGenerator] 提取年份: %s", extracted_years or "未指定")
        logger.info("[RAGGenerator] 重排返回条数: %d", top_n)
        logger.info("=" * 60)

        retriever = self._get_retriever()
        logger.info("[RAGGenerator] 阶段1: 混合检索 + gte-rerank-v2 重排")
        retrieved_results = retriever.search(query, company_name=company_name, top_n=top_n,
                                              mentioned_companies=mentioned_companies, intent=intent,
                                              extracted_years=extracted_years)

        if not retrieved_results:
            logger.warning("[RAGGenerator] 检索无结果，返回空答案")
            return {
                "answer": "抱歉，未检索到与您问题相关的文档内容，无法回答该问题。",
                "sources": [],
                "query": query,
                "company_name": company_name,
                "retrieved_count": 0,
            }

        logger.info("[RAGGenerator] 阶段2: 构建 LLM 上下文")
        context, used_count = self._build_context(retrieved_results)

        logger.info("[RAGGenerator] 阶段3: 构建 Prompt")
        conversation_context = ""
        if self.conversation_manager:
            conversation_context = self.conversation_manager.get_context_string()
            if conversation_context:
                logger.info("[RAGGenerator] 注入对话历史上下文 (%d 字符)", len(conversation_context))
        if intent == "comparison":
            prompt = self._build_comparison_prompt(query, context, conversation_context)
            logger.info("[RAGGenerator] 使用对比分析 Prompt")
        elif intent == "financial_data":
            prompt = self._build_financial_data_prompt(query, context, conversation_context)
            logger.info("[RAGGenerator] 使用财务数据专用 Prompt")
        elif intent == "trend":
            prompt = self._build_trend_prompt(query, context, conversation_context)
            logger.info("[RAGGenerator] 使用趋势分析专用 Prompt")
        elif intent == "business_analysis":
            prompt = self._build_business_analysis_prompt(query, context, conversation_context)
            logger.info("[RAGGenerator] 使用业务分析专用 Prompt")
        else:
            prompt = self._build_prompt(query, context, conversation_context)
            logger.info("[RAGGenerator] 使用通用 Prompt")

        logger.info("[RAGGenerator] 阶段4: LLM 生成答案")
        answer = self._generate_answer(prompt)

        logger.info("[RAGGenerator] 阶段5: 构建来源摘要")
        sources = self._build_sources_summary(retrieved_results)

        result = {
            "answer": answer,
            "sources": sources,
            "query": query,
            "company_name": company_name,
            "retrieved_count": len(retrieved_results),
            "context_used_count": used_count,
        }

        logger.info("=" * 60)
        logger.info("[RAGGenerator] RAG 问答流程完成")
        logger.info("[RAGGenerator] 答案长度: %d 字符", len(answer))
        logger.info("[RAGGenerator] 来源数: %d, 实际使用: %d", len(sources), used_count)
        logger.info("[RAGGenerator] 答案预览: %s",
                     answer[:100] + "..." if len(answer) > 100 else answer)
        logger.info("=" * 60)

        return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="混合检索与 RAG 生成工具")
    parser.add_argument("--query", type=str, required=True, help="查询文本")
    parser.add_argument("--company", type=str, default=None, help="限定公司名（可选）")
    parser.add_argument("--top-n", type=int, default=RERANK_TOP_N, help="重排后返回条数")
    parser.add_argument("--generate", action="store_true", help="启用 RAG 生成模式（检索+生成完整答案）")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    vector_db_dir = project_root / "data" / "stock_data" / "databases" / "vector_dbs"

    if args.generate:
        generator = RAGGenerator(vector_db_dir)
        result = generator.query(args.query, company_name=args.company, top_n=args.top_n)

        print("\n" + "=" * 80)
        print("RAG 生成结果")
        print("=" * 80)
        print(f"\n问题: {result['query']}")
        if result['company_name']:
            print(f"限定公司: {result['company_name']}")
        print(f"\n答案:\n{result['answer']}")
        print(f"\n--- 来源信息（共 {len(result['sources'])} 条，实际使用 {result.get('context_used_count', '?')} 条）---")
        for s in result['sources']:
            pages_str = f"第{s['pages'][0]}-{s['pages'][-1]}页" if s['pages'] and len(s['pages']) >= 2 else (
                f"第{s['pages'][0]}页" if s['pages'] else "页码未知"
            )
            print(f"  [来源{s['index']}] {s['company_name']} | {s['source_file']} | {pages_str} | "
                  f"hybrid={s['scores']['hybrid']:.4f} | rerank={s['scores']['rerank']:.1f} | "
                  f"confidence={s['scores']['confidence']}")
    else:
        retriever = HybridRetriever(vector_db_dir)
        results = retriever.search(args.query, company_name=args.company, top_n=args.top_n)

        print(f"\n检索结果（共 {len(results)} 条）：")
        print("-" * 80)
        for i, r in enumerate(results):
            print(f"\n[{i + 1}] 来源: {r['source_file']} | 页码: {r['pages']} | 公司: {r['company_name']}")
            print(f"    分数: hybrid={r['scores']['hybrid']}, rerank={r['scores']['rerank']}, confidence={r['scores']['confidence']}")
            text_preview = r["parent_text"][:200].replace("\n", " ")
            print(f"    文本预览: {text_preview}...")
