# TDD 台账

| 编号 | 初始状态 | 契约 | 验证证据 |
| --- | --- | --- | --- |
| C-T1 | GREEN | 旧来源文件审计模块仍可导入，并准确报告缺失和已定位文件 | RED：模块被删除，测试收集报 `ModuleNotFoundError`；GREEN：来源审计与关联回归共 62 passed。 |
| C-T2 | GREEN | 冻结清单审计仍校验哈希、大小和物理页，CLI 将失败写入报告 | RED：模块被删除，测试收集报 `ModuleNotFoundError`；GREEN：匹配及哈希/大小/页数漂移、CLI 报告回归通过。 |
| C-T3 | GREEN | 绑定清单审计仍校验路径与哈希，缺少来源清单时不静默通过 | RED：模块被删除，测试收集报 `ModuleNotFoundError`；GREEN：路径/哈希漂移和缺少 `--source-inventory` 的失败报告回归通过。 |
| C-T4 | GREEN | 新基线就绪 CLI 维持只读、无 Provider 的独立语义 | `full-v7-candidate` 输出 100 条已核验、0 条未核验、无 blocker、退出码 0；定向评测回归 62 passed。 |
