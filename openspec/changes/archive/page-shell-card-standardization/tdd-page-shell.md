# TDD 测试用例：页面容器与卡片规范统一

> 编码：UTF-8
> 图例：红色 = 未验证，绿色 = 已通过

## 组件测试

| ID | 测试用例 | 验证方法 | 状态 |
|---|---|---|:--:|
| TC-SHELL-01 | PageShell 渲染统一的 `page-shell` 根容器，并保留子内容 | Vitest + RTL | 红色 |
| TC-SHELL-02 | PageShell 支持传入额外 className，不覆盖默认容器类 | Vitest + RTL | 红色 |
| TC-SHELL-03 | PageHeader 渲染标题和可选描述 | Vitest + RTL | 红色 |
| TC-SHELL-04 | PageHeader 支持页面图标并保持标题结构 | Vitest + RTL | 红色 |

## 页面迁移验证

| ID | 测试用例 | 验证方法 | 状态 |
|---|---|---|:--:|
| TC-SHELL-05 | DAG、图表、知识库、设置页面均使用统一页面容器 | Vitest + 代码核对 | 红色 |
| TC-SHELL-06 | 非聊天页面桌面端内容最大宽度为 1200px，聊天页面铺满内容区不变 | 浏览器 + CSS 核对 | 红色 |
| TC-SHELL-07 | 移动端页面水平内边距收敛为 16px，卡片不产生横向溢出 | 浏览器 + 响应式检查 | 红色 |
| TC-SHELL-08 | 亮色和暗色主题下页面卡片均有可识别边界 | 浏览器 + 目视 | 红色 |

## 回归验证

| ID | 测试用例 | 验证方法 | 状态 |
|---|---|---|:---:|
| TC-SHELL-09 | 前端既有 Vitest 用例全部通过 | `npm test` | 绿色 |
| TC-SHELL-10 | TypeScript 检查无错误 | `npx tsc --noEmit --pretty false --incremental false` | 绿色 |
| TC-SHELL-11 | 生产构建成功 | `npm run build` | 红色（既有错误） |
