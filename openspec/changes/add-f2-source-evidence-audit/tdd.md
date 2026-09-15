# TDD：F2 来源证据审计

## RED

- 新增 `tests/test_evaluation_source_audit.py`，在来源审计模块不存在时收集失败。
- 新增 CLI 缺失来源测试；旧 CLI 不认识 `--source-root`，无法执行来源门禁。

## GREEN

- 新增 `src/evaluation/source_audit.py`，只读检查样本 `expected_sources` 在显式来源根目录中的可定位性。
- `src/evaluation/cli.py` 新增可重复的 `--source-root` 参数；来源缺失时将具体文件写入报告并返回非零，无来源根目录时保持原离线夹具模式。
- 来源审计定向测试 **3 passed**；评测相关回归（含质量门禁、升级收益、阈值配置）**39 passed**。
- 实际运行 `--source-root data/stock_data` 的结果为：检查 1 个来源、缺失 `示例公司.pdf`、`source_ready=false`、`coverage_ready=false`、退出码 1。该结果证明当前资产不足，不代表评测集或产品质量通过。

## 结论

来源审计能力已完成，但真实来源资产仍缺失；不得因此勾选 v7 F2 或把历史清单声明为已复核来源。
