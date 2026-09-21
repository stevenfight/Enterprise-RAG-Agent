## Why

六项历史产品行为变更已具备提案和测试证据，但使用旧格式规格文档，无法被当前 OpenSpec 严格校验识别为 delta。它们持续阻塞 F1，却不能像纯流程变更一样标记为 `skip_specs`。

## What Changes

- 将既有、已验证的 CORS、SSE、鉴权、金额换算和 Cookie 行为提炼为最小 delta Requirement/Scenario。
- 保留原有历史规格和 TDD 文档，不修改业务实现或扩大行为范围。
- 不处理范围明显更大的 v7 研究 Agent 变更。

## Capabilities

### New Capabilities

- 无。本变更仅迁移既有规格表达。

### Modified Capabilities

- 无。本变更不改变现有产品需求。

## Impact

- 六个历史产品行为变更下新增兼容当前工具的 delta 规格文件。
- F1 OpenSpec 严格校验结果。
