# 设计：OpenSpec 生命周期收口与 CI 质量门禁

## OpenSpec 收口策略

先以 `tasks.md`、TDD 状态和现有验证记录为依据逐项审核。仅当任务全部完成且不存在需要人工确认的真实文件时，才将目录从 `openspec/changes/<name>` 移动到 `openspec/changes/archive/<name>`。

提示词注入防护的 `.py.bak` 清理项不执行盲删：先检查三个预期文件是否存在。当前已核实它们均不存在并且 `*.py.bak` 已被忽略，故该项可记录为“无需删除”，再允许归档。

## CI 设计

新增 `.github/workflows/quality-gate.yml`，与现有 `docker-build.yml` 独立：

- 触发：以 `main` 为目标分支的 pull request、手动触发，以及由 Docker 工作流在 main 推送时通过 `workflow_call` 调用。
- `backend`：Ubuntu、Python 3.11、pip 缓存、按 `requirements.lock` 的已固定直接依赖安装、`python -m compileall -q src`，并执行以下不访问真实 API 的 pytest 白名单：`tests/test_api_memory_factory.py`、`tests/test_prompt_injection_guard.py`、`tests/tdd_planner_alias.py`、`tests/tdd_retrieval_topn_fix.py`。
- `frontend`：Ubuntu、Node 20、npm 缓存、`npm ci`、`npm test`、`npm run build`。
- 最小权限：`contents: read`；同分支重复运行使用并发取消策略。

首版不运行 `tests/test_smoke_api.py`，因为它要求预先启动 API 服务并依赖本机配置；将其保留为本地/部署后冒烟项。

`requirements.lock` 当前仅固定直接依赖版本，未固定传递依赖和哈希；首版 CI 使用它保证主要依赖版本一致，不将其表述为完整可复现安装。完整哈希锁定属于后续工程化工作。

## 发布门禁策略

仅新增质量工作流不会阻止现有 `docker-build.yml` 在同一 main 推送中推送镜像。推荐的目标链路为：

`Pull Request → Quality Gate 通过 → 合并 main → Quality Gate 通过 → Docker Build & Push → Deploy to Server（如已配置 Secrets）`

为实现该链路，后续需经用户确认后将 Docker 工作流改为监听 `Quality Gate` 成功事件，并在 checkout 与 SHA 标签中使用被验证提交的 SHA；同时在 GitHub 分支保护中把 Quality Gate 的 backend、frontend 任务设为 main 的必需检查。分支保护是仓库设置，不能只通过仓库文件自动完成。

Docker 工作流的 `paths` 必须同时包含 `requirements.lock` 与 `quality-gate.yml`：前者决定 CI 和后端镜像使用的已固定直接依赖，后者决定镜像发布前的实际门禁逻辑。否则仅修改锁文件或门禁工作流时，main 推送可能不触发应有的质量验证与镜像构建。

## README 事实同步

根目录 `README.md` 属于公开项目概览，必须与仓库当前可验证事实一致。更新范围限定为：

- 将主状态更新为当前 v5.16 的本地实现状态，并明确远端 Quality Gate 与服务器部署仍未验收；
- 将前端依赖描述从 React 18 / Ant Design 5 改为 `frontend/package.json` 中实际声明的 React 19 / Ant Design 6；
- 将历史 SDD/TDD 数量与本轮本地验证结果分开表述，避免把不同统计口径混为一个“总数”；
- 调整 OpenSpec 目录示例，说明已完成变更位于 `openspec/changes/archive/`，活动目录只展示在研变更。

README 不得宣称 GitHub Actions、分支保护或服务器已成功；这些状态只有在相应外部验收完成后才可更新。

## 部署故障隔离与恢复策略

公开 GitHub 记录只能确认 Deploy to Server 在 SSH 步骤失败，不能证明服务器已更新，也不能由无认证日志判断根因。为避免本次质量门禁推送再次自动执行未知失败脚本，实施顺序如下：

1. **C0：临时隔离。** 在推送质量门禁变更前，将部署工作流触发条件收敛为 `workflow_dispatch`；保留工作流文件和手动部署能力，不删除现有配置。此状态仅用于故障排查，不是永久关闭自动部署。
2. **C1/C2：凭据与目标核验。** 在用户提供服务器访问授权及仓库 Secrets 管理权限后，核验 `SSH_HOST`、`SSH_USER`、`SSH_KEY`、`/opt/enterprise-rag` 与 GHCR 包访问权限。服务器拉取私有 GHCR 镜像必须使用最小范围、具备 `read:packages` 权限的专用凭据（例如受限的 `GHCR_PULL_TOKEN`）；凭据只能从 GitHub Secret 注入，不能输出到日志或写入仓库。`GITHUB_TOKEN` 可在满足包访问关系的 Actions 作业中使用，但它是作业级短期令牌，不应作为服务器长期拉取凭据。
3. **C3：镜像版本。** 首次受控部署至少拉取已通过 Quality Gate 的提交 SHA 标签，而非 `latest`。手动触发必须提供并校验一个非空、格式正确的 `image_sha` 输入；自动触发恢复后必须使用 `workflow_run.head_sha`。后端和前端镜像必须使用同一个 SHA，且该 SHA 必须能在 GHCR 拉取。不得把默认分支当前 SHA、手动触发工作流的 SHA 与待部署镜像 SHA 混用。在服务器路径、凭据和部署成功得到验证后，再评估将部署目标提升为镜像 digest，以获得更强的不可变性。
4. **C4/C5：受控恢复。** 手动部署须确认镜像拉取、`docker compose` 启动和健康检查均成功；仅在用户确认该次验证通过后，恢复 `workflow_run` 自动触发。现有 `docker compose down` 会导致完整短暂停机，是否改为 `docker compose pull && docker compose up -d --remove-orphans` 必须先核实服务器 compose 配置，作为后续最小化停机优化，不在本次故障隔离中直接改写。

GitHub main 分支保护同样需要仓库管理员通过 GitHub 设置或已认证的 CLI 操作配置，不能凭本地仓库状态宣称已经启用。

## 工作流静态检查

新增或修改工作流时，先使用 actionlint 进行 YAML 与 GitHub Actions 语义检查；如本地未安装 actionlint，不在本次计划阶段自动安装，实施时先征得用户同意。

## 提交与验证顺序

先完成收口提交并在本地复查目录状态；再新增 CI，先在本地执行与 CI 等价的后端、前端命令，通过后提交。远端 Actions 运行结果通过后才将质量门禁视为完成。
