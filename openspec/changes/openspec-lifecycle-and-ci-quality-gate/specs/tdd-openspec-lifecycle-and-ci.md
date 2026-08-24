# TDD：OpenSpec 生命周期收口与 CI 质量门禁

验证状态：全部 RED。创建日期：2026-08-25。

| 编号 | 状态 | 验证内容 | 预期结果 |
|---|---|---|---|
| LC-R01 | RED | 候选 OpenSpec 目录审核 | 仅已完成且无阻塞项的目录进入归档清单。 |
| LC-R02 | RED | 提示词防护备份核查 | 三个 `.py.bak` 文件均不存在，或具备明确删除授权。 |
| LC-R03 | RED | 归档完整性检查 | 归档目录保留原 proposal、design、spec、tasks 与 TDD 文件。 |
| LC-R04 | RED | 活动目录检查 | 不再显示已完成变更目录。 |
| CI-R01 | RED | 后端本地等价命令 | 锁定依赖安装、`compileall` 和 pytest 白名单均通过。 |
| CI-R02 | RED | 前端本地等价命令 | `npm ci`、Vitest 与生产构建均通过。 |
| CI-R03 | RED | 工作流静态检查 | 工作流只使用读取权限，不含部署、镜像推送或 Secrets。 |
| CI-R04 | RED | GitHub Actions 验收 | main 或拉取请求上的 backend、frontend 两个任务均通过。 |
| CI-R05 | RED | 工作流静态检查 | actionlint 不报告 YAML 或 GitHub Actions 语义错误。 |
| RG-R01 | RED | 发布门禁失败路径 | 若启用发布门禁，Quality Gate 失败不会触发镜像推送或服务器部署。 |
| RG-R02 | RED | 发布门禁通过路径 | 若启用发布门禁，Docker 镜像使用通过质量验证的提交 SHA 构建并标记。 |
| RG-R03 | RED | 分支保护核查 | main 配置 backend、frontend 为必需状态检查，且禁止绕过合并规则。 |
