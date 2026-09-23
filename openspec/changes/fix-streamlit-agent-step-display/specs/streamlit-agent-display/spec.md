## ADDED Requirements

### Requirement: Streamlit Agent 推理链 SHALL 正确显示步骤序号

Streamlit 适配层 SHALL 将 AgentResult 中的 `step` 字段映射到现有推理链展示模型的 `step_number`，缺失时不得因字段读取抛出异常。

#### Scenario: Agent 返回带步骤的推理链

- **WHEN** `reasoning_chain` 项包含 `step=2`
- **THEN** 展示模型中的 `step_number` 为 `2`
- **AND** `thought/action/observation` 字段保持原值

#### Scenario: Agent 返回缺少步骤字段的旧数据

- **WHEN** `reasoning_chain` 项不包含 `step`
- **THEN** 适配层使用安全默认值
- **AND** 不因读取不存在的 `step_number` 抛出 KeyError
