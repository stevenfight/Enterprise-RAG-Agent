# TDD 测试用例：设置页仪表盘改造

> 图例：红色 = 未验证，绿色 = 已通过

| ID | 测试用例 | 验证方法 | 状态 |
|---|---|---|:--:|
| TC-SETTINGS-01 | 概览显示 Agent 模型名称和加载状态 | Vitest + RTL | 绿色 |
| TC-SETTINGS-02 | 概览显示向量数据库公司数量 | Vitest + RTL | 绿色 |
| TC-SETTINGS-03 | 概览显示长期记忆启用状态和容量 | Vitest + RTL | 绿色 |
| TC-SETTINGS-04 | 概览显示 LangSmith 项目和启用状态 | Vitest + RTL | 绿色 |
| TC-SETTINGS-05 | 概览显示已启用工具数 / 工具总数 | Vitest + RTL | 绿色 |
| TC-SETTINGS-06 | 未加载、不可用和未启用状态使用非成功状态样式 | Vitest + RTL | 绿色 |
| TC-SETTINGS-07 | SettingsPage 继续保留三块详细配置卡片 | Vitest + RTL | 红色 |
| TC-SETTINGS-08 | 前端 Vitest 全量通过 | `npm test -- --run` | 红色 |
| TC-SETTINGS-09 | TypeScript 检查通过 | `npx tsc --noEmit` | 红色 |
| TC-SETTINGS-10 | 生产构建成功 | `npm run build` | 红色 |
