# 设计

## 决策

1. 恢复 `source_audit`、`source_integrity`、`source_binding` 三个只读模块及其公共导出。
2. 常规评测继续接受 `--source-root`、`--source-inventory`、`--source-binding-manifest`：
   - 提供来源根目录时执行文件可定位性审计；
   - 提供冻结清单时执行哈希、大小与物理页审计；
   - 提供绑定清单但未提供冻结清单时，在报告中写入明确失败原因。
3. `--baseline-readiness-output` 保持只读、无夹具、无 Provider 的独立路径；它只报告数据集覆盖和人工核验状态，不替代常规评测的来源审计。
4. 常规评测退出码同时受质量门禁和已启用来源审计的 `ready` 约束。

## 验证

- 先恢复旧来源审计测试并确认当前候选失败。
- 恢复兼容实现后，来源审计测试、评测质量门禁测试和完整候选集签核测试必须通过。
- 用 CLI 验证基线就绪路径保持 100 条已核验、无 blocker，且不调用 Provider。
