# TDD 测试用例: 聊天界面可视化优化

> 编码: UTF-8
> 图例: 红色 = 未验证（待实现）, 绿色 = 已通过
> 验证方式: Vitest + React Testing Library + 代码审查

---

## 测试分组一：聊天区铺满 (TC-UI-001)

对应规范: SPEC-UI-001

| ID | 测试用例 | 验证方法 | 状态 |
|----|---------|---------|:--:|
| TC-UI-001-01 | `theme.ts` 导出 `chatAreaLight` / `chatAreaDark` / `borderDark` | Vitest | 绿色 |
| TC-UI-001-02 | 聊天路由 `/` 时 Content 的 overflow 为 hidden（铺满） | Vitest | 绿色 |
| TC-UI-001-03 | 非聊天路由时 Content 保持 overflow auto（标准内边距） | Vitest | 绿色 |

---

## 测试分组二：暗色颜色统一 (TC-UI-002)

对应规范: SPEC-UI-002

| ID | 测试用例 | 验证方法 | 状态 |
|----|---------|---------|:--:|
| TC-UI-002-01 | `chatAreaDark` 等于主题暗色背景 `#1A1826` | Vitest | 绿色 |
| TC-UI-002-02 | `borderDark` 等于 `#3A3550` | Vitest | 绿色 |
| TC-UI-002-03 | ChatContainer 会话列表暗色背景引用 `colors.bgDarkSidebar` | 代码审查 | 绿色 |

---

## 测试分组三：流式打字机光标 (TC-UI-003)

对应规范: SPEC-UI-003

| ID | 测试用例 | 验证方法 | 状态 |
|----|---------|---------|:--:|
| TC-UI-003-01 | AI 消息 `isStreaming=true` 时渲染 `typing-cursor` 元素 | Vitest | 绿色 |
| TC-UI-003-02 | AI 消息 `isStreaming=false` 时不渲染 `typing-cursor` | Vitest | 绿色 |
| TC-UI-003-03 | 用户消息不渲染 `typing-cursor` | Vitest | 绿色 |

---

## 测试分组四：回归 (TC-UI-004)

| ID | 测试用例 | 验证方法 | 状态 |
|----|---------|---------|:--:|
| TC-UI-004-01 | 既有聊天组件测试（ChatInput / MessageBubble / ChatContainer）保持通过 | Vitest | 绿色 |
| TC-UI-004-02 | 全量 `npm run test` 通过（9 文件 / 89 用例） | 命令行 | 绿色 |
