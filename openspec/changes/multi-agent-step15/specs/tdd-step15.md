# TDD 测试用例: 文档类型标签打标与检索加权（阶段十五）

> 编码: UTF-8
> 约定: <span style="color:red">红色</span> = 未通过, <span style="color:green">绿色</span> = 已通过

---

## 一、测试文件规划

| 文件 | 测试范围 |
|------|---------|
| `tests/tdd_multi_agent_step15.py` | SP15-A ~ SP15-I（Python unittest，mock / 纯函数，不依赖 LLM API） |

---

## 二、测试用例

### SP15-A: `classify_doc_tags` 分类规则

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-15-A-01 | 年报 | `classify_doc_tags("移动2024年度报告.pdf")` | `["annual_report"]` | <span style="color:green">GREEN</span> |
| TC-15-A-02 | 研报 | `classify_doc_tags("国信证券_中芯国际.pdf")` | `["research_report"]` | <span style="color:green">GREEN</span> |
| TC-15-A-03 | 纪要 | `classify_doc_tags("中芯国际机构调研纪要.pdf")` | `["meeting_minutes"]` | <span style="color:green">GREEN</span> |
| TC-15-A-04 | 其他 | `classify_doc_tags("某文件.pdf")` | `["other"]` | <span style="color:green">GREEN</span> |

---

### SP15-B: ingestion 读 tags

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-15-B-01 | collect_chunks 带 tags | 构造含 metainfo.tags 的 chunked JSON，调用 `collect_chunks_by_company` | 每个 child_chunk 含 `tags` 且等于 metainfo.tags | <span style="color:green">GREEN</span> |
| TC-15-B-02 | metadata 写 tags | 构造带 tags 的 child_chunks，验证 `build_company_index` 的 metadata 组装含 tags | metadata 条目含 `tags` | <span style="color:green">GREEN</span> |

---

### SP15-C: 检索结果带 tags

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-15-C-01 | 结果 dict 含 tags | mock metadata 带 tags，调用 search 结果组装 | 结果 dict 含 `"tags": ["annual_report"]` | <span style="color:green">GREEN</span> |

---

### SP15-D: `_merge_results` 保留 tags

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-15-D-01 | 合并保留 tags | 构造带 tags 的 vector/bm25 结果，调用 `_merge_results` | 合并结果含原 tags | <span style="color:green">GREEN</span> |

---

### SP15-E: `_classify_doc_type` 类型判定

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-15-E-01 | tags 优先 | `_classify_doc_type("国信证券.pdf", ["annual_report"])` | `"annual_report"` | <span style="color:green">GREEN</span> |
| TC-15-E-02 | 文件名回退 | `_classify_doc_type("国信证券.pdf", None)` | `"research_report"` | <span style="color:green">GREEN</span> |

---

### SP15-F: `_compute_source_authority_boost` 年报加成

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-15-F-01 | 年报+财务数字 | 构造 `tags=["annual_report"]` 且 parent_text 含「亿元」的结果 | 返回 0.10 | <span style="color:green">GREEN</span> |

---

### SP15-G: `_ensure_annual_report_coverage` 保底

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-15-G-01 | 无年报时补年报 | 构造 results 全为研报、all_scored 含年报，调用保底 | 返回结果含年报来源 | <span style="color:green">GREEN</span> |

---

### SP15-H: `_format_results` 输出 doc_type

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-15-H-01 | 中文标签 | 构造 tags=["annual_report"] 的结果调用 `_format_results` | doc_type = "年报" | <span style="color:green">GREEN</span> |

---

### SP15-I: `/api/retrieve` 响应模型暴露 tags

| 编号 | 用例名称 | 测试步骤 | 预期结果 | 状态 |
|:--:|------|------|------|:--:|
| TC-15-I-01 | 响应模型含 tags | 构造含 tags 的 dict 用 `RetrieveResultItem.model_validate` 校验并 dump | tags 字段存在且等于 `["annual_report"]` | <span style="color:green">GREEN</span> |

---

## 三、测试统计

| 规范 | 测试用例数 | 已通过 | 未通过 |
|------|:--:|:--:|:--:|
| SP15-A | 4 | 4 | 0 |
| SP15-B | 2 | 2 | 0 |
| SP15-C | 1 | 1 | 0 |
| SP15-D | 1 | 1 | 0 |
| SP15-E | 2 | 2 | 0 |
| SP15-F | 1 | 1 | 0 |
| SP15-G | 1 | 1 | 0 |
| SP15-H | 1 | 1 | 0 |
| SP15-I | 1 | 1 | 0 |
| **合计** | **14** | **14** | **0** |
