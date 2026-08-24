# 任务清单：OpenSpec 生命周期收口与 CI 质量门禁

## 工作包 A：OpenSpec 生命周期收口

- [x] A1. 逐项审核五个候选变更：`model-upgrade`、`quality-robustness-enhancement`、`prompt-injection-guard`、`sync-roadmap-status`、`workspace-hygiene-cleanup` 的 proposal、tasks、TDD 与现有验证记录。
- [x] A2. 检查提示词防护的三个 `.py.bak` 文件；均不存在，已记录“无需删除”的闭环证据。
- [x] A3. 使用 `git mv` 将审核通过的候选目录移入 `openspec/changes/archive/`，不复制或重建归档内容。
- [x] A4. 核实活动目录仅保留真实未完成变更，并更新交接/版本记录。
- [x] A5. 已执行归档完整性和 Git 状态检查，并提交工作包 A（`513cf2f`）。

## 工作包 B：GitHub Actions 质量门禁

- [x] B0. 已确认采用“质量通过后才构建镜像”的发布门禁；Docker 工作流已调用 Quality Gate，GitHub 分支保护仍待配置。
- [x] B1. 本地固定白名单 32/32 通过；`test_smoke_api.py`、`test_p0_fixes.py` 保持在首版 CI 外。
- [x] B2. 已新建 `.github/workflows/quality-gate.yml`，包含触发条件、最小权限、并发策略、缓存及 actionlint。
- [x] B3. 已实现 Python 3.11 后端编译与固定白名单测试任务。
- [x] B4. 已实现 Node 20 前端安装、Vitest 与生产构建任务。
- [x] B5. 本地等价命令与 YAML 解析已通过，工作包 B 已提交（`7a51458`）；远端 actionlint 与 GitHub Actions 回归验证仍待完成。
- [ ] B5.1. 依据当前仓库事实更新根目录 `README.md`：项目状态、React/Ant Design 版本、历史/本轮测试口径与 OpenSpec 归档说明；不宣称未验收的远端成功。
- [ ] B5.2. 将 Docker 工作流路径过滤补充 `requirements.lock` 与 `quality-gate.yml`，并验证仅修改任一文件时都会触发 Quality Gate 与镜像构建。
- [ ] B5.3. 将 `CHANGELOG.md` 的 v5.16 条目移至最新条目位置，并按实际完成状态补充 README 同步与 C0 部署隔离，不提前记录远端或服务器成功。
- [ ] B6. 推送后确认 GitHub Actions 的 actionlint、backend 与 frontend 任务均为通过状态。
- [ ] B6.1. 从已完成的远端运行记录 workflow-lint、backend 与 frontend 的实际检查全名。
- [ ] B7. 由仓库管理员仅使用 B6.1 已核实的检查全名，在 GitHub 为 main 启用 Quality Gate 必需检查；再验证失败质量任务不发布镜像。此项需要 GitHub 管理权限或已认证 CLI，不能由本地文件替代。
- [ ] B8. 所有适用验证通过后，将本 TDD 标记为 GREEN。

## 工作包 C：自动部署可验证性

- [ ] C0. 作为所有当前未推送变更的硬前置条件，临时移除 `workflow_run` 触发，仅保留 `workflow_dispatch`，以隔离已失败的自动部署；记录恢复条件，不能永久关闭自动部署。完成 C0 前不得推送 README、Docker 路径过滤或其他会触发 Docker Build & Push 的变更。
- [ ] C1. 排查 Deploy to Server 的 SSH action 失败原因；当前公开记录仅能确认该步骤失败，无法读取受限日志。
- [ ] C2. 在取得服务器访问与 GitHub Secrets 管理授权后，核验 `SSH_HOST`、`SSH_USER`、`SSH_KEY`、`/opt/enterprise-rag`，并配置或确认仅有 `read:packages` 权限的服务器 GHCR 拉取 Secret；全程不输出凭据。
- [ ] C3. 为 `workflow_dispatch` 增加必填 `image_sha` 输入及格式校验；将首次受控部署流程改为以该 SHA 拉取后端、前端同一版本镜像，而不是仅依赖可变的 `latest` 标签。
- [ ] C3.1. 在 SHA 部署验证后，评估以镜像 digest 替代 SHA 标签的收益和实现方式；未完成评估前不阻塞首次受控发布。
- [ ] C4. 手动触发一次受控发布，确认镜像拉取、服务启动及健康检查成功；评估现有 `docker compose down` 的停机影响，但不在未核实 compose 配置时改写该命令。
- [ ] C5. 仅在 C1 至 C4 通过且用户确认后，恢复仅限 main 分支成功 Docker Build & Push 的 `workflow_run` 自动触发；使用 `workflow_run.head_sha` 拉取两个同版本镜像，并核验自动部署成功。

## 版本记录

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-08-25 | 创建收口与质量门禁实施计划。 |
| v1.1 | 2026-08-25 | 补充发布门禁、固定测试白名单、归档候选与工作流静态检查。 |
| v1.2 | 2026-08-25 | 修正实际提交状态，补充自动部署失败的可验证性与 SHA 镜像部署任务。 |
| v1.3 | 2026-08-25 | 计划复核：补充 README 事实同步、失败部署临时隔离、最小 GHCR 拉取权限、自动恢复条件与停机风险。 |
| v1.4 | 2026-08-25 | 二次复核：补充锁文件/质量门禁路径触发，以及手动和自动部署的镜像 SHA 来源与同版本校验。 |
| v1.5 | 2026-08-25 | 三次复核：将部署隔离设为推送硬前置条件，补充远端检查名核验与自动部署仅限 main 的分支边界。 |
| v1.6 | 2026-08-25 | 实施前复核：补充 CHANGELOG 最新条目顺序与本地/远端验证状态一致性要求。 |
