# 任务清单: 文档类型标签打标与检索加权（阶段十五）

> 编码: UTF-8

---

## 任务列表

| 序号 | 任务 | 产出 | 状态 |
|:--:|------|------|:--:|
| 1 | 创建 OpenSpec 变更记录 | proposal.md / design.md / tasks.md / specs/tdd-step15.md | 已完成 |
| 2 | 编写 TDD 用例规格（全线标红） | specs/tdd-step15.md | 已完成 |
| 3 | 编写后端单元测试（预期先红） | tests/tdd_multi_agent_step15.py | 已完成 |
| 4 | 运行测试确认红 | 测试输出 | 已完成 |
| 5 | text_splitter 打 tags | src/text_splitter.py | 已完成 |
| 6 | ingestion 读 tags 写 metadata | src/ingestion.py | 已完成 |
| 7 | 检索结果带 tags | src/retrieval.py (VectorRetriever/BM25Retriever) | 已完成 |
| 8 | 合并保留 tags | src/retrieval.py (_merge_results) | 已完成 |
| 9 | 加权与保底 | src/retrieval.py (_classify_doc_type/_compute_source_authority_boost/_ensure_annual_report_coverage) | 已完成 |
| 10 | 输出 doc_type 中文标签 | src/tools/retrieve_tool.py | 已完成 |
| 11 | 运行测试转绿 | 测试输出 | 已完成 |
| 12 | 纳入 run_all.py 回归 | tests/run_all.py | 已完成 |
| 13 | TDD 转绿 + 更新文档 | specs/tdd-step15.md 状态更新 | 已完成 |

---

## 验收标准

- `tests/tdd_multi_agent_step15.py` 全部 14 项用例通过：
  - SP15-A 分类规则 4 项
  - SP15-B ingestion 读 tags 2 项
  - SP15-C 检索结果带 tags 1 项
  - SP15-D 合并保留 tags 1 项
  - SP15-E 类型判定 2 项
  - SP15-F 年报加成 1 项
  - SP15-G 年报保底 1 项
  - SP15-H 中文标签 1 项
  - SP15-I 响应模型暴露 tags 1 项
- `python tests/run_all.py --skip-llm` 可运行新测试且无回归
- 与阶段十四（页码修复）共享一次 `text_splitter.py + ingestion.py --rebuild` 重建
- 重建后 `metadata.json` 含 `tags` 字段，且检索结果 doc_type 正确
