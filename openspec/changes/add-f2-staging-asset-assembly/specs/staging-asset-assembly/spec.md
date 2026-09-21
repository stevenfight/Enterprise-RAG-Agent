## ADDED Requirements

### Requirement: staging 资产必须与本地核查资产一致

staging 装配 MUST 只使用已核查的候选提交和外置评测资产，并在上传前后核对数据集、来源清单、复核包、签核台账和 PDF 的 SHA-256。

#### Scenario: 上传后哈希全部一致

- **WHEN** staging 中所有声明资产的 SHA-256 与本地装配清单一致
- **THEN** 资产装配审计标记为就绪
- **AND** 后续运行态验收可以继续

#### Scenario: 上传后任一资产漂移

- **WHEN** 任一数据集、来源清单、复核包、签核台账或 PDF 的 SHA-256 不一致
- **THEN** 装配审计标记为未就绪
- **AND** 不启动完整金融评测

### Requirement: staging 不得改变正式环境或发布状态

隔离 staging MUST 使用独立目录、Compose 项目、端口、数据卷和环境文件；装配过程 MUST 保留完整候选的 `draft`、`pending_review` 和 `release_ready=false` 状态。

#### Scenario: staging 运行态与正式栈隔离

- **WHEN** staging Compose 启动并执行健康检查
- **THEN** 只访问 staging loopback 端口
- **AND** 正式容器、正式目录和正式数据保持不变

#### Scenario: 候选尚未达到发布状态

- **WHEN** 完整候选 metadata 仍记录 `release_ready=false`
- **THEN** staging 只执行预验收
- **AND** 不创建发布标签、不激活正式 publication
