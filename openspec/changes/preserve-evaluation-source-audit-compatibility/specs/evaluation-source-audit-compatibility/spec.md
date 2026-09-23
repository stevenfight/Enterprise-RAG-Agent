## ADDED Requirements

### Requirement: 常规评测 SHALL 保留来源审计兼容接口

常规离线评测 SHALL 支持来源根目录、冻结清单和数据集绑定清单审计；任一已启用审计不就绪时，评测报告 SHALL 保留失败原因并以非零状态结束。

#### Scenario: 提供来源审计参数

- **WHEN** 运行常规评测并提供 `--source-root`、`--source-inventory` 或 `--source-binding-manifest`
- **THEN** 报告包含对应来源审计结果
- **AND** 不就绪审计会阻断成功退出码

#### Scenario: 运行基线就绪检查

- **WHEN** 仅运行 `--baseline-readiness-output`
- **THEN** 该路径只报告数据集覆盖与人工核验状态
- **AND** 不替代常规来源审计，也不调用 Provider
