## Why

新版严格 OpenSpec 校验要求每个活跃变更要么提供产品规格 delta，要么明确声明其为无产品规格变更的工具、部署或文档工作。历史目录未带合法 metadata，导致 F1 总验收无法区分真实产品规格债务和纯流程文档债务。

## What Changes

- 为经逐项确认的纯工具/部署变更补充当前格式的 metadata。
- 记录仍涉及产品行为的变更清单，保留其 delta 规格迁移要求。
- 不改变业务实现、API、部署运行态、任务状态或历史证据。

## Capabilities

### New Capabilities

- 无。本变更不新增产品能力。

### Modified Capabilities

- 无。本变更不修改产品规格，只恢复 OpenSpec 严格校验对纯流程变更的正确识别。

## Impact

- `openspec/changes/*/.openspec.yaml`
- F1 的 OpenSpec 严格校验记录
