# TDD 测试用例: 聊天界面升级为 Ant Design X

> 编码: UTF-8
> 图例: 红色 = 未验证（待实现）, 绿色 = 已通过
> 验证方式: Vitest + React Testing Library 组件测试 + `npm run build` 类型检查 + `npm run test`

---

## 测试分组一：依赖与构建 (TC-AX-001)

对应规范: SPEC-AX-001

| ID | 测试用例 | 验证方法 | 状态 |
|----|---------|---------|:--:|
| TC-AX-001-01 | `package.json` dependencies 包含 `@ant-design/x` 且版本为 2.x | 检查文件 | 绿色 |
| TC-AX-001-02 | `npm run build` 生产构建成功，无类型错误 | 命令行 | 红色（被项目既有技术债阻断，非本次范围） |
| TC-AX-001-03 | `npm run test` 全部用例通过 | 命令行 | 绿色 |

---

## 测试分组二：Sender 输入组件 (TC-AX-002)

对应规范: SPEC-AX-002（自动化组件测试 `ChatInput.test.tsx`）

| ID | 测试用例 | 验证方法 | 状态 |
|----|---------|---------|:--:|
| TC-AX-002-01 | 输入文本点击发送，`onSend` 被调用且传入文本，输入框清空 | Vitest | 绿色 |
| TC-AX-002-02 | 空输入发送，`onSend` 不被调用 | Vitest | 绿色 |
| TC-AX-002-03 | `disabled=true` 时无法触发发送 | Vitest | 绿色 |
| TC-AX-002-04 | 传入 `fillText` 后自动填入并触发 `onFillTextConsumed` | Vitest | 绿色 |
| TC-AX-002-05 | 渲染出 `Sender`（含 `ant-sender` 语义类） | Vitest | 绿色 |

---

## 测试分组三：Bubble 消息气泡 (TC-AX-003)

对应规范: SPEC-AX-003（自动化组件测试 `MessageBubble.test.tsx`）

| ID | 测试用例 | 验证方法 | 状态 |
|----|---------|---------|:--:|
| TC-AX-003-01 | 用户消息渲染为 `placement=end`（右对齐） | Vitest | 绿色 |
| TC-AX-003-02 | AI 消息渲染为 `placement=start`（左对齐） | Vitest | 绿色 |
| TC-AX-003-03 | 系统消息渲染为居中提示 | Vitest | 绿色 |
| TC-AX-003-04 | Markdown 表格渲染为 `<table>` 元素 | Vitest | 绿色 |
| TC-AX-003-05 | 含来源的消息渲染来源卡片 | Vitest | 绿色 |
| TC-AX-003-06 | 含推理链的消息渲染"推理过程"折叠区 | Vitest | 绿色 |

---

## 测试分组四：Conversations 会话列表 (TC-AX-004)

对应规范: SPEC-AX-004（自动化组件测试 `ChatContainer.test.tsx`）

| ID | 测试用例 | 验证方法 | 状态 |
|----|---------|---------|:--:|
| TC-AX-004-01 | 会话列表渲染出 `Conversations`（含 `ant-conversations` 语义类） | Vitest | 绿色 |
| TC-AX-004-02 | 点击"新建对话"触发 `createNewSession` | Vitest | 绿色 |
| TC-AX-004-03 | 点击会话项触发 `switchSession` | Vitest | 绿色 |
| TC-AX-004-04 | 空消息态渲染 `Welcome` 欢迎组件 | Vitest | 绿色 |
| TC-AX-004-05 | 有消息时隐藏 `Welcome`，展示消息气泡 | Vitest | 绿色 |

---

## 测试分组五：功能回归 (TC-AX-005)

对应规范: SPEC-AX-006

| ID | 测试用例 | 验证方法 | 状态 |
|----|---------|---------|:--:|
| TC-AX-005-01 | 未改动的 `ThoughtChainDrawer` 测试保持通过 | Vitest | 绿色 |
| TC-AX-005-02 | 未改动的 `ChartContainer` / `DagFlow` / `agentEvent` 测试保持通过 | Vitest | 绿色 |
| TC-AX-005-03 | 主题亮/暗色下 `@ant-design/x` 组件正常渲染（无报错） | Vitest | 绿色 |
