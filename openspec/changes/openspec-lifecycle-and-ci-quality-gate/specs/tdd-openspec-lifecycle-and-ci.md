# TDD：OpenSpec 生命周期收口与 CI 质量门禁

验证状态：部分 GREEN。创建日期：2026-08-25；本地验证日期：2026-08-25。

| 编号 | 状态 | 验证内容 | 预期结果 |
|---|---|---|---|
| LC-R01 | GREEN | 候选 OpenSpec 目录审核 | 五个候选目录均满足归档条件。 |
| LC-R02 | GREEN | 提示词防护备份核查 | 三个 `.py.bak` 文件均不存在，且已由 `.gitignore` 覆盖。 |
| LC-R03 | GREEN | 归档完整性检查 | 使用 `git mv` 保留五个目录的原有规范文件。 |
| LC-R04 | GREEN | 活动目录检查 | 不再显示五个已完成变更目录。 |
| CI-R01 | GREEN | 后端本地等价命令 | `compileall` 与 32 项 pytest 白名单均通过。 |
| CI-R02 | GREEN | 前端本地等价命令 | Vitest 150 项通过，生产构建通过。 |
| CI-R03 | GREEN | 工作流静态检查 | 远端 `Quality Gate / workflow-lint` 通过；质量工作流只使用读取权限，不含部署、镜像推送或 Secrets。 |
| CI-R04 | GREEN | GitHub Actions 验收 | 运行 `32759245372` 的 `Quality Gate / backend`、`Quality Gate / frontend` 均通过。 |
| CI-R05 | GREEN | 工作流静态检查 | 运行 `32759245372` 的 actionlint 不报告 YAML 或 GitHub Actions 语义错误。 |
| CI-R06 | RED | Docker 路径触发 | 修改 `requirements.lock` 或 `quality-gate.yml` 时，Docker Build & Push 都会被触发并调用 Quality Gate。 |
| RG-R01 | RED | 发布门禁失败路径 | 若启用发布门禁，Quality Gate 失败不会触发镜像推送或服务器部署。 |
| RG-R02 | GREEN | 发布门禁通过路径 | 运行 `32759245372` 在 Quality Gate 通过后成功构建并推送前后端镜像，镜像使用提交 `74df2b0` 的 SHA 标签。 |
| RG-R03 | RED | 分支保护核查 | main 配置 backend、frontend 为必需状态检查，且禁止绕过合并规则。 |
| RG-R04 | GREEN | 检查名核验 | 已记录 GitHub 实际检查名：`Quality Gate / workflow-lint`、`Quality Gate / backend`、`Quality Gate / frontend`；分支保护只使用这些名称。 |
| DP-R01 | RED | 部署失败状态核查 | 部署工作流失败时，发布记录明确服务器未更新或状态未确认。 |
| DP-R02 | RED | SHA 镜像部署验证 | 受控部署只拉取通过 Quality Gate 的提交 SHA 镜像，并在健康检查通过后标记成功。 |
| DOC-R01 | GREEN | README 事实同步 | README 的 v5.16 状态、React 19 / Ant Design 6、历史/本轮验证口径及 OpenSpec 归档说明均与仓库事实一致，且不宣称远端或服务器已成功。 |
| DOC-R02 | GREEN | CHANGELOG 当前版本记录 | v5.16 位于 CHANGELOG 最新条目位置，记录实际完成的 README/C0 变更，不把远端或服务器验收写为通过。 |
| DP-R03 | GREEN | 失败部署隔离 | 当前部署根因未确认时，工作流只允许手动触发，不再因本次推送自动重试。 |
| DP-R04 | RED | GHCR 拉取凭据 | 服务器部署使用最小范围 `read:packages` Secret，凭据不进入仓库或日志。 |
| DP-R05 | RED | 受控 SHA 部署 | 手动部署拉取已通过质量门禁的提交 SHA 镜像，服务启动与健康检查均通过。 |
| DP-R06 | RED | 自动触发恢复 | 仅在受控部署成功并获用户确认后恢复 `workflow_run`，随后验证自动部署成功。 |
| DP-R07 | RED | 手动镜像 SHA 输入 | 手动部署缺少、格式错误或无法拉取的 `image_sha` 时失败；合法 SHA 使前后端拉取同一标签。 |
| DP-R08 | RED | 自动镜像 SHA 来源 | 自动部署恢复后以 `workflow_run.head_sha` 作为前后端共同镜像标签。 |
| DP-R09 | RED | 自动部署分支边界 | 自动部署仅响应 main 成功构建；非 main 分支的 Docker Build & Push 不触发服务器部署。 |
