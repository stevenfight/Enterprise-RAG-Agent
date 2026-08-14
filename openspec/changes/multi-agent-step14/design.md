# 设计说明: 数据来源页码映射修复（阶段十四）

> 编码: UTF-8

---

## 一、问题链路

```
text_splitter.py  split_markdown_reports
        │
        ├─ split_markdown_file(md_path, pdf_path)
        │      │
        │      └─ build_line_page_map(pdf_path)   ← 返回 line_to_page 闭包
        │             │
        │             ├─ 打开 PDF，建立 page_char_ranges（每页在全文中的字符区间）
        │             ├─ 读取 markdown 文本 md_text（BUG: 路径多一层 .parent → 恒为空）
        │             └─ line_to_page(line_number, md_lines)
        │                    ├─ char_offset = 该行在 markdown 中的字符偏移
        │                    ├─ ratio = char_offset / len(md_text)   ← 分母恒为 1
        │                    ├─ pdf_char_pos = ratio * len(full_text)  ← 值爆炸
        │                    └─ 超出所有 page range → 回退最后一页
        │
        └─ parent_data["pages"] = [p1, p2]   ← 全部变成 [last, last]
```

## 二、修复设计

仅修改一处路径拼接（[src/text_splitter.py](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/text_splitter.py#L101)）：

```python
# 修复前（多一层 .parent）
md_dir = pdf_path.parent.parent.parent / "debug_data" / "03_reports_markdown"

# 修复后
md_dir = pdf_path.parent.parent / "debug_data" / "03_reports_markdown"
```

修复后 `md_file` 指向 `data/stock_data/debug_data/03_reports_markdown/xxx.md`，`md_text` 正确读取，`line_to_page` 的比例映射恢复：

- 第 1 行 → `char_offset=0` → `pdf_char_pos=0` → 第 1 页
- 最后一行 → `ratio≈1` → `pdf_char_pos≈len(full_text)` → 最后一页附近
- 中间行 → 中间页附近（近似）

## 三、测试设计

### SP14-A 路径修复（真实数据）

使用本地真实 PDF 与 markdown：

- `data/stock_data/pdf_reports/电信2024年度报告.pdf`（218 页）
- `data/stock_data/debug_data/03_reports_markdown/电信2024年度报告.md`

| 用例 | 验证点 |
|------|--------|
| TC-14-A-01 | `line_to_page` 抽样结果不恒等于最后一页 218 |
| TC-14-A-02 | 第一行映射到第 1 页（`char_offset=0`） |
| TC-14-A-03 | 最后一行映射到接近最后一页 |

### SP14-B 单调性

| 用例 | 验证点 |
|------|--------|
| TC-14-B-01 | 行号递增时页码单调不减 |

## 四、兼容性

- 无 PDF 对应文件的 markdown：`build_line_page_map` 返回 `None`，`pages` 缺失，行为不变（沿用 `parent.get("pages", None)`）。
- 无 `fitz` 依赖时返回 `None`，行为不变。
