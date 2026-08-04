# 前端 — 企业级财务年报分析智能 RAG-Agent

> 基于 React 18 + TypeScript + Ant Design 5 的现代化前端界面
> 进度: Phase 1 (对话界面) + Phase 2 (Agent 可视化 / 交互图表) 已完成

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 构建工具 | Vite 5 |
| UI 框架 | React 18 + TypeScript |
| 组件库 | Ant Design 5 |
| 图表 | ECharts + echarts-for-react |
| 流程图 | @antv/g6 v5 (DAG 展示) |
| 状态管理 | Zustand |
| 测试 | Vitest + React Testing Library + jsdom |

---

## 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器 (http://localhost:5173)
npm run dev

# 生产构建
npm run build

# 运行单元测试
npm test              # Vitest 一次性运行 (47 条)
npm run test:watch    # 监视模式
```

---

## 项目结构

```
frontend/src/
├── components/
│   ├── chat/
│   │   ├── ChatContainer.tsx      # 对话容器（消息列表 + 输入框）
│   │   ├── ChatInput.tsx          # 输入区域（文本 + 发送 + 快捷键）
│   │   ├── MessageBubble.tsx      # 消息气泡（Markdown + 推理链摘要）
│   │   ├── ThoughtChainDrawer.tsx # 思维链侧边抽屉（Phase 2）
│   │   └── SourceCard.tsx         # 引用来源卡片
│   ├── charts/
│   │   └── ChartContainer.tsx     # ECharts 交互图表容器（Phase 2）
│   ├── dag/
│   │   └── DagFlow.tsx            # @antv/g6 DAG 流程图（Phase 2）
│   ├── common/
│   │   ├── ErrorBoundary.tsx      # React 错误边界
│   │   └── LoadingSpinner.tsx     # 加载动画
│   └── layout/
│       ├── AppLayout.tsx          # 全局布局（侧边栏 + 内容区）
│       ├── Sidebar.tsx            # 左侧导航菜单
│       └── HeaderBar.tsx          # 顶部栏 + 系统状态
├── pages/
│   ├── ChatPage.tsx               # 对话首页（默认路由）
│   ├── ChartsPage.tsx             # 图表中心（Phase 2）
│   ├── DagBoardPage.tsx           # DAG 看板（Phase 2）
│   ├── KnowledgePage.tsx          # 知识库管理（Phase 3 待实现）
│   └── SettingsPage.tsx           # 系统设置（Phase 3 待实现）
├── services/
│   ├── api.ts                     # axios 实例 + 拦截器
│   └── chatService.ts             # API 封装 + SSE 流式处理
├── stores/
│   ├── appStore.ts                # 全局状态（主题、侧边栏）
│   └── chatStore.ts               # 对话状态（会话、消息）
├── hooks/
│   └── useTheme.ts                # 主题切换 Hook
├── styles/
│   ├── theme.ts                   # Ant Design 主题 token
│   └── global.css                 # 全局样式
├── constants/
│   └── dag.ts                     # DAG 类型颜色常量
├── types/
│   └── chat.ts                    # 消息/会话/Agent 流式类型定义
└── vitest-setup.ts                # 测试全局 setup
```

---

## 页面路由

| 路由 | 页面 | 状态 |
|------|------|:--:|
| `/` | 智能问答中心 | Phase 1 完成 |
| `/dag` | DAG 任务规划看板 | Phase 2 完成 |
| `/charts` | 交互式数据图表 | Phase 2 完成 |
| `/knowledge` | 知识库管理 | Phase 3 待实现 |
| `/settings` | 系统设置与监控 | Phase 3 待实现 |

---

## 测试

```bash
# 运行所有前端组件测试
npm test

# 监视模式（开发时使用）
npm run test:watch
```

测试文件位于 `src/components/*/__tests__/`：

| 测试文件 | 用例数 | 覆盖率 |
|---------|:-----:|:--:|
| ChartContainer.test.tsx | 22 | 颜色覆盖、类型切换、空数据、tooltip formatter |
| ThoughtChainDrawer.test.tsx | 17 | 时间线节点、步骤渲染、展开折叠 |
| DagFlow.test.tsx | 8 | useMemo 稳定比较、G6 实例管理、卸载清理 |
| **合计** | **47** | **全部 GREEN** |
