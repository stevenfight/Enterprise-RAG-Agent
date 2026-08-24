# 任务清单: 聊天界面升级为 Ant Design X

> 编码: UTF-8
> 每完成一项后对照 `specs/tdd-antdx-chat.md` 将对应测试标绿。

---

## 阶段零：规范与准备

- [x] 0.1 创建 `openspec/changes/antdx-chat-upgrade/` 目录结构
- [x] 0.2 编写 `proposal.md` - 变更提案
- [x] 0.3 编写 `design.md` - 技术设计
- [x] 0.4 编写 `specs/spec-antdx-chat.md` - 功能规范
- [x] 0.5 编写 `specs/tdd-antdx-chat.md` - 测试用例（全线标红）

---

## 阶段一：依赖安装与兼容性验证

- [x] 1.1 安装 `@ant-design/x@^2.9.0` 依赖
- [x] 1.2 验证 `@ant-design/x` 与 antd 6 / React 19 兼容（tsc 编译）
- [ ] 1.3 验证 `npm run build` 构建通过（被项目既有技术债阻断，见 6.2 备注）

---

## 阶段二：输入组件替换

- [x] 2.1 重写 `ChatInput.tsx`，使用 `Sender` 组件
- [x] 2.2 保留 `onSend` / `disabled` / `fillText` / `onFillTextConsumed` 接口
- [x] 2.3 新增 `ChatInput.test.tsx` 组件测试

---

## 阶段三：消息气泡替换

- [x] 3.1 重写 `MessageBubble.tsx`，使用 `Bubble` 组件
- [x] 3.2 保留 Markdown 渲染、来源、推理链、多 Agent 状态、时间戳
- [x] 3.3 新增 `MessageBubble.test.tsx` 组件测试

---

## 阶段四：会话列表与欢迎页替换

- [x] 4.1 重写 `ChatContainer.tsx`，使用 `Conversations` + `Welcome`
- [x] 4.2 保留会话切换 / 删除 / 清空 / 自动滚动逻辑
- [x] 4.3 新增 `ChatContainer.test.tsx` 组件测试

---

## 阶段五：样式与主题对齐

- [x] 5.1 在 `global.css` 追加 `@ant-design/x` 语义类覆盖（气泡/输入框边框、圆角、阴影）
- [x] 5.2 验证亮/暗色主题下组件观感（组件测试渲染无报错）

---

## 阶段六：TDD 验证与回归

- [x] 6.1 运行 `npm run test` 全量测试通过（80/80）
- [ ] 6.2 运行 `npm run build` 构建通过（被项目既有技术债阻断，非本次聊天 UI 替换范围）
- [x] 6.3 对照 `specs/tdd-antdx-chat.md` 逐条标绿
- [ ] 6.4 确认其他页面（DAG / 图表 / 知识库 / 设置）无回归（其类型错误为既有技术债）
