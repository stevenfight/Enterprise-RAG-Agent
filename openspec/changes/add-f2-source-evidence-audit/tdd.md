# TDD：F2 来源证据审计

## RED

- 新增 `tests/test_evaluation_source_audit.py`，在来源审计模块不存在时收集失败。
- 新增 CLI 缺失来源测试；旧 CLI 不认识 `--source-root`，无法执行来源门禁。

## GREEN

- 新增 `src/evaluation/source_audit.py`，只读检查样本 `expected_sources` 在显式来源根目录中的可定位性。
- `src/evaluation/cli.py` 新增可重复的 `--source-root` 参数；来源缺失时将具体文件写入报告并返回非零，无来源根目录时保持原离线夹具模式。
- 来源审计定向测试 **3 passed**；评测相关回归（含质量门禁、升级收益、阈值配置）**39 passed**。
- 候选种子集实际运行 `--source-root data/stock_data` 的结果仍为：检查 1 个来源、缺失 `示例公司.pdf`、`source_ready=false`、`coverage_ready=false`、退出码 1；这证明隔离候选当前仍不能完成来源闭环。
- 只读复核项目根目录的未跟踪完整候选集：100 条候选引用 7 个 PDF，使用项目根目录 `pdf_reports/` 作为显式来源根目录时，来源审计结果为 `checked_source_count=7`、`missing_source_files=[]`、`ready=true`。该数据集不在隔离候选分支中，不能把该结果当作候选分支发布证据。
- 只读复核冻结清单与项目根目录 12 份 PDF：12/12 SHA-256 和物理页数匹配；服务器隔离 staging 仍没有这些 PDF 和完整候选集，正式旧环境的 PDF 仅作为可追溯旧资产，不作为 staging 发布证据。

## 结论

来源审计能力已完成；真实来源在项目根目录/正式旧环境可追溯，但尚未装配到隔离候选/staging，且完整候选集元数据仍为 `draft`、复核包仍为 `pending_review`、`release_ready=false`。不得因此勾选 v7 F2 或把本地未跟踪数据声明为已发布来源。
