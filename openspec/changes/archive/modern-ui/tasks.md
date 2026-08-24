# 任务清单: 现代化前端展示界面 (Modern UI)

> 编码: UTF-8
> 每完成一项后对照 `specs/tdd-frontend-ui.md` 将对应测试标绿。

---

## 阶段零：规范与准备（已完成）

- [x] 0.1 创建 `openspec/changes/modern-ui/` 目录结构
- [x] 0.2 编写 `proposal.md` - 变更提案
- [x] 0.3 编写 `design.md` - 技术设计
- [x] 0.4 编写 `specs/spec-frontend-ui.md` - 功能规范
- [x] 0.5 编写 `specs/tdd-frontend-ui.md` - 测试用例（全线标红）

---

## 阶段一：Phase 1 - 最小化对话界面（已完成）

> 目标：替换 Streamlit 核心问答功能，验证前后端分离架构
> 对应 TDD: TC-FE-001 至 TC-FE-006 (48 条用例)
> 对应 Spec: SPEC-FE-001 至 SPEC-FE-006
> 完成日期: 2026-06-25

### 1.1 项目脚手架搭建

- [x] 1.1.1 创建 `frontend/` 目录，使用 Vite 初始化 React + TypeScript 项目
- [x] 1.1.2 安装核心依赖: react, react-dom, react-router-dom, antd, @ant-design/icons, axios, zustand, dayjs
- [x] 1.1.3 安装开发依赖: @types/react, @types/react-dom, @vitejs/plugin-react, typescript, vite
- [x] 1.1.4 配置 `vite.config.ts`（API 代理到 localhost:8000，端口 5173）
- [x] 1.1.5 配置 TypeScript 严格模式
- [x] 1.1.6 创建 `.env.development` (VITE_API_BASE_URL)
- [x] 1.1.7 验证: `npm run dev` 启动成功，空白页面可访问

### 1.2 主题与全局样式

- [x] 1.2.1 创建 `src/styles/theme.ts` - Ant Design 主题 token 定义（深蓝+金色）
- [x] 1.2.2 创建 `src/styles/global.css` - 全局样式（滚动条、等宽字体）
- [x] 1.2.3 创建 `src/hooks/useTheme.ts` - 主题切换 Hook（localStorage 持久化）
- [x] 1.2.4 创建 `src/stores/appStore.ts` - 全局应用状态（主题、侧边栏折叠）
- [x] 1.2.5 验证: 亮色/暗色切换正常，刷新页面保持

### 1.3 布局组件

- [x] 1.3.1 创建 `src/components/layout/AppLayout.tsx` - 全局布局（侧边栏 + 顶栏 + 内容区）
- [x] 1.3.2 创建 `src/components/layout/Sidebar.tsx` - 左侧导航菜单（5 个入口 + 主题切换）
- [x] 1.3.3 创建 `src/components/layout/HeaderBar.tsx` - 顶部栏（项目标题 + 系统状态指示灯）
- [x] 1.3.4 验证: 侧边栏导航切换，页面路由跟随切换

### 1.4 API 对接层

- [x] 1.4.1 创建 `src/services/api.ts` - axios 实例 + 拦截器（conversation_id 注入）
- [x] 1.4.2 创建 `src/services/chatService.ts` - 封装 `/api/query`, `/api/health`, `/api/companies`
- [x] 1.4.3 验证: DevTools Network 面板看到 API 请求正常

### 1.5 类型定义

- [x] 1.5.1 创建 `src/types/chat.ts` - Message, Session, Source 等类型定义
- [x] 1.5.2 验证: TypeScript 编译无错误

### 1.6 对话首页

- [x] 1.6.1 创建 `src/stores/chatStore.ts` - 对话状态管理（sessions, messages, 会话切换）
- [x] 1.6.2 创建 `src/components/chat/ChatContainer.tsx` - 对话容器（消息列表 + 输入框）
- [x] 1.6.3 创建 `src/components/chat/MessageBubble.tsx` - 消息气泡（左对齐 AI / 右对齐用户）
- [x] 1.6.4 创建 `src/components/chat/ChatInput.tsx` - 输入区域（文本框 + 发送按钮 + 快捷键 Enter）
- [x] 1.6.5 创建 `src/components/chat/SourceCard.tsx` - 引用来源卡片
- [x] 1.6.6 创建 `src/components/common/LoadingSpinner.tsx` - 加载动画
- [x] 1.6.7 创建 `src/pages/ChatPage.tsx` - 对话首页组件
- [x] 1.6.8 集成 react-markdown 渲染 AI 回答中的 Markdown 格式
- [x] 1.6.9 验证: 完整对话流程（输入 → loading → 回答 → 来源展示）

### 1.7 会话管理

- [x] 1.7.1 chatStore 实现：新建会话、切换会话、消息持久化（localStorage）
- [x] 1.7.2 左侧会话列表 UI（可折叠/展开）
- [x] 1.7.3 清空对话功能（二次确认弹窗）
- [x] 1.7.4 验证: 多会话创建、切换、消息隔离

### 1.8 侧边栏配置

- [x] 1.8.1 公司选择下拉框（调用 `/api/companies`）
- [x] 1.8.2 检索返回条数滑块（1-10，默认 5）
- [x] 1.8.3 意图识别开关
- [x] 1.8.4 系统状态指示器（调用 `/api/health`）
- [x] 1.8.5 示例问题快捷入口
- [x] 1.8.6 验证: 所有配置项正常发送到 API 请求

### 1.9 错误处理与边界

- [x] 1.9.1 创建 `src/components/common/ErrorBoundary.tsx` - React 错误边界
- [x] 1.9.2 API 错误统一处理（网络错误、超时、后端错误码）
- [x] 1.9.3 空消息校验
- [x] 1.9.4 后端不可用时的降级提示
- [x] 1.9.5 验证: 模拟各种错误场景

### 1.10 占位页面

- [x] 1.10.1 创建 `src/pages/DagBoardPage.tsx` - "功能开发中"占位
- [x] 1.10.2 创建 `src/pages/ChartsPage.tsx` - "功能开发中"占位
- [x] 1.10.3 创建 `src/pages/KnowledgePage.tsx` - "功能开发中"占位
- [x] 1.10.4 创建 `src/pages/SettingsPage.tsx` - "功能开发中"占位

### 1.11 路由与入口

- [x] 1.11.1 配置 `App.tsx` - React Router 路由表
- [x] 1.11.2 创建 `src/main.tsx` - 应用入口
- [x] 1.11.3 创建 `index.html` - Vite HTML 入口
- [x] 1.11.4 验证: 五个页面路由全部可访问

### 1.12 TDD 验证（Phase 1 完成标志）

- [x] 1.12.1 对照 `specs/tdd-frontend-ui.md` 逐条验证（48 条用例）
- [x] 1.12.2 验证通过的用例标绿，失败标红记录原因
- [x] 1.12.3 48 条全部通过 → Phase 1 交付完成

---

## 阶段二：Phase 2 - Agent 可视化 + 交互图表（已完成）

> 依赖: Phase 1 完成 + 后端扩展流式接口
> 完成日期: 2026-07-01
> 优化版本: 2026-07-01 (边缘情况修复 + 日志增强)

- [√] 2.1 扩展后端: 新增 `/api/agent/stream` SSE 端点（返回 Agent 中间步骤）
- [√] 2.2 移除 `/api/query` 的 `include_agent_details` 参数方案（简化设计，Agent 能力统一走 SSE 端点）
- [√] 2.3 安装 echarts, echarts-for-react 依赖
- [√] 2.4 创建 `src/components/chat/ThoughtChainDrawer.tsx` - Agent 思维链侧边抽屉
- [√] 2.5 SSE 流式响应处理（已内置在 chatService.ts streamAgentQuery + ChatPage handleSend 中）
- [√] 2.6 更新 ChatContainer: 集成思维链展示 + 新增 onViewReasoning 回调
- [√] 2.7 安装 @antv/g6 依赖
- [√] 2.8 创建 `src/components/dag/DagFlow.tsx` - DAG 流程图组件（@antv/g6 v5）
- [√] 2.9 创建 DagBoardPage.tsx - DAG 看板页面（替换占位，含查询输入 + 图例 + 执行批次）
- [√] 2.10 创建 `src/components/charts/ChartContainer.tsx` - ECharts 图表容器（柱/折/饼，按需注册）
- [√] 2.11 更新 ChartsPage: 集成交互式图表展示（从 /api/charts/list 加载，支持类型筛选）
- [√] 2.11b 后端: chart_tool 同步输出 JSON 结构化数据
- [√] 2.11c 后端: 新增 `/api/charts/list` 接口（返回图表列表 + JSON 数据）
- [√] 2.11d 后端: 新增 `/api/agent/plan` 接口（返回规划 DAG 数据）
- [√] 2.12 更新 TDD 用例（新增 Phase 2 + Phase 3 测试项，共 7 分组 52 条，全线标红）
- [√] 2.13 侧边栏重构：移除意图开关 + 新增 Agent 深度推理 + 高级选项折叠
  - [√] 2.13.1 移除"意图识别与改写"开关，前端固定传 `enable_rewrite=true`
  - [√] 2.13.2 新增"Agent 深度推理"开关（默认关闭），开启后调用 SSE 端点
  - [√] 2.13.3 "检索返回条数"滑块移入可折叠的"高级选项"面板
  - [√] 2.13.4 更新 ChatPage.tsx 的 handleSend 逻辑：Agent 模式走 SSE，普通模式走 /api/query
  - [√] 2.13.5 更新 TDD 用例（TC-FE-003-06 改为验证意图识别自动生效，新增 TC-FE-014 侧边栏重构测试）
- [√] 2.14 更新 ChatPage.tsx 移除意图开关 UI，新增 Agent 开关 UI

---

## 阶段三：Phase 3 - 管理后台 + 完善（完成于 2026-08-10）

- [x] 3.1 扩展后端: 新增知识库管理接口（文档列表、上传、索引状态）
- [x] 3.2 实现 KnowledgePage（文档列表 + 索引状态）
- [x] 3.3 新增 PDF 上传功能
- [x] 3.4 实现 SettingsPage（只读监控面板，v1.2 修正）
- [x] 3.5 扩展后端: 新增系统状态接口
- [x] 3.6 响应式适配优化（移动端，responsive.css）
- [x] 3.7 生产构建优化（代码分割、懒加载）
- [ ] 3.8 Nginx 部署配置（待后续实施）
- [x] 3.9 最终 TDD 全量验证（101/108 绿，7 红为待实施项：移动端汉堡菜单 + Nginx 部署）
