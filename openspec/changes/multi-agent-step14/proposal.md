# 变更提案: 数据来源页码映射修复（阶段十四）

> 编码: UTF-8

---

## 一、变更背景

多 Agent 回答中的「数据来源」页码标注系统性错误：每个 PDF 的所有 chunk 都被标注为该 PDF 的**最后一页**。

实测统计（`chunked_reports/*.json` 的 `pages` 字段）：

| 文档 | 实际页数 | chunk 页码（几乎全部） |
|------|:--:|:--:|
| 移动2024年度报告 | 222 | `[222, 222]` |
| 电信2024年度报告 | 218 | `[218, 218]` |
| 联通2024年度报告 | 216 | `[216, 216]` |
| 中芯国际2024年报 | 222 | `[222, 222]` |
| 各研报 | 29/12/8/6/5 | 全是各自最后一页 |

根因定位在 [src/text_splitter.py](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/text_splitter.py#L101) 的 `build_line_page_map`：markdown 文件路径拼接多了一层 `.parent`。

```python
md_dir = pdf_path.parent.parent.parent / "debug_data" / "03_reports_markdown"
# pdf_path = data/stock_data/pdf_reports/xxx.pdf
# .parent.parent.parent = data            （多跳一层）
# 正确应为 .parent.parent = data/stock_data
```

导致 `md_file` 指向不存在的 `data/debug_data/03_reports_markdown/xxx.md`，`md_text` 恒为空字符串。随后 `line_to_page` 的比例映射失效：

```python
ratio = char_offset / max(len(md_text), 1)   # md_text="" → 除以 1
pdf_char_pos = int(ratio * len(full_text))    # 变成 char_offset × 全文长度，值爆炸
```

`pdf_char_pos` 超出所有页码范围，最终走到 `return page_char_ranges[-1][2]`，永远返回最后一页。

## 二、变更目标

1. 修复 `build_line_page_map` 的 markdown 路径拼接，使 `line_to_page` 能正确读取 markdown 文本，页码映射恢复合理分布。
2. 重建索引后，`metadata.json` 的 `pages` 字段不再恒为最后一页。

## 三、变更范围

- `src/text_splitter.py`：`build_line_page_map` 中 `md_dir` 路径去掉一层 `.parent`。

## 四、技术决策

1. **最小修复**：仅改路径一行，保留现有「字符比例映射」算法（方案 A：近似页码）。
2. 映射为近似值：markdown 与 PDF 提取文本字符分布非线性，页码为「大致准确」而非逐字精确，可满足来源展示需求。
3. 修复后需重新运行 `text_splitter.py` 与 `ingestion.py --rebuild` 才使数据生效（与阶段十五 tags 打标共享一次重建）。

## 五、测试策略（TDD 先红后绿）

- **SP14-A**：`build_line_page_map` 路径修复，用真实 PDF + markdown 数据验证 `line_to_page` 映射恢复合理（3 项）。
- **SP14-B**：`line_to_page` 页码单调性（1 项）。

合计 4 项，Python unittest，不依赖 LLM API（依赖本地 PDF/markdown 测试数据）。

## 六、验收标准

- `tests/tdd_multi_agent_step14.py` 全部 4 项通过。
- `python tests/run_all.py --skip-llm` 运行新测试且无回归。
- 重建索引后，抽样 `metadata.json` 的 `pages` 分布不再恒为最后一页。
