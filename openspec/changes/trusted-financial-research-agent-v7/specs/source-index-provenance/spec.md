## ADDED Requirements

### Requirement: 源文档、索引代际和声明必须形成不可变且可回溯的溯源链

系统 MUST 以内容哈希和逻辑文档版本管理源 PDF，只有已验证的 generation 才能原子激活；报告声明能够回溯到对应文档版本和来源证据。

#### Scenario: 候选索引构建失败

- **WHEN** 新 generation 的验证、制品完整性或发布写入失败
- **THEN** 当前 active generation 保持不变，失败候选不得对查询可见

#### Scenario: 来源版本失效

- **WHEN** 被报告声明依赖的文档版本失效
- **THEN** 系统精确标记直接或间接依赖的计算、声明和报告为 stale，并保留失效记录
