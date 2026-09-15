# TDD：F2 来源完整性绑定审计

## RED

- 新增 `tests/test_evaluation_source_integrity.py`，覆盖来源清单加载、哈希/大小/物理页匹配、漂移和未登记来源。
- 新增 CLI 契约测试，确认 `--source-inventory` 缺失或漂移时返回非零并写出 `source_integrity`。

## GREEN

- 新增 `src/evaluation/source_integrity.py`，只读核对来源清单登记、文件存在性、SHA-256、文件大小和物理页数。
- `src/evaluation/cli.py` 新增 `--source-inventory`；与 `--source-root` 同时提供时，绑定失败写入 `metadata.source_integrity` 并返回非零；未提供清单时保持旧存在性审计。
- 新增来源完整性测试 **6 passed**，覆盖匹配、来源缺失、清单未登记、哈希/大小漂移、物理页漂移和 CLI 报告。
- 使用项目根目录未跟踪完整候选集和根目录 `pdf_reports/` 进行只读绑定：100 条候选引用 7 个 PDF，`missing_inventory_files=[]`、`missing_source_files=[]`、三类漂移均为空、`ready=true`。
- 项目根目录 12 份 PDF 与清单 12/12 哈希和物理页数匹配；该结果不代表隔离候选/staging 已装配或发布状态已提升。

## 边界

- 本变更只证明来源文件完整性，不证明样本答案正确、人工签核有效、Provider 可用、v5.19 baseline 存在或成本门禁通过。
