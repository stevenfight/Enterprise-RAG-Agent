# 变更提案：OpenSpec 生命周期收口与 CI 质量门禁

## 背景

项目已完成稳定基线回归并推送，但 `openspec/changes/` 中仍保留多个任务已完成的变更目录，容易让后续维护误判项目进度。现有 GitHub Actions 仅负责 Docker 镜像构建与推送，未在拉取请求或主分支提交时自动验证后端和前端质量。

## 目标

1. 审核并归档已完成的 OpenSpec 变更，确保活动目录只表示真实在研工作。
2. 新增独立、无密钥依赖的 GitHub Actions 质量门禁，覆盖后端静态编译/测试与前端测试/构建。

## 非目标

- 不删除任何未确认的本地备份文件。
- 不修改业务功能、检索模型、提示词规则或部署目标。
- 不在 CI 中调用 DashScope、LangSmith、OpenEvals、真实 API 或部署服务器。
- 不创建正式版本标签或 GitHub Release。

## 交付边界

本变更分为两个可独立提交的工作包：

1. `docs(openspec): close completed changes`：状态审核、归档与文档同步。
2. `ci: add baseline quality gate`：新增质量门禁工作流及其必要的测试入口整理。

质量工作流本身只负责验证。若要使其成为镜像发布门禁，推荐后续将 Docker 构建调整为仅在 Quality Gate 成功后触发，并在 GitHub 对 main 启用必需状态检查；该调整会改变发布时序，实施前需要用户确认。
