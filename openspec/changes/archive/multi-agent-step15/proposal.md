# 变更提案: 文档类型标签打标与检索加权（阶段十五）

> 编码: UTF-8

---

## 一、变更背景

评测用例 gen-007 暴露数据来源混用问题：查询「中芯国际2024年营业收入相比2023年增长了多少」时：

- 2024 年数据正确取到年报（人民币 578 亿）
- 2023 年数据却取到研报（国信证券，美元列报 630 亿），被误当人民币
- 最终算出 -8.25% 的错误增长率（正确 +27.7%）

**根因**：中芯国际向量库中研报（7 份）远多于年报（1 份），BM25 与向量检索按纯相关性排序时研报占优，年报被淹没。当前「年报优先」仅靠 Prompt 规则 9/10/11（[src/agent_core.py](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/agent_core.py#L196-L197)），无检索层代码实现，无法在数据入口处解决问题。

完整方案见 [_local/blog/Agent项目/后续优化想法/Tags打标传参方案.md](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/_local/blog/Agent项目/后续优化想法/Tags打标传参方案.md)。

## 二、变更目标

1. 在数据拆分阶段（text_splitter.py）自动为文档打文档类型标签（tags）。
2. 标签随整条链路写入 metadata.json，检索时按 tags 做来源加权与年报保底，确保年报数据优先返回。

## 三、变更范围（8 个环节）

| 环节 | 文件 | 改动 |
|------|------|------|
| ① | data/stock_data/subset.csv | 不改（tags 由 file_name 自动推断） |
| ② | src/text_splitter.py | 新增 `classify_doc_tags(file_name)`，metainfo 写入 tags |
| ③ | src/ingestion.py | `collect_chunks_by_company` 读 tags，`build_company_index` 写 metadata.json |
| ④ | src/retrieval.py (VectorRetriever/BM25Retriever) | 检索结果 dict 加 `tags` |
| ⑤ | src/retrieval.py (_merge_results) | 合并结果保留 tags |
| ⑥ | src/retrieval.py (加权/保底) | 新增 `_classify_doc_type` / `_compute_source_authority_boost` / `_ensure_annual_report_coverage`，rerank 阶段年报加分 |
| ⑦ | src/tools/retrieve_tool.py | `_format_results` 输出 doc_type 中文标签 |
| ⑧ | src/api_service.py | `RetrieveResultItem` 响应模型暴露 `tags` 字段（检索接口透出打标结果） |

## 四、技术决策

1. **标签分类规则**（`classify_doc_tags`，按文件名子串匹配）：

   | 标签 | 匹配子串 |
   |------|---------|
   | `annual_report` | 年度报告 / 年报 / 【财报】 |
   | `research_report` | 证券 / 研报 / 研究报 |
   | `meeting_minutes` | 调研纪要 / 会议纪要 / 投资者关系 |
   | `other` | 以上均不匹配 |

2. **tags 存储格式**：单元素列表，如 `["annual_report"]`（兼容检索层 `meta.get("tags", [])` 语义）。

3. **三层防线**：
   - Hybrid 融合阶段：`_compute_source_authority_boost` 对年报 + 含财务数字的块给予 `ANNUAL_REPORT_BOOST_HYBRID = 0.10` 加成。
   - Rerank 阶段：`_gte_rerank` / `_fallback_rerank` 对年报结果 rerank 分额外加 `ANNUAL_REPORT_BOOST_RERANK = 1.5`。
   - 保底机制：`_ensure_annual_report_coverage` 当某公司结果中无年报来源时，从候选中补充最高分年报块。

4. **旧数据兼容**：metadata.json 无 tags 时 `meta.get("tags", [])` 返回空列表；`_classify_doc_type` 回退到文件名推断，不报错。

## 五、测试策略（TDD 先红后绿）

- **SP15-A**：`classify_doc_tags` 分类规则（4 项）。
- **SP15-B**：ingestion 读 tags 并写入 child_chunks / metadata（2 项）。
- **SP15-C**：检索结果 dict 带 tags（1 项，mock metadata）。
- **SP15-D**：`_merge_results` 保留 tags（1 项）。
- **SP15-E**：`_classify_doc_type` 优先 tags、回退文件名（2 项）。
- **SP15-F**：`_compute_source_authority_boost` 年报加成（1 项）。
- **SP15-G**：`_ensure_annual_report_coverage` 保底（1 项）。
- **SP15-H**：`_format_results` 输出 doc_type 中文标签（1 项）。
- **SP15-I**：`/api/retrieve` 响应模型 `RetrieveResultItem` 暴露 tags（1 项）。

合计 14 项，Python unittest，不依赖 LLM API（检索层用 mock / 纯函数）。

## 六、验收标准

- `tests/tdd_multi_agent_step15.py` 全部 14 项通过。
- `python tests/run_all.py --skip-llm` 运行新测试且无回归。
- 与阶段十四（页码修复）共享一次 `text_splitter.py + ingestion.py --rebuild` 重建，重建后 `metadata.json` 含 `tags` 字段。
