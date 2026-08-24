# 功能规范: 聊天界面可视化优化

> 编码: UTF-8

## SPEC-UI-001: 聊天区铺满

聊天首页 `/` 的 `Content` 内边距为 0，`overflow` 为 `hidden`，聊天区占满整个内容区域；其他路由保持 `padding: 24` 与 `overflow: auto` 不变。

## SPEC-UI-002: 暗色颜色统一

- `theme.ts` 的 `colors` 导出 `chatAreaLight`、`chatAreaDark`、`borderDark` 三个语义色。
- ChatContainer、ChatPage、MessageBubble 中不再使用与主题 token 不一致的硬编码背景/边框色，统一引用 `colors` 语义色。
- 亮色与暗色模式下，会话列表、聊天区、配置面板、AI 气泡背景颜色彼此协调。

## SPEC-UI-003: 流式打字机光标

- `MessageBubble` 支持 `isStreaming` 可选 prop（默认 `false`）。
- 当 AI 消息处于流式输出状态（`isStreaming === true`）时，消息内容末尾渲染一个带 `typing-cursor` 类的光标元素。
- 用户消息与系统消息不渲染光标。
- 非流式状态下不渲染光标。
