# 技术设计: 聊天界面可视化优化

> 编码: UTF-8

## 1. 聊天区铺满

[AppLayout.tsx](../../../../frontend/src/components/layout/AppLayout.tsx) 的 `Content` 当前对所有路由统一使用 `padding: 24` 和 `overflow: auto`。

方案：引入 `useLocation` 判断当前路由，当 `pathname === '/'`（聊天首页）时：

- `padding: 0`
- `overflow: hidden`（由 ChatPage 内部 `chat-scroll-area` 自行管理滚动）

其他路由保持不变。

## 2. 暗色颜色统一

在 [theme.ts](../../../../frontend/src/styles/theme.ts) 的 `colors` 中补充三个语义色：

```ts
// 聊天区域专用
chatAreaLight: '#FAFAFA',
chatAreaDark: DARK_BG,          // #1A1826
borderDark: '#3A3550',
```

随后将以下组件中的硬编码颜色替换为语义色：

| 组件 | 硬编码位置 | 替换为 |
|------|-----------|--------|
| ChatContainer | 会话列表背景 `#1a1a2e` | `colors.bgDarkSidebar` |
| ChatContainer | 聊天区背景 `#141420` | `colors.chatAreaDark` |
| ChatContainer | 边框 `#2a2a3a` / `#f0f0f0` | `colors.borderDark` / `colors.border` |
| ChatPage | 面板背景 `#1a1a1a` | `colors.bgDarkCard` |
| MessageBubble | AI 气泡背景 `rgba(30,28,45,.85)` | `colors.bgDarkCard` |
| MessageBubble | 边框 `#2a2a3a` / `#f0f0f0` | `colors.borderDark` / `colors.border` |

## 3. 流式打字机光标

- `MessageBubble` 新增可选 prop `isStreaming?: boolean`。
- 当 `isStreaming && !isUser` 时，在 Markdown 渲染结果的末尾追加光标 span：

```html
<span class="typing-cursor"></span>
```

- `ChatContainer` 在遍历消息时，对「最后一条 assistant 消息且 `isLoading === true`」传入 `isStreaming=true`。
- 在 `global.css` 中定义 `.typing-cursor` 的闪烁动画（`@keyframes` + `animation: blink 1s step-end infinite`）。

## 4. 不变项

- SSE 事件流、`applyAgentEvent`、`streamAgentQuery` 不变。
- `chatStore` 状态结构不变。
- `MessageBubble` / `ChatInput` / `ChatContainer` 对外 props 接口向后兼容（仅新增可选 prop）。
