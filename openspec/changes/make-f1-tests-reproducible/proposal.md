## Why

F1 后端全量测试不能依赖未跟踪的运行时图表文件，也不能把仅适用于 Git 工作树的 v5.19 指纹核验误报为部署 archive 的产品失败。

## What Changes

本变更仅修复测试前置和测试边界：保留已核验图表投影断言；Git 工作树中继续严格验证 v5.19 指纹。不得修改财务事实、图表 API、运行时数据目录或正式部署。

## Capabilities

### New Capabilities

- 无。本变更不新增产品能力。

### Modified Capabilities

- 无。本变更不修改产品规格，只调整测试可复现性。

## Impact

- `tests/test_chart_unit_conversion.py`
- `tests/test_v519_compatibility_manifest.py`
- F1 隔离后端验收流程
