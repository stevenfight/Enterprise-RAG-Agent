# 设计：隔离 staging 评测资产装配

## 装配边界

staging 目录只允许接收候选提交归档和下列外置资产：

- `evals/datasets/full-v7-candidate.jsonl` 及其 metadata、review、manual-signoff 文件；
- `evals/datasets/core-v7-candidate.jsonl` 与 `evals/fixtures/offline-core-v7.json`，仅用于无 Provider 的核心集预验收；
- `data/stock_data/pdf_source_inventory.json`；
- 根目录 `pdf_reports/` 中与完整候选引用一致的 PDF 文件。

这些资产保留原始状态字段，不在上传过程中修改 JSONL、metadata 或签核状态。

## 证据与验收

- 上传前生成本地资产哈希清单，上传后在服务器重新计算并逐项比较。
- 通过 `--source-root`、`--source-inventory` 和 `--source-binding-manifest` 先执行来源与数据集绑定；绑定失败不得报告为通过。
- 运行态只使用 `docker-compose.staging.yml`、独立项目名和 loopback 端口；正式端口和容器不参与验收。

## 失败边界

磁盘不足、端口占用、哈希不一致、来源缺失、容器不健康或发布状态被意外提升时，停止后续验收并保留失败证据；不通过删除正式数据或放宽门禁解决。
