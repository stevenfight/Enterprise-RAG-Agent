## Why

`trusted-financial-research-agent-v7` 是全库严格 OpenSpec 校验唯一剩余失败项。它已有七份历史规格、验收口径和大量 GREEN 测试，但没有当前工具可识别的 delta，因此阻塞 F1。

## What Changes

- 依据已有文档与 GREEN 证据，为 v7 的七个能力域各增加最小 delta Requirement/Scenario。
- 保留历史规格、TDD、验收和路线图，不更改业务实现、指标阈值或发布结论。
- 不把未实施或仅规划的能力伪装为已交付。

## Capabilities

### New Capabilities

- 无。本变更只迁移已存在的规格表达。

### Modified Capabilities

- 无。本变更不修改产品需求。

## Impact

- `trusted-financial-research-agent-v7` 下新增七个兼容当前工具的 delta 规格目录。
- F1 全库 OpenSpec 严格校验结果。
