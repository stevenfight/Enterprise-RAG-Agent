# 变更提案：隔离 staging 评测资产装配

## 背景

本地完整评测集、人工复核包和根目录 PDF 已通过只读哈希与来源绑定核查，但它们仍未进入 `/opt/enterprise-rag-staging`。正式环境与 staging 资产边界不同，不能直接把正式目录当作候选验收环境。

## 目标

- 将指定候选提交与已核查的 F2 评测资产装配到独立 staging 目录。
- 对数据集、复核包、签核台账、来源清单和 PDF 保留可复核的 SHA-256 证据。
- 使用独立 Compose、端口、数据卷和环境文件执行运行态预验收。
- 保持完整候选的 `draft/pending_review/release_ready=false` 状态，不自动发布。

## 非目标

- 不修改正式目录 `/opt/enterprise-rag`、正式容器或正式数据。
- 不推送远端、不更新 PR、不合并 `main`。
- 不把完整候选集或 PDF 纳入本轮 Git 提交。
