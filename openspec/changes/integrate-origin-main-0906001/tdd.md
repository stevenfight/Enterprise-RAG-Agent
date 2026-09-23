# TDD 记录

- [GREEN] 三方差异显示候选版本已包含远端报告可发现性行为及 E-RRD-2 测试；冲突解决必须保留这些断言。
- [RED] 合并前当前候选相对更新后的 `origin/main` 存在三个未解决冲突，不能创建可合并 PR。
- [GREEN] 合并后研究 API 回归 **29 passed**，侧边栏与研究任务页面回归 **25 passed**；前端 lint/build 和 `openspec validate integrate-origin-main-0906001 --strict` 均通过。
