# 变更提案: 聊天界面升级为 Ant Design X 组件库

> 编码: UTF-8
> 状态: 提案中
> 关联: `openspec/changes/modern-ui/` (Phase 1-3 已完成)

---

## 1. 变更背景

当前聊天界面基于 Ant Design 通用组件（`Card`、`Typography`、`Space`、`Tag`）手工搭建，虽然在功能上已完整覆盖问答、SSE 流式、多 Agent 状态、思维链等场景，但视觉上停留在"功能实现"层面，缺乏现代化 AI 对话产品应有的质感。

`@ant-design/x` 是蚂蚁集团基于 RICH 交互范式打造的 AI 界面专用组件库，与项目现有 antd 6 技术栈天然兼容。它提供了 `Bubble`、`Sender`、`Conversations`、`ThoughtChain`、`Welcome`、`XMarkdown` 等开箱即用的 AI 交互组件，能够在**最小改动量**的前提下，将聊天界面观感提升到 LobeChat / ChatGPT 级别。

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 聊天界面替换为 Ant Design X 组件 | Bubble / Sender / Conversations / Welcome 渲染正常 |
| Markdown 渲染升级为 XMarkdown | 流式渲染、公式、表格、代码高亮均正确 |
| 保留现有后端交互逻辑 | SSE 流式、多 Agent 状态、思维链均正常工作 |
| 不修改其他页面 | DAG 看板、图表中心、知识库、设置页零改动 |
| 不修改后端 | 所有 Python 代码零改动 |

## 3. 变更范围

### 3.1 修改（chat 相关组件）

| 文件 | 变更内容 |
|------|---------|
| `frontend/package.json` | 新增 `@ant-design/x` 依赖 |
| `frontend/src/components/chat/ChatInput.tsx` | 替换为 `Sender` 组件 |
| `frontend/src/components/chat/MessageBubble.tsx` | 替换为 `Bubble` + `XMarkdown` |
| `frontend/src/components/chat/ChatContainer.tsx` | 用 `Conversations` + `Bubble.List` 重构 |
| `frontend/src/pages/ChatPage.tsx` | 用 `Welcome` 替换自定义欢迎页，调整布局 |
| `frontend/src/components/chat/ThoughtChainDrawer.tsx` | 可选：用 `ThoughtChain` 组件增强 |

### 3.2 保留不变

- 所有 `src/` 下的 Python 后端代码
- `frontend/src/services/` (API 层)
- `frontend/src/stores/` (Zustand 状态管理)
- `frontend/src/pages/DagBoardPage.tsx`
- `frontend/src/pages/ChartsPage.tsx`
- `frontend/src/pages/KnowledgePage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/components/layout/` (布局)
- `frontend/src/components/dag/` (DAG)
- `frontend/src/components/charts/` (图表)
- `frontend/src/styles/` (主题)
- 所有测试文件

### 3.3 删除

- 无（所有旧组件保留在 git 历史中，不删除）

## 4. 技术选型对照

| 旧组件 | 新组件 | 来源 |
|--------|--------|------|
| `ChatInput` (antd Input + Button) | `Sender` | `@ant-design/x` |
| `MessageBubble` (自定义 div + antd Tag) | `Bubble` + `Bubble.List` | `@ant-design/x` |
| 会话列表 (自定义 div) | `Conversations` | `@ant-design/x` |
| 自定义欢迎页 | `Welcome` | `@ant-design/x` |
| formatMarkdown 函数 | `XMarkdown` | `@ant-design/x-sdk` |
| 自定义推理链 UI | `ThoughtChain` | `@ant-design/x` |
| 自定义 SSE 处理 | `XStream` (可选) | `@ant-design/x-sdk` |

## 5. 风险与应对

| 风险 | 应对 |
|------|------|
| @ant-design/x 与 antd 6 版本兼容 | antd 6.6.x + @ant-design/x 2.9.x 被 Ant Design Pro v6 验证过 |
| 自定义 SSE 逻辑与 XStream 冲突 | 先保留现有 SSE 处理逻辑，不引入 XStream，降低风险 |
| 现有 Zustand store 与 useXChat 不兼容 | 不引入 useXChat，保留 Zustand，仅替换 UI 组件 |
| 现有测试用例可能因组件变化失败 | 更新测试用例中的选择器和断言 |

## 6. 版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0-dev | 2026-08-20 | 初始化提案 |