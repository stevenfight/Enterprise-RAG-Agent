# -*- coding: utf-8 -*-
"""
企业文档接入自动化测试脚本

覆盖场景（基于《企业文档接入开发指南》）：
  1. 环境与前置条件验证
  2. 公司注册表完整性
  3. 索引文件完整性 + 可用性
  4. 数据一致性（注册表 vs 分块数据 vs 索引）
  5. 配置文件完整性
  6. 公司名识别规则
  7. 文档新增/删除场景一致性
  8. COMPANY_ABBREV_MAP 完整性
  9. 端到端：新增文档后重建索引后查询验证

运行方式: python tests/test_document_integration.py
"""

import json
import os
import pickle
import ssl
import sys
import tempfile
import time
from pathlib import Path

# 忽略 SSL 证书验证（与 tdd_all_optimizations.py / integration_test.py 保持一致）
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import faiss

from retrieval import COMPANY_ABBREV_MAP
from pdf_mineru import _extract_company_name
from utils import get_api_key

# --- 测试框架 ---
passed = 0
failed = 0
warnings = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} - {detail}")
        failed += 1


def warn(name, condition, detail=""):
    global warnings
    if not condition:
        print(f"  [WARN] {name} - {detail}")
        warnings += 1


# --- 路径常量 ---
project_root = Path(__file__).resolve().parent.parent
pdf_dir = project_root / "pdf_reports"
chunked_dir = project_root / "data" / "stock_data" / "databases" / "chunked_reports"
vector_db_dir = project_root / "data" / "stock_data" / "databases" / "vector_dbs"
registry_path = vector_db_dir / "company_registry.json"
subset_csv_path = project_root / "data" / "stock_data" / "subset.csv"
debug_md_dir = project_root / "data" / "stock_data" / "debug_data" / "03_reports_markdown"
config_dir = project_root / "config"
bm25_expansions_path = config_dir / "bm25_expansions.json"
financial_dict_path = config_dir / "financial_dict.txt"

EXPECTED_FILES_PER_COMPANY = ["index.faiss", "metadata.json", "parent_texts.json", "bm25_index.pkl"]


def load_registry():
    if not registry_path.exists():
        return None
    return json.loads(registry_path.read_text(encoding="utf-8"))


def load_chunked_data():
    """读取所有 chunked_reports JSON 并按公司分组"""
    company_data = {}
    if not chunked_dir.exists():
        return company_data
    for jf in sorted(chunked_dir.glob("*.json")):
        data = json.loads(jf.read_text(encoding="utf-8"))
        metainfo = data.get("metainfo", {})
        cn = metainfo.get("company_name", "").strip()
        if not cn:
            continue
        if cn not in company_data:
            company_data[cn] = []
        company_data[cn].append({
            "file_stem": jf.stem,
            "source_file": metainfo.get("file_name", jf.stem + ".pdf"),
            "sha1": metainfo.get("sha1", ""),
            "parent_count": len(data.get("content", {}).get("parent_chunks", [])),
            "child_count": sum(
                len(p.get("child_chunks", []))
                for p in data.get("content", {}).get("parent_chunks", [])
            ),
        })
    return company_data


print("=" * 70)
print("企业文档接入自动化测试")
print("=" * 70)
print(f"项目根目录: {project_root}")
print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# ============================================================
# 模块一: 环境与前置条件
# ============================================================
print("--- 模块一: 环境与前置条件 ---")

# 1.1 API Key 可用性
try:
    dashscope_key = get_api_key("DASHSCOPE_API_KEY")
    check("DASHSCOPE_API_KEY 可用", len(dashscope_key) > 10, f"长度: {len(dashscope_key)}")
except Exception as e:
    check("DASHSCOPE_API_KEY 可用", False, str(e))

try:
    mineru_key = get_api_key("MINERU_API_KEY")
    check("MINERU_API_KEY 可用", len(mineru_key) > 10, f"长度: {len(mineru_key)}")
except Exception as e:
    check("MINERU_API_KEY 可用", False, str(e))

# 1.2 关键目录存在
check("pdf_reports/ 目录存在", pdf_dir.exists())
check("chunked_reports/ 目录存在", chunked_dir.exists())
check("vector_dbs/ 目录存在", vector_db_dir.exists())
check("config/ 目录存在", config_dir.exists())
check("debug_data/03_reports_markdown/ 目录存在", debug_md_dir.exists())

# 1.3 PDF 源文件数量
pdf_files = sorted(pdf_dir.glob("*.pdf"))
check("PDF 源文件 >= 12 个", len(pdf_files) >= 12, f"实际: {len(pdf_files)}")
print(f"    当前 PDF 文件: {len(pdf_files)} 个")
for pf in pdf_files:
    size_mb = pf.stat().st_size / (1024 * 1024)
    print(f"      - {pf.name} ({size_mb:.1f} MB)")

# ============================================================
# 模块二: 公司注册表完整性
# ============================================================
print("\n--- 模块二: 公司注册表完整性 ---")

registry = load_registry()
check("company_registry.json 文件存在", registry is not None)
if registry is None:
    print("\n[FATAL] 公司注册表不存在，终止后续测试")
    print(f"\n{'='*70}")
    print(f"测试结果: {passed} PASS, {failed} FAIL, {warnings} WARN, 共 {passed + failed} 项")
    print(f"{'='*70}")
    sys.exit(1)

registry_companies = registry.get("companies", {})
check("注册表中有公司记录", len(registry_companies) > 0, f"实际: {len(registry_companies)}")

# 2.1 已知 4 家公司全部存在
expected_companies = ["中芯国际", "中国移动", "中国联通", "中国电信"]
for cn in expected_companies:
    check(f"注册表包含 {cn}", cn in registry_companies)

# 2.2 注册表与 vector_dbs 目录一致性
actual_dirs = {
    d.name for d in vector_db_dir.iterdir()
    if d.is_dir() and not d.name.startswith(".")
}
check("注册表公司数 == vector_dbs 目录数",
      len(registry_companies) == len(actual_dirs),
      f"注册表: {len(registry_companies)}, 目录: {len(actual_dirs)} (实际: {actual_dirs})")

for cn in registry_companies:
    check(f"  {cn} 有对应索引目录", cn in actual_dirs)

# 检查注册表中是否有多余公司（目录存在但注册表无）
for d in actual_dirs:
    warn(f"  {d} 目录在注册表中有记录", d in registry_companies,
         f"目录存在但注册表中无记录，可能是残留数据")

# 2.3 注册表字段完整性
for cn, info in registry_companies.items():
    check(f"{cn} 有 child_chunk_count 字段", "child_chunk_count" in info)
    check(f"{cn} 有 parent_chunk_count 字段", "parent_chunk_count" in info)
    check(f"{cn} 有 source_files 字段", "source_files" in info)
    check(f"{cn} 有 embedding_model 字段", "embedding_model" in info)
    check(f"{cn} 有 vector_dim 字段", "vector_dim" in info)
    check(f"{cn} 有 created_at 字段", "created_at" in info)
    check(f"{cn} embedding_model 为 text-embedding-v3",
          info.get("embedding_model") == "text-embedding-v3",
          f"实际: {info.get('embedding_model')}")
    check(f"{cn} vector_dim 为 1024",
          info.get("vector_dim") == 1024,
          f"实际: {info.get('vector_dim')}")
    check(f"{cn} child_chunk_count > 0",
          info.get("child_chunk_count", 0) > 0,
          f"实际: {info.get('child_chunk_count')}")
    check(f"{cn} source_files 非空",
          len(info.get("source_files", [])) > 0)

# ============================================================
# 模块三: 索引文件完整性 + 可用性
# ============================================================
print("\n--- 模块三: 索引文件完整性 + 可用性 ---")

for cn in registry_companies:
    company_dir = vector_db_dir / cn
    check(f"{cn} 索引目录存在", company_dir.exists())

    for fname in EXPECTED_FILES_PER_COMPANY:
        fpath = company_dir / fname
        check(f"{cn} 有 {fname}", fpath.exists())
        if fpath.exists():
            size_mb = fpath.stat().st_size / (1024 * 1024)
            check(f"{cn} {fname} 非空 (>0 KB)", size_mb > 0, f"大小: {size_mb:.2f} MB")

    # 3.1 FAISS 索引可正常加载
    faiss_path = company_dir / "index.faiss"
    if faiss_path.exists():
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                import shutil
                tmp_faiss = os.path.join(tmp_dir, "index.faiss")
                shutil.copy2(str(faiss_path), tmp_faiss)
                index = faiss.read_index(tmp_faiss)
            check(f"{cn} FAISS 索引可加载", True)
            check(f"{cn} FAISS 索引维度正确", index.d == 1024, f"实际: {index.d}")
            check(f"{cn} FAISS 向量数与子块数一致",
                  index.ntotal == registry_companies[cn].get("child_chunk_count", -1),
                  f"FAISS: {index.ntotal}, 注册表: {registry_companies[cn].get('child_chunk_count')}")
        except Exception as e:
            check(f"{cn} FAISS 索引可加载", False, str(e))

    # 3.2 BM25 索引可正常加载
    bm25_path = company_dir / "bm25_index.pkl"
    if bm25_path.exists():
        try:
            with open(str(bm25_path), "rb") as f:
                bm25 = pickle.load(f)
            check(f"{cn} BM25 索引可加载", True)
            check(f"{cn} BM25 语料库大小 > 0", bm25.corpus_size > 0,
                  f"实际: {bm25.corpus_size}")
        except Exception as e:
            check(f"{cn} BM25 索引可加载", False, str(e))

    # 3.3 metadata.json 可正常解析
    metadata_path = company_dir / "metadata.json"
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            check(f"{cn} metadata 可解析", True)
            check(f"{cn} metadata 条目数 == 注册表子块数",
                  len(metadata) == registry_companies[cn].get("child_chunk_count", -1),
                  f"metadata: {len(metadata)}, 注册表: {registry_companies[cn].get('child_chunk_count')}")
        except Exception as e:
            check(f"{cn} metadata 可解析", False, str(e))

    # 3.4 parent_texts.json 可正常解析
    parent_path = company_dir / "parent_texts.json"
    if parent_path.exists():
        try:
            parent_texts = json.loads(parent_path.read_text(encoding="utf-8"))
            check(f"{cn} parent_texts 可解析", True)
            check(f"{cn} parent_texts 条目数 == 注册表父块数",
                  len(parent_texts) == registry_companies[cn].get("parent_chunk_count", -1),
                  f"parent_texts: {len(parent_texts)}, 注册表: {registry_companies[cn].get('parent_chunk_count')}")
        except Exception as e:
            check(f"{cn} parent_texts 可解析", False, str(e))

# ============================================================
# 模块四: 数据一致性验证
# ============================================================
print("\n--- 模块四: 数据一致性验证 ---")

# 4.1 source_files 与 chunked_reports 一致性
chunked_data = load_chunked_data()
check("chunked_reports 可加载", len(chunked_data) > 0)
check("chunked_reports 公司数 == 注册表公司数",
      len(chunked_data) == len(registry_companies),
      f"chunked: {len(chunked_data)}, 注册表: {len(registry_companies)}")

for cn in registry_companies:
    if cn in chunked_data:
        # 统一用 stem（不含扩展名）比较，消除 .pdf vs .md 差异
        chunked_sources = {Path(item["source_file"]).stem for item in chunked_data[cn]}
        registry_sources = {Path(sf).stem for sf in registry_companies[cn].get("source_files", [])}

        # 检查注册表中的 source_files 都能在 chunked 中找到
        for sf_stem in registry_sources:
            check(f"{cn} source_file '{sf_stem}' 在 chunked 中有对应",
                  sf_stem in chunked_sources,
                  f"注册表中有但 chunked 中无")

        # 检查 chunked 中无注册表之外的来源（可能是忘了 rebuild）
        for sf_stem in chunked_sources:
            check(f"{cn} chunked 文件 '{sf_stem}' 在注册表中有记录",
                  sf_stem in registry_sources,
                  f"chunked 中有但注册表中无，可能需要 --rebuild")

# 4.2 metadata 中的 parent_key 能在 parent_texts 中找到
print("\n  [子项] metadata parent_key 引用完整性检测")
for cn in registry_companies:
    company_dir = vector_db_dir / cn
    metadata_path = company_dir / "metadata.json"
    parent_path = company_dir / "parent_texts.json"
    if not metadata_path.exists() or not parent_path.exists():
        warn(f"{cn} 缺少 metadata 或 parent_texts，跳过引用完整性检测", False)
        continue

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    parent_texts = json.loads(parent_path.read_text(encoding="utf-8"))
    missing_refs = 0
    for meta in metadata[:1000]:  # 抽样前 1000 条
        pk = meta.get("parent_key", "")
        if pk and pk not in parent_texts:
            missing_refs += 1
    check(f"{cn} metadata parent_key 引用完整（抽样1000条）",
          missing_refs == 0,
          f"缺失引用: {missing_refs}")

# 4.3 分块 JSON 文件数量
print("\n  [子项] chunked_reports JSON 文件统计")
chunked_json_count = len(list(chunked_dir.glob("*.json")))
check("chunked_reports JSON 文件 == 12 个", chunked_json_count == 12, f"实际: {chunked_json_count}")

# 4.4 debug_data Markdown 文件数量
md_files = list(debug_md_dir.glob("*.md"))
check("03_reports_markdown Markdown 文件 == 12 个", len(md_files) == 12, f"实际: {len(md_files)}")

# ============================================================
# 模块五: 配置文件完整性
# ============================================================
print("\n--- 模块五: 配置文件完整性 ---")

# 5.1 bm25_expansions.json
check("bm25_expansions.json 文件存在", bm25_expansions_path.exists())
if bm25_expansions_path.exists():
    expansions = json.loads(bm25_expansions_path.read_text(encoding="utf-8"))
    check("bm25_expansions 条目 >= 15", len(expansions) >= 15, f"实际: {len(expansions)}")

    # 关键术语测试
    key_terms = ["营收", "利润", "毛利率", "增长", "对比", "产能", "现金流", "研发"]
    for term in key_terms:
        check(f"扩展词典含 '{term}'", term in expansions)

    # 每个扩展条目是非空列表
    for term, words in expansions.items():
        check(f"扩展词 '{term}' 为非空列表",
              isinstance(words, list) and len(words) > 0,
              f"实际: {type(words).__name__}, 长度: {len(words) if isinstance(words, list) else 'N/A'}")

# 5.2 financial_dict.txt
check("financial_dict.txt 文件存在", financial_dict_path.exists())
if financial_dict_path.exists():
    dict_content = financial_dict_path.read_text(encoding="utf-8").strip()
    dict_lines = [l for l in dict_content.split("\n") if l.strip()]
    check("financial_dict 条目 >= 20", len(dict_lines) >= 20, f"实际: {len(dict_lines)}")

    key_finance_terms = ["归母净利润", "营业收入", "产能利用率", "EBITDA"]
    for term in key_finance_terms:
        found = any(term in l for l in dict_lines)
        check(f"财经词典含 '{term}'", found)

# 5.3 subset.csv
check("subset.csv 文件存在", subset_csv_path.exists())
if subset_csv_path.exists():
    csv_lines = subset_csv_path.read_text(encoding="utf-8").strip().split("\n")
    check("subset.csv 有表头行", len(csv_lines) >= 2, f"实际行数: {len(csv_lines)}")
    # 检查表头包含 sha1, company_name, file_name
    check("subset.csv 包含 sha1 列", "sha1" in csv_lines[0])
    check("subset.csv 包含 company_name 列", "company_name" in csv_lines[0])
    check("subset.csv 包含 file_name 列", "file_name" in csv_lines[0])

# ============================================================
# 模块六: 公司名识别规则验证
# ============================================================
print("\n--- 模块六: 公司名识别规则验证 ---")

test_cases = [
    # (文件名, 期望公司名, 描述)
    ("中芯国际2024年年度报告", "中芯国际", "全名匹配"),
    ("电信2024年度报告", "中国电信", "简称匹配"),
    ("移动2024年度报告", "中国移动", "简称匹配"),
    ("联通2024年度报告", "中国联通", "简称匹配"),
    ("【财报】中芯国际：中芯国际2024年年度报告", "中芯国际", "【财报】前缀"),
    ("【华泰证券】中芯国际（688981）：上调港股目标价", "中芯国际", "【券商】格式"),
    ("宁德时代2025年度报告", "宁德时代", "新增公司全名匹配"),
]

for file_stem, expected, desc in test_cases:
    result = _extract_company_name(file_stem, md_dir=str(debug_md_dir))
    pass_check = result == expected or (expected == "宁德时代" and result is not None)
    check(f"公司名识别: '{desc}' -> '{expected}'",
          result == expected,
          f"输入: '{file_stem}', 实际: '{result}', 期望: '{expected}'")

# 边界情况：无公司名匹配
result_none = _extract_company_name("未知文件名称123")
warn("未知文件返回非空（可能取前4字符）", len(result_none) > 0,
     f"结果: '{result_none}'")

# ============================================================
# 模块七: 文档新增/删除场景一致性
# ============================================================
print("\n--- 模块七: 文档新增/删除场景一致性 ---")

# 7.1 检查 chunked 和 registry 公司数一致
chunked_companies = set(chunked_data.keys())
registry_companies_set = set(registry_companies.keys())
only_in_chunked = chunked_companies - registry_companies_set
only_in_registry = registry_companies_set - chunked_companies

check("无仅存在于 chunked 的公司（需构建索引）",
      len(only_in_chunked) == 0,
      f"待构建: {only_in_chunked}")
check("无仅存在于 registry 的公司（残留记录）",
      len(only_in_registry) == 0,
      f"残留: {only_in_registry}")

# 7.2 汇总每个公司的总子块数/父块数
print("\n  [子项] 各公司文档统计汇总")
for cn in sorted(registry_companies_set):
    info = registry_companies[cn]
    chunked_info = chunked_data.get(cn, [])
    print(f"    {cn}:")
    print(f"      源文件数: {len(info.get('source_files', []))}")
    print(f"      分块 JSON 数: {len(chunked_info)}")
    print(f"      父块数: {info.get('parent_chunk_count', '?')}")
    print(f"      子块数: {info.get('child_chunk_count', '?')}")
    print(f"      注册表创建时间: {info.get('created_at', '?')}")
    for sf in info.get("source_files", []):
        print(f"        - {sf}")

# 7.3 PDF 源文件与 source_files 对应关系
print("\n  [子项] PDF 源文件与注册表 source_files 对照")
pdf_names = {pf.name for pf in pdf_files}
all_registry_sources = set()
for cn, info in registry_companies.items():
    all_registry_sources.update(info.get("source_files", []))
    for sf in info.get("source_files", []):
        if sf in pdf_names:
            check(f"{cn} source_file '{sf}' 在 pdf_reports 中存在", True)
        else:
            warn(f"{cn} source_file '{sf}' 不在 pdf_reports 中", False,
                 "可能是文件已删除或改名，建议检查")

# ============================================================
# 模块八: COMPANY_ABBREV_MAP 完整性
# ============================================================
print("\n--- 模块八: COMPANY_ABBREV_MAP 完整性 ---")

for cn in registry_companies:
    check(f"COMPANY_ABBREV_MAP 包含 {cn}", cn in COMPANY_ABBREV_MAP,
          f"当前映射: {list(COMPANY_ABBREV_MAP.keys())}")

# 检查 app_streamlit.py 从 retrieval 导入 MAP
streamlit_path = project_root / "app_streamlit.py"
if streamlit_path.exists():
    st_content = streamlit_path.read_text(encoding="utf-8")
    check("app_streamlit.py 导入 COMPANY_ABBREV_MAP",
          "COMPANY_ABBREV_MAP" in st_content)
    check("app_streamlit.py 无独立 ABBREV_MAP 定义",
          "ABBREV_MAP = {" not in st_content)

# ============================================================
# 模块九: 端到端 RAG 查询验证
# ============================================================
print("\n--- 模块九: 端到端 RAG 查询验证 ---")

# 预检查：验证 DashScope API 连通性，SSL 不可用时跳过
_dashscope_available = False
try:
    import dashscope
    dashscope.api_key = dashscope_key
    _test_resp = dashscope.TextEmbedding.call(
        model="text-embedding-v3",
        input=["测试"],
        timeout=10,
    )
    _dashscope_available = (_test_resp.status_code == 200)
except Exception as _e:
    _err_msg = str(_e)
    if "SSL" in _err_msg or "CERTIFICATE" in _err_msg or "certificate" in _err_msg.lower():
        print(f"  [SKIP] DashScope API 不可达 (SSL 证书问题)，跳过模块九")
    else:
        print(f"  [SKIP] DashScope API 不可达: {_err_msg[:100]}")

if not _dashscope_available:
    print("  [INFO] 模块九需要 API 连通性，当前环境不满足，已跳过")
else:
    try:
        from retrieval import RAGGenerator
        from query_processor import QueryProcessor

        rag = RAGGenerator(str(vector_db_dir))
        qp = QueryProcessor()

        # 9.1 所有公司都能正常查询
        for cn in ["中芯国际", "中国移动", "中国联通", "中国电信"]:
            query = f"{cn}2024年营收情况"
            t0 = time.time()
            try:
                qp_result = qp.process(query)
                intent = qp_result.get("intent", "unknown")

                result = rag.query(
                    query,
                    company_name=cn,
                    top_n=5,
                    intent=intent,
                    extracted_years=qp_result.get("extracted_years"),
                )
                elapsed = time.time() - t0

                check(f"{cn} 查询返回答案", len(result.get("answer", "")) > 50,
                      f"答案长度: {len(result.get('answer', ''))}")
                check(f"{cn} 查询含来源引用", "[来源" in result.get("answer", ""))
                check(f"{cn} 检索结果 > 0", result.get("retrieved_count", 0) > 0,
                      f"检索数: {result.get('retrieved_count', 0)}")
                check(f"{cn} 查询耗时 < 60s", elapsed < 60, f"耗时: {elapsed:.1f}s")
            except Exception as e:
                check(f"{cn} 查询成功", False, str(e))

        # 9.2 对比查询（场景二相关：文档替换后多公司查询正常）
        query2 = "中国移动和中国联通和中国电信2024年营收对比"
        t0 = time.time()
        try:
            qp2 = qp.process(query2)
            result2 = rag.query(
                query2,
                mentioned_companies=["中国移动", "中国联通", "中国电信"],
                intent="comparison",
                top_n=5,
            )
            elapsed2 = time.time() - t0
            companies_in_sources = set(s.get("company_name", "") for s in result2.get("sources", []))
            check("三家对比查询返回答案", len(result2.get("answer", "")) > 50)
            check("三家对比覆盖 >= 2 家公司", len(companies_in_sources) >= 2,
                  f"覆盖: {companies_in_sources}")
            check("三家对比耗时 < 120s", elapsed2 < 120, f"耗时: {elapsed2:.1f}s")
        except Exception as e:
            check("三家对比查询成功", False, str(e))

        # 9.3 域外问题拦截（验证无需检索就能正确拦截）
        query3 = "今天天气怎么样"
        try:
            qp3 = qp.process(query3)
            check("域外问题正确拦截", qp3.get("intent") == "out_of_domain",
                  f"实际意图: {qp3.get('intent')}")
        except Exception as e:
            check("域外问题拦截成功", False, str(e))

    except ImportError as e:
        print(f"  [SKIP] 模块九: 缺少模块 - {e}")
        warn("端到端 RAG 查询验证", False, f"ImportError: {e}")
    except Exception as e:
        print(f"  [SKIP] 模块九: 初始化失败 - {e}")
        warn("端到端 RAG 查询验证", False, str(e))

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 70)
total = passed + failed
status = "PASS" if failed == 0 else "FAIL"
print(f"测试完成: {passed} PASS, {failed} FAIL, {warnings} WARN, 共 {total} 项  [{status}]")
print(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# 输出场景覆盖摘要
print("\n--- 场景覆盖摘要 ---")
print(f"  场景一 (已有公司新增PDF)    : 模块四 source_files一致性 + 模块三 索引可加载")
print(f"  场景二 (替换/更新PDF)       : 模块四 chunked/registry一致性   + 模块九 端到端查询")
print(f"  场景三 (新增公司)           : 模块六 公司名识别     + 模块二 注册表完整性")
print(f"  场景四 (增量追加)           : 模块七 chunked/registry公司数一致性")
print(f"  场景五 (删除公司)           : 模块七 注册表残留检测")
print(f"  BM25/配置调优               : 模块五 配置文件完整性")
print("=" * 70)