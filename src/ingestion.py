"""
向量数据库构建工具

按公司名分库构建 FAISS 索引，实现 Small-to-Big 检索策略：
  - 子块 Embedding → FAISS 向量索引
  - 父块完整文本 → parent_texts.json
  - 子块元数据 → metadata.json
  - 公司注册表 → company_registry.json

命令行用法：
  python src/ingestion.py                          # 构建所有未建索引的公司
  python src/ingestion.py --company 中芯国际        # 仅构建指定公司
  python src/ingestion.py --company 中芯国际 --rebuild  # 重建指定公司索引
  python src/ingestion.py --update                  # 增量更新所有公司
  python src/ingestion.py --status                  # 查看索引状态
"""

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import faiss
import numpy as np
import tiktoken

from utils import get_api_key

from retrieval import preprocess_table_text

ENCODING = tiktoken.get_encoding("cl100k_base")
MAX_INPUT_TOKENS = 2048


EMBEDDING_MODEL = "text-embedding-v3"
EMBEDDING_DIM = 1024
BATCH_SIZE = 10


def load_registry(registry_path):
    registry_path = Path(registry_path)
    if registry_path.exists():
        return json.loads(registry_path.read_text(encoding="utf-8"))
    return {"companies": {}}


def save_registry(registry, registry_path):
    registry_path = Path(registry_path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def get_embeddings_batch(texts, api_key):
    import dashscope
    dashscope.api_key = api_key

    processed_texts = [preprocess_table_text(t) for t in texts]

    resp = dashscope.TextEmbedding.call(
        model=EMBEDDING_MODEL,
        input=processed_texts,
        timeout=30,
    )

    if resp.status_code != 200:
        raise Exception(f"Embedding API 调用失败: {resp.status_code} - {resp.message}")

    embeddings = []
    for item in resp.output["embeddings"]:
        embeddings.append(item["embedding"])
    return embeddings


def get_embeddings_with_retry(texts, api_key, max_retries=3):
    for attempt in range(max_retries):
        try:
            return get_embeddings_batch(texts, api_key)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"    [重试] 第 {attempt + 1} 次失败: {e}，{wait} 秒后重试", flush=True)
                time.sleep(wait)
            else:
                raise


def collect_chunks_by_company(chunked_dir):
    chunked_dir = Path(chunked_dir)
    company_data = {}

    for jf in sorted(chunked_dir.glob("*.json")):
        data = json.loads(jf.read_text(encoding="utf-8"))
        metainfo = data["metainfo"]
        company_name = metainfo.get("company_name", "").strip()
        if not company_name:
            print(f"  [警告] {jf.name} 缺少 company_name，跳过")
            continue

        if company_name not in company_data:
            company_data[company_name] = {
                "child_chunks": [],
                "parent_texts": {},
                "source_files": set(),
            }

        for parent in data["content"]["parent_chunks"]:
            parent_id = parent["id"]
            global_parent_key = f"{jf.stem}::{parent_id}"
            company_data[company_name]["parent_texts"][global_parent_key] = parent["text"]

            pages = parent.get("pages", None)
            source_file = parent.get("source_file", jf.stem + ".pdf")
            company_data[company_name]["source_files"].add(source_file)

            for child in parent["child_chunks"]:
                child_hash = hashlib.sha1(child["text"].encode("utf-8")).hexdigest()[:12]
                company_data[company_name]["child_chunks"].append({
                    "child_id": child["id"],
                    "parent_key": global_parent_key,
                    "parent_id": parent_id,
                    "source_file": source_file,
                    "pages": pages,
                    "company_name": company_name,
                    "hash": child_hash,
                    "text": child["text"],
                })

    for cn in company_data:
        company_data[cn]["source_files"] = sorted(company_data[cn]["source_files"])

    return company_data


def truncate_text_to_tokens(text, max_tokens=MAX_INPUT_TOKENS):
    tokens = ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = ENCODING.decode(tokens[:max_tokens])
    return truncated


def build_bm25_index(child_chunks):
    import jieba
    from rank_bm25 import BM25Okapi

    # 强制重新初始化 jieba，确保用户词典生效
    jieba.re_initialized = False
    dict_path = Path(__file__).resolve().parent.parent / "config" / "financial_dict.txt"
    print(f"    [BM25构建] 加载财务词典: {dict_path}", flush=True)
    print(f"    [BM25构建] 词典文件存在: {dict_path.exists()}", flush=True)
    jieba.load_userdict(str(dict_path))

    # 验证词典是否生效
    test_tokens = list(jieba.cut("营业收入"))
    print(f"    [BM25构建] 词典加载后分词测试: '营业收入' -> {test_tokens}", flush=True)
    if "营业收入" not in test_tokens:
        print(f"    [BM25构建] 警告: 财务词典未生效，'营业收入'被分词为: {test_tokens}，尝试强制加载", flush=True)
        jieba.add_word("营业收入", freq=1000, tag="n")
        jieba.add_word("归母净利润", freq=1000, tag="n")
        jieba.add_word("扣非净利润", freq=1000, tag="n")
        jieba.add_word("同比增长", freq=1000, tag="n")
        jieba.add_word("主营业务收入", freq=1000, tag="n")
        jieba.add_word("营业总收入", freq=1000, tag="n")
        jieba.add_word("资产负债率", freq=1000, tag="n")
        jieba.add_word("净资产收益率", freq=1000, tag="n")
        jieba.add_word("经营活动现金流", freq=1000, tag="n")
        jieba.add_word("自由现金流", freq=1000, tag="n")
        jieba.add_word("综合毛利率", freq=1000, tag="n")
        jieba.add_word("销售毛利率", freq=1000, tag="n")
        jieba.add_word("研发费用", freq=1000, tag="n")
        jieba.add_word("现金分红", freq=1000, tag="n")
        jieba.add_word("移动用户", freq=1000, tag="n")
        jieba.add_word("宽带用户", freq=1000, tag="n")
        jieba.add_word("5G用户", freq=1000, tag="n")

    test_tokens2 = list(jieba.cut("营业收入"))
    print(f"    [BM25构建] 最终分词验证: '营业收入' -> {test_tokens2}", flush=True)

    # 额外验证：对包含"营业收入"的子块抽样检查分词
    sample_count = 0
    for c in child_chunks:
        if "营业收入" in c["text"] and sample_count < 3:
            tokens = list(jieba.cut(c["text"]))
            has_full = "营业收入" in tokens
            print(f"    [BM25构建] 抽样验证 pk={c.get('parent_key', 'N/A')}: '营业收入'完整词={has_full}, 分词片段={tokens[:15]}...", flush=True)
            sample_count += 1

    tokenized_corpus = []
    for c in child_chunks:
        tokens = list(jieba.cut(c["text"]))
        tokenized_corpus.append(tokens)

    bm25 = BM25Okapi(tokenized_corpus)

    # 构建后验证：检查索引中"营业收入"完整词的文档数
    yingye_shouru_count = sum(1 for df in bm25.doc_freqs if "营业收入" in df)
    yingye_count = sum(1 for df in bm25.doc_freqs if "营业" in df)
    print(f"    [BM25构建] 索引验证: '营业收入'完整词文档数={yingye_shouru_count}, '营业'文档数={yingye_count}", flush=True)

    return bm25


def build_faiss_index(child_chunks, api_key):
    texts = []
    for c in child_chunks:
        t = truncate_text_to_tokens(c["text"])
        texts.append(t)
    total = len(texts)
    all_embeddings = []

    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"    共 {total} 个子块，分 {num_batches} 批调用 Embedding API", flush=True)

    for batch_idx in range(num_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total)
        batch_texts = texts[start:end]

        try:
            embeddings = get_embeddings_with_retry(batch_texts, api_key)
            all_embeddings.extend(embeddings)
        except Exception as e:
            print(f"    [失败] 批次 {batch_idx + 1}/{num_batches}: {e}", flush=True)
            for _ in batch_texts:
                all_embeddings.append([0.0] * EMBEDDING_DIM)

        if (batch_idx + 1) % 20 == 0 or batch_idx + 1 == num_batches:
            print(f"    进度: {end}/{total} ({(end/total)*100:.1f}%)", flush=True)

        if batch_idx + 1 < num_batches:
            time.sleep(0.5)

    vectors = np.array(all_embeddings, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    vectors = vectors / norms

    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(vectors)

    return index


def build_company_index(company_name, child_chunks, parent_texts, output_dir, api_key):
    company_dir = Path(output_dir) / company_name
    company_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  [构建] {company_name}: {len(child_chunks)} 个子块", flush=True)

    index = build_faiss_index(child_chunks, api_key)

    faiss_path = company_dir / "index.faiss"
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_faiss = os.path.join(tmp_dir, "index.faiss")
        faiss.write_index(index, tmp_faiss)
        shutil.copy2(tmp_faiss, str(faiss_path))
    print(f"    已保存: {faiss_path}", flush=True)

    metadata = []
    for c in child_chunks:
        metadata.append({
            "child_id": c["child_id"],
            "parent_key": c["parent_key"],
            "parent_id": c["parent_id"],
            "source_file": c["source_file"],
            "pages": c["pages"],
            "company_name": c["company_name"],
            "hash": c["hash"],
        })

    metadata_path = company_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    已保存: {metadata_path}", flush=True)

    parent_texts_path = company_dir / "parent_texts.json"
    parent_texts_path.write_text(json.dumps(parent_texts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    已保存: {parent_texts_path}", flush=True)

    bm25_index = build_bm25_index(child_chunks)
    bm25_path = company_dir / "bm25_index.pkl"
    import pickle
    with open(str(bm25_path), "wb") as f:
        pickle.dump(bm25_index, f)
    print(f"    已保存: {bm25_path}", flush=True)

    return {
        "child_chunk_count": len(child_chunks),
        "parent_chunk_count": len(parent_texts),
        "source_files": [Path(f).name for f in sorted(set(c["source_file"] for c in child_chunks))],
        "embedding_model": EMBEDDING_MODEL,
        "vector_dim": EMBEDDING_DIM,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def show_status(registry_path, vector_db_dir):
    registry = load_registry(registry_path)
    vector_db_dir = Path(vector_db_dir)

    print("\n当前索引状态:")
    print("-" * 70)

    if not registry["companies"]:
        print("  (无索引)")
    else:
        for name, info in registry["companies"].items():
            company_dir = vector_db_dir / name
            index_exists = (company_dir / "index.faiss").exists()
            status = "OK" if index_exists else "索引文件缺失"
            print(f"  {name}")
            print(f"    子块数: {info.get('child_chunk_count', '?')}, "
                  f"父块数: {info.get('parent_chunk_count', '?')}, "
                  f"状态: {status}")
            print(f"    来源文件: {', '.join(info.get('source_files', []))}")
            print(f"    创建时间: {info.get('created_at', '?')}")

    chunked_dir = vector_db_dir.parent / "chunked_reports"
    if chunked_dir.exists():
        company_data = collect_chunks_by_company(chunked_dir)
        unindexed = [cn for cn in company_data if cn not in registry["companies"]]
        if unindexed:
            print(f"\n  未建索引的公司: {', '.join(unindexed)}")

    print("-" * 70)


def main():
    parser = argparse.ArgumentParser(description="向量数据库构建工具")
    parser.add_argument("--company", type=str, default=None, help="仅构建指定公司的索引")
    parser.add_argument("--rebuild", action="store_true", help="重建索引（删除旧索引）")
    parser.add_argument("--update", action="store_true", help="增量更新已有公司索引")
    parser.add_argument("--status", action="store_true", help="查看索引状态")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    chunked_dir = project_root / "data" / "stock_data" / "databases" / "chunked_reports"
    vector_db_dir = project_root / "data" / "stock_data" / "databases" / "vector_dbs"
    registry_path = vector_db_dir / "company_registry.json"

    if args.status:
        show_status(registry_path, vector_db_dir)
        return

    print("=" * 60)
    print("向量数据库构建工具")
    print("=" * 60)

    api_key = get_api_key()
    print(f"[信息] API Key 读取成功 (长度: {len(api_key)})")
    print(f"[信息] Embedding 模型: {EMBEDDING_MODEL} ({EMBEDDING_DIM} 维)")
    print(f"[信息] 批量大小: {BATCH_SIZE} 条/次")

    company_data = collect_chunks_by_company(chunked_dir)
    if not company_data:
        print("[错误] 未找到分块数据，请先运行 text_splitter.py")
        return

    registry = load_registry(registry_path)

    if args.company:
        target_companies = [args.company]
        if args.company not in company_data:
            print(f"[错误] 未找到公司 '{args.company}' 的分块数据")
            print(f"  可用公司: {', '.join(company_data.keys())}")
            return
    elif args.update:
        target_companies = list(registry["companies"].keys())
    else:
        target_companies = list(company_data.keys())

    print(f"[信息] 待处理公司: {', '.join(target_companies)}\n")

    for company_name in target_companies:
        data = company_data[company_name]

        if args.rebuild and company_name in registry["companies"]:
            company_dir = vector_db_dir / company_name
            if company_dir.exists():
                import shutil
                shutil.rmtree(company_dir)
                print(f"  [重建] 已删除 {company_name} 的旧索引", flush=True)
            del registry["companies"][company_name]

        if company_name in registry["companies"] and not args.rebuild:
            print(f"  [跳过] {company_name}: 索引已存在（使用 --rebuild 重建）", flush=True)
            continue

        info = build_company_index(
            company_name,
            data["child_chunks"],
            data["parent_texts"],
            vector_db_dir,
            api_key,
        )
        registry["companies"][company_name] = info

    save_registry(registry, registry_path)

    print("\n" + "=" * 60)
    print("向量数据库构建完成!")
    print(f"索引位置: {vector_db_dir}")
    print(f"注册表: {registry_path}")
    print("=" * 60)

    show_status(registry_path, vector_db_dir)


if __name__ == "__main__":
    main()
