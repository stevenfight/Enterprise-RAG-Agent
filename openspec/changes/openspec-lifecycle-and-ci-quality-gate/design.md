# 设计：OpenSpec 生命周期收口与 CI 质量门禁

## OpenSpec 收口策略

先以 `tasks.md`、TDD 状态和现有验证记录为依据逐项审核。仅当任务全部完成且不存在需要人工确认的真实文件时，才将目录从 `openspec/changes/<name>` 移动到 `openspec/changes/archive/<name>`。

提示词注入防护的 `.py.bak` 清理项不执行盲删：先检查三个预期文件是否存在。当前已核实它们均不存在并且 `*.py.bak` 已被忽略，故该项可记录为“无需删除”，再允许归档。

## CI 设计

新增 `.github/workflows/quality-gate.yml`，与现有 `docker-build.yml` 独立：

- 触发：对 `main` 的 push、以 `main` 为目标分支的 pull request、手动触发。
- `backend`：Ubuntu、Python 3.11、pip 缓存、按 `requirements.lock` 的已固定直接依赖安装、`python -m compileall -q src`，并执行以下不访问真实 API 的 pytest 白名单：`tests/test_api_memory_factory.py`、`tests/test_prompt_injection_guard.py`、`tests/tdd_planner_alias.py`、`tests/tdd_retrieval_topn_fix.py`。
- `frontend`：Ubuntu、Node 20、npm 缓存、`npm ci`、`npm test`、`npm run build`。
- 最小权限：`contents: read`；同分支重复运行使用并发取消策略。

首版不运行 `tests/test_smoke_api.py`，因为它要求预先启动 API 服务并依赖本机配置；将其保留为本地/部署后冒烟项。

`requirements.lock` 当前仅固定直接依赖版本，未固定传递依赖和哈希；首版 CI 使用它保证主要依赖版本一致，不将其表述为完整可复现安装。完整哈希锁定属于后续工程化工作。

## 发布门禁策略

仅新增质量工作流不会阻止现有 `docker-build.yml` 在同一 main 推送中推送镜像。推荐的目标链路为：

`Pull Request → Quality Gate 通过 → 合并 main → Quality Gate 通过 → Docker Build & Push → Deploy to Server（如已配置 Secrets）`

为实现该链路，后续需经用户确认后将 Docker 工作流改为监听 `Quality Gate` 成功事件，并在 checkout 与 SHA 标签中使用被验证提交的 SHA；同时在 GitHub 分支保护中把 Quality Gate 的 backend、frontend 任务设为 main 的必需检查。分支保护是仓库设置，不能只通过仓库文件自动完成。

## 工作流静态检查

新增或修改工作流时，先使用 actionlint 进行 YAML 与 GitHub Actions 语义检查；如本地未安装 actionlint，不在本次计划阶段自动安装，实施时先征得用户同意。

## 提交与验证顺序

先完成收口提交并在本地复查目录状态；再新增 CI，先在本地执行与 CI 等价的后端、前端命令，通过后提交。远端 Actions 运行结果通过后才将质量门禁视为完成。
