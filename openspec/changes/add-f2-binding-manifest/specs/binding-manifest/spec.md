# 评测数据绑定清单

## ADDED Requirements

### Requirement: 绑定清单必须锁定数据集和来源清单

评测 CLI 在收到 `--source-binding-manifest` 时 MUST 读取 JSON 清单，并核对实际传入的数据集与来源清单的规范化路径、文件存在性和 SHA-256。

#### 场景：绑定完全一致

- **当** 清单可解析，两个实际文件存在，且路径与 SHA-256 均一致
- **那么** `metadata.source_binding.ready` 必须为 `true`

#### 场景：绑定清单缺失或不可解析

- **当** `--source-binding-manifest` 指向不存在或不可解析的文件
- **那么** `metadata.source_binding.ready` 必须为 `false`，并记录 `manifest_error`

#### 场景：数据集或来源清单发生漂移

- **当** 实际文件路径或 SHA-256 与清单不一致
- **那么** `metadata.source_binding.ready` 必须为 `false`，并分别列出路径或哈希不匹配字段

### Requirement: 保持无绑定清单兼容

未传入 `--source-binding-manifest` 时，评测 CLI MUST 保持现有数据集、来源审计和质量门禁行为不变。

#### Scenario: 未传入绑定清单

- **当** CLI 未传入 `--source-binding-manifest`
- **那么** CLI 不执行绑定清单门禁，并保持既有质量门禁和来源审计结果
