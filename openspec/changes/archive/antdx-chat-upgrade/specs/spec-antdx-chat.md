# 功能规范: 聊天界面升级为 Ant Design X

> 编码: UTF-8
> 范围: 仅聊天交互组件（ChatInput / MessageBubble / ChatContainer），不涉及后端与其他页面

---

## SPEC-AX-001: 依赖安装与组件引入

### 描述
安装 `@ant-design/x` 依赖，并在聊天组件中正确引入 `Sender` / `Bubble` / `Conversations` / `Welcome`。

### 场景

| ID | 场景 | 预期 |
|----|------|------|
| AX-001-01 | `npm install @ant-design/x` | 依赖写入 `package.json` dependencies，版本为 2.x |
| AX-001-02 | 组件中 `import { Sender, Bubble, Conversations, Welcome } from '@ant-design/x'` | TypeScript 编译通过，无模块找不到错误 |
| AX-001-03 | 运行 `npm run build` | 生产构建成功，无类型错误 |

---

## SPEC-AX-002: Sender 输入组件

### 描述
`ChatInput` 使用 `Sender` 组件，保留 `onSend` / `disabled` / `fillText` / `onFillTextConsumed` 对外接口不变。

### 场景

| ID | 场景 | 预期 |
|----|------|------|
| AX-002-01 | 输入文本后点击发送按钮 | 触发 `onSend` 且传入去空格后的文本，输入框清空 |
| AX-002-02 | 在输入框按 Enter | 触发发送（不换行） |
| AX-002-03 | 在输入框按 Shift+Enter | 换行，不触发发送 |
| AX-002-04 | 输入框为空时发送 | 不触发 `onSend` |
| AX-002-05 | `disabled=true` | 输入框不可输入，发送按钮不可用 |
| AX-002-06 | 外部传入 `fillText` | 自动填入输入框，并调用 `onFillTextConsumed` |
| AX-002-07 | 输入框聚焦 | 支持多行（minRows=1, maxRows=4）自适应高度 |

---

## SPEC-AX-003: Bubble 消息气泡

### 描述
`MessageBubble` 使用 `Bubble` 组件渲染用户 / AI / 系统三种消息。

### 场景

| ID | 场景 | 预期 |
|----|------|------|
| AX-003-01 | 用户消息 | 气泡右对齐（placement=end），填充式（filled）样式 |
| AX-003-02 | AI 消息 | 气泡左对齐（placement=start），描边式（outlined）样式 |
| AX-003-03 | 系统消息 | 居中灰色提示样式 |
| AX-003-04 | AI 消息含 Markdown 表格 | 正确渲染为 HTML `<table>`（非纯文本） |
| AX-003-05 | AI 消息含引用来源 | 气泡下方展示来源卡片列表 |
| AX-003-06 | AI 消息含推理链 | 气泡下方展示可折叠的推理过程摘要 |
| AX-003-07 | AI 消息含多 Agent 状态 | 气泡下方展示 Worker 运行状态 |
| AX-003-08 | 消息含时间戳 | 气泡下方展示时间戳 |

---

## SPEC-AX-004: Conversations 会话列表

### 描述
`ChatContainer` 会话列表使用 `Conversations` 组件。

### 场景

| ID | 场景 | 预期 |
|----|------|------|
| AX-004-01 | 会话列表渲染 | 每个会话显示标题，当前会话高亮 |
| AX-004-02 | 点击"新建对话" | 调用 `createNewSession`，创建并切换到新会话 |
| AX-004-03 | 点击会话项 | 调用 `switchSession`，切换到该会话 |
| AX-004-04 | 会话删除入口 | 通过会话项操作菜单删除会话，调用 `deleteSession` |
| AX-004-05 | 清空当前会话 | 底部"清空对话"按钮触发二次确认后清空消息 |

---

## SPEC-AX-005: Welcome 欢迎页

### 描述
空消息态使用 `Welcome` 组件展示欢迎信息。

### 场景

| ID | 场景 | 预期 |
|----|------|------|
| AX-005-01 | 无消息且非加载态 | 显示欢迎图标 + 标题"您好，我是企业财务年报分析助手" + 副标题 |
| AX-005-02 | 有消息后 | 欢迎区隐藏，展示消息列表 |

---

## SPEC-AX-006: 功能回归

### 描述
替换组件后，既有核心功能不受影响。

### 场景

| ID | 场景 | 预期 |
|----|------|------|
| AX-006-01 | 普通 RAG 模式发送 | 调用 `/api/query`，回答与来源正常展示 |
| AX-006-02 | Agent 模式（SSE）发送 | 调用 `/api/agent/stream`，推理链 / 多 Agent 状态流式更新 |
| AX-006-03 | 自动滚动 | 新消息到达时自动滚动到底部 |
| AX-006-04 | 其他页面 | `/dag` `/charts` `/knowledge` `/settings` 路由零改动、正常渲染 |
| AX-006-05 | 主题切换 | 亮/暗色下 `@ant-design/x` 组件跟随主题正常显示 |
