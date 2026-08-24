# 任务清单: 聊天界面可视化优化

> 编码: UTF-8
> 每完成一项后对照 `specs/tdd-chat-ui-polish.md` 将对应测试标绿。

---

## 阶段零：规范与准备

- [x] 0.1 创建 `openspec/changes/chat-ui-polish/` 目录结构
- [x] 0.2 编写 `proposal.md`
- [x] 0.3 编写 `design.md`
- [x] 0.4 编写 `specs/spec-chat-ui-polish.md`
- [x] 0.5 编写 `specs/tdd-chat-ui-polish.md`（全线标红）

---

## 阶段一：聊天区铺满

- [x] 1.1 `theme.ts` 补充 `chatAreaLight` / `chatAreaDark` / `borderDark` 语义色
- [x] 1.2 `AppLayout.tsx` 聊天路由去 padding、`overflow: hidden`

---

## 阶段二：暗色颜色统一

- [x] 2.1 `ChatContainer.tsx` 硬编码颜色替换为语义色
- [x] 2.2 `ChatPage.tsx` 面板硬编码颜色替换为语义色
- [x] 2.3 `MessageBubble.tsx` 气泡硬编码颜色替换为语义色

---

## 阶段三：流式打字机光标

- [x] 3.1 `MessageBubble.tsx` 新增 `isStreaming` prop 并渲染光标
- [x] 3.2 `ChatContainer.tsx` 传递 `isStreaming` 给最后一条 assistant 消息
- [x] 3.3 `global.css` 定义 `.typing-cursor` 闪烁动画

---

## 阶段四：TDD 验证与回归

- [x] 4.1 新增 `chat-ui-polish` 测试用例（theme / MessageBubble / AppLayout）
- [x] 4.2 运行 `npm run test` 全量通过（9 文件 / 89 用例）
- [x] 4.3 对照 `specs/tdd-chat-ui-polish.md` 逐条标绿
