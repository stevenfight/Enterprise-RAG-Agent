## ADDED Requirements

### Requirement: 发布集运行时数据 SHALL 与源代码候选隔离

系统 SHALL 将 v7 发布集的本地 SQLite 元数据和迁移备份视为运行时数据，而非可提交的发布资产。

#### Scenario: 本地发布集元数据存在

- **WHEN** 本地 `data/v7/` 包含 metadata 数据库或迁移备份
- **THEN** Git 必须忽略该目录
- **AND** 源代码、测试和规格仍可独立验证

### Requirement: 视觉与发布集候选 SHALL 通过离线契约验证

系统 SHALL 能在不调用真实视觉 Provider 的条件下验证页面制品、视觉事实和 generation 发布生命周期。

#### Scenario: 执行定向测试

- **WHEN** 运行 M0/M1、视觉安全、发布集提升/退休和制品访问测试
- **THEN** 测试不得要求真实 Provider 凭据或运行时发布数据
- **AND** 所有契约必须通过
