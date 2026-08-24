# 技术设计: 现代化前端展示界面 (Modern UI)

> 编码: UTF-8

---

## 一、整体架构

### 1.1 现状 vs 目标

```
现状（前后端混合）:
┌─────────────────────────────────────────────┐
│  Streamlit (app_streamlit.py)               │
│  ┌──────────────────────────────────────┐   │
│  │  UI 渲染 + 后端逻辑 + API 调用      │   │
│  └──────────────────────────────────────┘   │
│       │                                     │
│       ▼                                     │
│  FastAPI (src/api_service.py)               │
│  ┌──────────────────────────────────────┐   │
│  │  REST API: /api/query, /api/health   │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘

目标（前后端分离）:
┌──────────────────────────┐   HTTP/JSON   ┌───────────────────────┐
│  React Frontend          │ ◄──────────► │  FastAPI Backend      │
│  ┌────────────────────┐  │              │  ┌───────────────────┐ │
│  │ Vite + React 18    │  │              │  │ /api/query        │ │
│  │ + Ant Design       │  │              │  │ /api/retrieve     │ │
│  │ + ECharts          │  │              │  │ /api/companies    │ │
│  │ + AntV G6/ReactFlow│  │              │  │ /api/health       │ │
│  └────────────────────┘  │              │  └───────────────────┘ │
│                          │              │  (Phase 1 不修改)      │
│  独立部署到 Nginx/CDN    │              │  独立部署到 Uvicorn     │
└──────────────────────────┘              └───────────────────────┘

Streamlit (保留不变):
┌─────────────────────────────────────────────┐
│  streamlit run app_streamlit.py             │
│  作为快速调试/内部使用入口，不做修改          │
└─────────────────────────────────────────────┘
```

### 1.2 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI 后端 | 8000 | 现有接口，不变 |
| React Dev Server | 5173 | Vite 开发模式 |
| React 生产构建 | 80/443 | Nginx 部署 |
| Streamlit | 8501 | 备用入口 |

---

## 二、前端项目结构

```
frontend/
├── index.html                      # Vite 入口 HTML
├── package.json                    # 依赖与脚本
├── tsconfig.json                   # TypeScript 配置
├── vite.config.ts                  # Vite 配置 (含 API 代理)
├── .env.development                # 开发环境变量
├── .env.production                 # 生产环境变量
│
├── public/
│   └── favicon.svg                 # 网站图标
│
└── src/
    ├── main.tsx                    # React 入口
    ├── App.tsx                     # 根组件 (路由 + 布局)
    ├── vite-env.d.ts              # Vite 类型声明
    │
    ├── pages/                      # 页面组件
    │   ├── ChatPage.tsx            # 智能问答中心（首页）
    │   ├── DagBoardPage.tsx        # DAG 任务规划看板 (Phase 2)
    │   ├── ChartsPage.tsx          # 数据图表中心 (Phase 2)
    │   ├── KnowledgePage.tsx       # 知识库管理 (Phase 3)
    │   └── SettingsPage.tsx        # 系统设置与监控 (Phase 3)
    │
    ├── components/                 # 通用组件
    │   ├── layout/
    │   │   ├── AppLayout.tsx       # 全局布局 (侧边栏 + 顶栏 + 内容区)
    │   │   ├── Sidebar.tsx         # 左侧导航菜单
    │   │   └── HeaderBar.tsx       # 顶部栏 (标题 + 主题切换)
    │   ├── chat/
    │   │   ├── ChatContainer.tsx   # 对话容器 (消息列表 + 输入框)
    │   │   ├── MessageBubble.tsx   # 消息气泡 (用户/AI/系统)
    │   │   ├── ChatInput.tsx       # 输入区域 (文本框 + 发送按钮)
    │   │   ├── ThoughtChain.tsx    # Agent 思维链侧边抽屉 (Phase 2)
    │   │   └── SourceCard.tsx      # 引用溯源卡片
    │   ├── charts/
    │   │   └── ChartContainer.tsx  # ECharts 图表容器 (Phase 2)
    │   ├── dag/
    │   │   └── DagFlow.tsx         # DAG 流程图组件 (Phase 2)
    │   └── common/
    │       ├── LoadingSpinner.tsx  # 加载状态
    │       └── ErrorBoundary.tsx   # 错误边界
    │
    ├── services/                   # API 对接层
    │   ├── api.ts                  # axios 实例 + 拦截器
    │   ├── chatService.ts          # 问答相关 API
    │   ├── knowledgeService.ts     # 知识库管理 API (Phase 3)
    │   └── systemService.ts        # 系统状态 API
    │
    ├── stores/                     # 状态管理 (Zustand)
    │   ├── chatStore.ts            # 对话状态
    │   ├── appStore.ts             # 全局应用状态 (主题/侧边栏)
    │   └── settingsStore.ts        # 用户设置 (Phase 3)
    │
    ├── hooks/                      # 自定义 Hooks
    │   ├── useChat.ts              # 对话逻辑封装
    │   ├── useStreamResponse.ts    # 流式响应处理 (Phase 2)
    │   └── useTheme.ts             # 主题切换
    │
    ├── types/                      # TypeScript 类型定义
    │   ├── api.ts                  # API 响应类型
    │   ├── chat.ts                 # 对话相关类型
    │   └── agent.ts                # Agent 相关类型 (Phase 2)
    │
    └── styles/
        ├── theme.ts                # 主题 token 定义
        ├── global.css              # 全局样式
        └── variables.css           # CSS 变量
```

---

## 三、核心组件设计

### 3.1 ChatContainer（对话容器）

```
┌──────────────────────────────────────────┐
│  ┌────────────────────────────────────┐  │
│  │  会话列表 (可折叠)                  │  │
│  │  ┌────────────────────────────┐    │  │
│  │  │ 会话1: 中芯国际2024年营收   │    │  │
│  │  │ 会话2: 三大运营商对比      │    │  │
│  │  │ 会话3: ...                │    │  │
│  │  └────────────────────────────┘    │  │
│  │  [+ 新建会话]                      │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │          消息列表区域               │  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │ [用户] 中芯国际2024年营收？   │  │  │
│  │  └──────────────────────────────┘  │  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │ [AI] 根据财报数据...         │  │  │
│  │  │ 📎 来源: 中芯国际2024年报    │  │  │
│  │  │     P45, 相关度 89%          │  │  │
│  │  │              [展开思维链 >]   │  │  │
│  │  └──────────────────────────────┘  │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  输入区域                          │  │
│  │  [________________________] [发送] │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

**状态设计**:
```typescript
interface ChatState {
  sessions: Session[];           // 会话列表
  currentSessionId: string;      // 当前会话 ID
  messages: Message[];           // 当前会话消息
  isStreaming: boolean;          // 是否正在流式响应
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  sources?: Source[];            // 引用来源
  thoughtChain?: ThoughtStep[];  // Agent 思维链 (Phase 2)
}

interface Source {
  documentName: string;
  pageNumber?: number;
  relevanceScore: number;
  snippet: string;
}
```

### 3.2 Sidebar（侧边导航）

```
┌───────────────┐
│  📊 企业知识库  │  Logo + 标题
│───────────────│
│  💬 智能问答   │  ← 当前激活
│  🔀 DAG 看板   │
│  📈 数据图表   │
│  📁 知识库管理  │
│  ⚙  系统设置   │
│───────────────│
│  🌙 暗色模式   │  主题切换
└───────────────┘
```

### 3.3 主题设计

```typescript
// 企业财务专业色板
const financialTheme = {
  // 主色调: 深蓝 + 金融金
  colorPrimary: '#1a3a5c',        // 深蓝主色
  colorAccent: '#c9a96e',         // 金融金色
  colorSuccess: '#52c41a',        // 成功绿
  colorWarning: '#faad14',        // 警告橙
  colorError: '#ff4d4f',          // 错误红

  // 暗色主题
  dark: {
    colorBgBase: '#141414',
    colorBgContainer: '#1f1f1f',
    colorTextBase: '#e8e8e8',
  },

  // 亮色主题
  light: {
    colorBgBase: '#f5f5f5',
    colorBgContainer: '#ffffff',
    colorTextBase: '#262626',
  },

  // 字体
  fontFamily: `'Source Han Sans CN', -apple-system, sans-serif`,
  fontFamilyMono: `'JetBrains Mono', 'Fira Code', monospace`,  // 数字专用
};
```

---

## 四、API 对接设计

### 4.1 接口映射（Phase 1 不修改后端）

| 前端功能 | 后端接口 | 方法 | 说明 |
|----------|---------|------|------|
| 发送问题 | `/api/query` | POST | 核心问答 |
| 仅检索 | `/api/retrieve` | POST | 调试用 |
| 获取公司列表 | `/api/companies` | GET | 侧边栏选择 |
| 健康检查 | `/api/health` | GET | 系统状态 |

### 4.2 axios 实例配置

```typescript
// frontend/src/services/api.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 120000,  // Agent 推理可能耗时较长
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器: 附加 conversation_id
apiClient.interceptors.request.use((config) => {
  const sessionId = useChatStore.getState().currentSessionId;
  if (sessionId && config.data) {
    config.data.conversation_id = sessionId;
  }
  return config;
});

// 响应拦截器: 统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 统一错误提示
    return Promise.reject(error);
  }
);
```

### 4.3 API 代理配置 (Vite 开发模式)

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

---

## 五、Phase 1 最小化交付详细定义

### 5.1 安装的 npm 依赖

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.23.0",
    "antd": "^5.18.0",
    "@ant-design/icons": "^5.3.0",
    "axios": "^1.7.0",
    "zustand": "^4.5.0",
    "dayjs": "^1.11.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

### 5.2 Phase 1 交付文件清单（约 15 个文件）

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── .env.development
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── vite-env.d.ts
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.tsx
    │   │   ├── Sidebar.tsx
    │   │   └── HeaderBar.tsx
    │   ├── chat/
    │   │   ├── ChatContainer.tsx
    │   │   ├── MessageBubble.tsx
    │   │   ├── ChatInput.tsx
    │   │   └── SourceCard.tsx
    │   └── common/
    │       └── LoadingSpinner.tsx
    ├── services/
    │   ├── api.ts
    │   └── chatService.ts
    ├── stores/
    │   ├── appStore.ts
    │   └── chatStore.ts
    ├── hooks/
    │   └── useTheme.ts
    ├── types/
    │   └── chat.ts
    └── styles/
        ├── theme.ts
        └── global.css
```

### 5.3 Phase 1 用户交互流程

```
用户打开浏览器 → 看到对话首页
  ├── 左侧: 会话列表 + 新建会话按钮
  ├── 中间: 欢迎语 + 示例问题快捷入口
  ├── 底部: 输入框 + 发送按钮
  ├── 顶部: 标题 + 主题切换按钮
  └── 侧边栏(可折叠):
      ├── 公司选择下拉框
      ├── 检索返回条数滑块
      ├── 意图识别开关
      └── 系统状态指示器
```

---

## 六、Phase 2 / Phase 3 预留设计

### 6.1 DAG 看板（Phase 2）

使用 `@antv/g6` 或 `ReactFlow` 渲染 Agent 任务规划 DAG 图：

```
              ┌──────────────┐
              │  检索营收数据  │
              │  中芯国际     │
              └──────┬───────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ 提取2024  │ │ 提取2023  │ │ 提取2022  │
    │  营收     │ │  营收     │ │  营收     │
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         └──────┬─────┴──────┬─────┘
                ▼            ▼
          ┌──────────┐ ┌──────────┐
          │ 计算同比  │ │ 生成图表  │
          │  增长率   │ │  趋势图   │
          └────┬─────┘ └────┬─────┘
               └──────┬─────┘
                      ▼
               ┌──────────┐
               │ 生成最终  │
               │  分析报告  │
               └──────────┘
```

### 6.2 后端扩展接口（按需新增）

当 Phase 2 需要流式展示 Agent 推理过程时，新增后端端点：

```python
# 新增: 流式 Agent 查询
@router.post("/api/agent/stream")
async def agent_query_stream(request: AgentQueryRequest):
    """返回 SSE 流, 每个事件包含一步 Thought/Action/Observation"""
    async def event_generator():
        async for step in agent.run_stream(query):
            yield f"data: {json.dumps(step)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## 七、技术决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 前端框架 | React 而非 Vue | Ant Design 与 React 生态更紧密, 企业级项目更主流 |
| 组件库 | Ant Design 5 而非 Arco Design | 社区更大, 文档更完善 |
| 图表库 | ECharts 而非 D3.js | 配置式 API, 开发效率高, 国内支持好 |
| 状态管理 | Zustand 而非 Redux | 轻量, TypeScript 友好, 无过度抽象 |
| 构建工具 | Vite 而非 CRA | CRA 已停止维护, Vite 是社区标准 |
| 流式(Phase 2) | SSE 而非 WebSocket | 单向推送足够, 实现更简单 |
