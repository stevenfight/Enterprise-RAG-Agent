# 任务清单：OpenSpec 生命周期收口与 CI 质量门禁

## 工作包 A：OpenSpec 生命周期收口

- [ ] A1. 逐项审核五个候选变更：`model-upgrade`、`quality-robustness-enhancement`、`prompt-injection-guard`、`sync-roadmap-status`、`workspace-hygiene-cleanup` 的 proposal、tasks、TDD 与现有验证记录。
- [ ] A2. 检查提示词防护的三个 `.py.bak` 文件；若均不存在，记录“无需删除”的闭环证据。
- [ ] A3. 使用 `git mv` 将审核通过的候选目录移入 `openspec/changes/archive/`，不复制或重建归档内容。
- [ ] A4. 核实活动目录仅保留真实未完成变更，并更新交接/版本记录。
- [ ] A5. 执行归档完整性和 Git 状态检查，提交工作包 A。

## 工作包 B：GitHub Actions 质量门禁

- [ ] B0. 确认质量门禁定位：仅报告质量，或采用推荐的“质量通过后才构建镜像”发布门禁；后者需额外修改 Docker 工作流和 GitHub 分支保护。
- [ ] B1. 本地运行固定白名单：`python -m pytest -q tests/test_api_memory_factory.py tests/test_prompt_injection_guard.py tests/tdd_planner_alias.py tests/tdd_retrieval_topn_fix.py`；保持 `test_smoke_api.py`、`test_p0_fixes.py` 在首版 CI 外。
- [ ] B2. 新建 `.github/workflows/quality-gate.yml`，配置触发条件、最小权限、并发策略、缓存及工作流静态检查。
- [ ] B3. 实现 Python 3.11 后端编译与固定白名单测试任务。
- [ ] B4. 实现 Node 20 前端安装、Vitest 与生产构建任务。
- [ ] B5. 以本地等价命令和 actionlint 回归验证 YAML 及两类任务，提交工作包 B。
- [ ] B6. 推送后确认 GitHub Actions 两项任务均为通过状态。
- [ ] B7. 若选择发布门禁，在 GitHub 为 main 启用 Quality Gate 必需检查；再将 Docker 工作流改为只构建已验证提交，并验证失败质量任务不发布镜像。
- [ ] B8. 所有适用验证通过后，将本 TDD 标记为 GREEN。

## 版本记录

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-08-25 | 创建收口与质量门禁实施计划。 |
| v1.1 | 2026-08-25 | 补充发布门禁、固定测试白名单、归档候选与工作流静态检查。 |
