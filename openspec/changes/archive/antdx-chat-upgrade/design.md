# 技术设计: 聊天界面升级为 Ant Design X

> 编码: UTF-8
> 关联变更: `openspec/changes/antdx-chat-upgrade/`

---

## 一、目标与原则

在**不修改后端、不修改其他页面、不改变现有状态管理与 SSE 逻辑**的前提下，仅将聊天交互相关的 UI 组件替换为 `@ant-design/x` 组件库，把界面观感从"功能实现"提升到 LobeChat / ChatGPT 级别。

**约束**：
- 保留 `zustand` 状态管理（`chatStore`），不引入 `useXChat`。
- 保留现有 SSE 处理逻辑（`streamAgentQuery` + `applyAgentEvent`），不引入 `XStream`。
- 保留 `SourceCard`、`ThoughtChainDrawer`、`LoadingSpinner` 等辅助组件不变。
- 不修改 `ChatPage.tsx` 的对外交互逻辑（`ChatContainer` props 接口不变）。

---

## 二、组件映射

| 旧实现 | 新实现 | 来源 |
|--------|--------|------|
| `ChatInput.tsx`（antd `TextArea` + `Button`） | `Sender` | `@ant-design/x` |
| `MessageBubble.tsx`（自定义 `div` + `dangerouslySetInnerHTML`） | `Bubble`（`placement` / `variant` / `shape` / `avatar` / `footer`） | `@ant-design/x` |
| `ChatContainer.tsx` 会话列表（自定义 `div` + `Popconfirm`） | `Conversations`（`items` / `activeKey` / `menu` / `creation`） | `@ant-design/x` |
| `ChatContainer.tsx` 欢迎区（内联 `div`） | `Welcome`（`icon` / `title` / `description`） | `@ant-design/x` |
| Markdown 渲染（`formatMarkdown` + `dangerouslySetInnerHTML`） | 保留现有 `formatMarkdown`，通过 `Bubble` 的 `content` 传入 ReactNode | 自有实现 |

> 说明：`@ant-design/x` 2.9.0 未内置 XMarkdown（该能力位于独立包 `@ant-design/x-markdown`）。为遵循最小变更原则，本变更**保留**现有 `formatMarkdown` 渲染逻辑，仅更换外层气泡壳，避免引入额外依赖与渲染差异风险。

---

## 三、各组件改造方案

### 3.1 ChatInput → Sender

`Sender` 原生支持 `Enter` 发送 / `Shift+Enter` 换行、`autoSize`、`loading` 态，替换后交互与旧实现一致。

```tsx
<Sender
  value={value}
  onChange={setValue}
  onSubmit={(text) => { onSend(text); setValue(''); }}
  loading={disabled}
  disabled={disabled}
  placeholder="请输入您的问题... (Enter 发送, Shift+Enter 换行)"
  autoSize={{ minRows: 1, maxRows: 4 }}
  className="chat-sender"
/>
```

对外 props 保持 `onSend` / `disabled` / `fillText` / `onFillTextConsumed` 不变。

### 3.2 MessageBubble → Bubble

单条消息用 `Bubble` 承载：

| Message.role | Bubble 配置 |
|--------------|-------------|
| `user` | `placement="end"`、`variant="filled"`、`shape="corner"`、`avatar` 用户图标 |
| `assistant` | `placement="start"`、`variant="outlined"`、`shape="corner"`、`avatar` 机器人图标 |
| `system` | 居中灰色提示（沿用现有实现，`Bubble.List` 的 `system` 语义不在单气泡中使用） |

- `content`：`formatMarkdown(message.content)` 生成的 ReactNode（`dangerouslySetInnerHTML`）。
- `footer`：引用来源卡片 + 推理链折叠区 + 多 Agent 状态 + 时间戳（沿用现有 JSX）。
- 视觉细节（马卡龙渐变、玻璃拟态、边框色）通过 `styles` / `classNames` 语义槽覆盖，保持现有主题观感。

### 3.3 ChatContainer 会话列表 → Conversations

```tsx
<Conversations
  items={sessions.map((s) => ({ key: s.id, label: s.title }))}
  activeKey={currentSessionId}
  onActiveChange={(key) => switchSession(key as string)}
  menu={(item) => ({
    items: [{ key: 'delete', label: '删除对话', danger: true }],
    onClick: ({ key }) => { if (key === 'delete') deleteSession(item.key); },
  })}
  creation={{ label: '新建对话', icon: <PlusOutlined />, onClick: createNewSession }}
/>
```

"清空对话"按钮保留在列表底部（沿用 `Popconfirm` 二次确认）。

### 3.4 ChatContainer 欢迎区 → Welcome

空消息态用 `Welcome` 展示图标、标题、副标题：

```tsx
<Welcome
  icon={<MessageOutlined />}
  title="您好，我是企业财务年报分析助手"
  description="请输入您的问题，或点击下方示例快速开始"
/>
```

示例问题仍保留在 `ChatPage` 左侧配置面板（不迁移，最小改动）。

### 3.5 消息列表

沿用 `ChatContainer` 内 `currentMessages.map(msg => <MessageBubble .../>)` 循环，保持逐条渲染与现有自动滚动逻辑不变（`MessageBubble` 内部改为 `Bubble`）。

---

## 四、主题与样式

`@ant-design/x` 组件基于 antd 的 token 体系渲染，会自动继承 `AppLayout` 中 `ConfigProvider` 的主题配置（马卡龙配色），无需额外注册 `XProvider`。

为对齐现有马卡龙渐变 / 玻璃拟态视觉，在 `global.css` 追加少量 `@ant-design/x` 语义类覆盖（如 `.ant-bubble`、`.ant-sender` 的边框/圆角/阴影）。

---

## 五、风险与应对

| 风险 | 应对 |
|------|------|
| `Conversations` 的 `menu` 触发交互与预期不符 | 删除操作沿用菜单项，若触发不可达则回退为悬停删除图标 |
| `Bubble` 与 `dangerouslySetInnerHTML` 组合的样式冲突 | 仅在 `content` 内复用现有 `markdown-body` class，气泡壳样式交给 `Bubble` |
| 主题 token 未透传到 `@ant-design/x` | 验证后若缺失，在 `AppLayout` 增加 `XProvider` 包裹 |
| 现有测试失败 | 新增 `@ant-design/x` 组件测试；`ThoughtChainDrawer` 等未改动测试应保持通过 |

---

## 六、版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0-dev | 2026-08-20 | 初始化设计 |
