# 变更提案：工作区本地生成物忽略规则

## 背景

当前工作区混入 npm 缓存、运行会话记忆、代理工作记录、预览图和一次性调试记录。这些文件不属于可复现的产品源码或规范交付物，且现有 `.gitignore` 未覆盖它们，导致 Git 状态噪声增加。

## 目标

在不删除任何现有文件、不影响源码、测试、OpenSpec 归档和依赖锁文件的前提下，补充最小忽略规则，使本地生成物不再出现在 Git 未跟踪状态中。

## 范围

- 修改根目录 `.gitignore`。
- 忽略 `.baoyu-skills/`、`.planning/`、`frontend/.npm-cache/`、`data/long_term_memory/`、`antdx-ui-preview.png` 和 `debug-regression-environment.md`。

## 非目标

- 不删除已存在的本地文件。
- 不修改业务代码、测试、依赖版本、OpenSpec 归档或 Git 提交历史。

## 版本记录

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-08-25 | 新增本地生成物忽略规则，6 项验证通过。 |
