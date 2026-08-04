# 变更提案: 现代化前端展示界面 (Modern UI)

> 编码: UTF-8
> 状态: Phase 1 已完成 (2026-06-25), Phase 2 已完成 (2026-07-01)

---

## 1. 变更背景

当前系统前端为 **Streamlit** 单页面应用 ([app_streamlit.py](../../../app_streamlit.py))，后端为 **FastAPI** ([src/api_service.py](../../../src/api_service.py))，二者处于"前后端混合"状态——Streamlit 内既有界面渲染又有后端调用逻辑。

Streamlit 在企业级场景下存在明显短板：

| 问题 | 说明 |
|------|------|
| **视觉同质化** | Streamlit 默认组件风格无法体现"企业级财务分析"的专业质感 |
| **交互能力弱** | 无法实现 Agent 推理链的流式展示、DAG 任务图可视化、多面板自由布局等高级交互 |
| **缺乏图表交互** | chart_tool 生成的静态 PNG 图片，无法做悬停、缩放、联动等交互操作 |
| **无暗色模式** | Streamlit 原生不支持暗色主题切换 |
| **扩展天花板低** | 知识库管理、系统监控、Agent 配置等管理功能难以在 Streamlit 上优雅实现 |

本项目后端已有完善的 REST API 层，具备天然的"前后端分离"条件——保留现有 FastAPI 不变，新增独立前端项目即可。

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 新增现代化前端界面 | 基于 React + Ant Design 的专业交互界面，替换 Streamlit 作为主展示入口 |
| Agent 推理过程可视化 | 用户可见 Agent 的 Think → Act → Observe 循环及 DAG 任务规划图 |
| 交互式图表升级 | 替换静态 PNG 为 ECharts 交互式图表（悬停、缩放、联动） |
| 暗色/亮色双主题 | 支持一键切换，金融数据在暗色下更有专业质感 |
| 保留 Streamlit 不变 | Streamlit 界面继续可用，作为快速调试入口，不做任何修改 |
| 后端零改动（Phase 1） | 最小化交付阶段不修改任何 Python 代码，纯新增 frontend/ 目录 |

---

## 3. 变更范围

### 3.1 新增（全部在 `frontend/` 目录下）

| 模块 | 说明 |
|------|------|
| `frontend/` - React 项目 | Vite + React 18 + TypeScript + Ant Design 5 |
| `frontend/src/pages/` | 各页面组件（问答中心、DAG 看板、数据图表、知识库管理、系统监控） |
| `frontend/src/components/` | 通用组件（对话气泡、思维链卡片、图表容器、侧边栏等） |
| `frontend/src/services/` | API 对接层（封装 FastAPI 接口调用） |
| `frontend/src/stores/` | 状态管理（Zustand） |
| `frontend/src/hooks/` | 自定义 Hooks（流式响应、图表数据等） |
| `frontend/src/styles/` | 主题变量、全局样式 |

### 3.2 修改

| 模块 | 文件 | 修改内容 |
|------|------|---------|
| 后端 | `src/api_service.py` | Phase 2: 新增 `/api/agent/stream` (SSE)、`/api/charts/list`、`/api/agent/plan` |
| 后端 | `src/tools/chart_tool.py` | Phase 2: 生成 PNG 同步输出 JSON 结构化数据 |
| 后端 | `src/agent_core.py` | Phase 2: 新增 `run_stream()` 生成器方法 |

### 3.3 保留不变

- 所有 `src/` 下的 Python 代码
- 所有 `config/`、`data/`、`tests/`、`docs/` 文件
- `app_streamlit.py` 继续可用
- `requirements.txt` 不变

---

## 4. 前端技术选型

| 层级 | 技术 | 选型理由 |
|------|------|---------|
| 构建工具 | Vite 5 | 极速 HMR，TypeScript 原生支持 |
| UI 框架 | React 18 | 组件化能力最强，生态最丰富 |
| 语言 | TypeScript | 类型安全，降低大型前端项目的维护成本 |
| 组件库 | Ant Design 5 | 企业级 B 端设计语言，与"财务分析"定位天然匹配 |
| 图表 | ECharts 5 + echarts-for-react | 国内最成熟的交互式图表库，支持柱/折/饼/雷达/热力等 |
| 流程图 | @antv/g6 或 ReactFlow | Agent DAG 任务规划可视化 |
| 状态管理 | Zustand | 轻量、无 boilerplate、TypeScript 友好 |
| HTTP 请求 | axios | 成熟稳定，拦截器支持 |
| 路由 | React Router 6 | 页面级导航 |
| 主题 | Ant Design ConfigProvider | 内置暗色/亮色主题切换 |

---

## 5. 页面架构（5 大核心模块）

```
┌─────────────────────────────────────────────────────┐
│  ┌──────────┐                                       │
│  │  侧边导航  │         主内容区                      │
│  │  · 问答   │                                       │
│  │  · DAG   │   ┌──────────────────────────────┐   │
│  │  · 图表   │   │                              │   │
│  │  · 知识库 │   │      各页面内容渲染区           │   │
│  │  · 设置   │   │                              │   │
│  │          │   └──────────────────────────────┘   │
│  └──────────┘                                       │
└─────────────────────────────────────────────────────┘
```

### 模块一：智能问答中心（首页）
- 对话式交互界面（类似 ChatGPT 布局）
- Agent 思维链侧边抽屉：展示 Think → Act → Observe 流程
- 引用溯源卡片：来源报告名、页码、相关度分数
- 会话列表（左侧）：新建/切换/删除对话

### 模块二：DAG 任务规划看板（差异化亮点）
- 流程图可视化 Agent 拆解的子任务及依赖关系
- 任务状态实时反馈：等待中 / 执行中 / 已完成 / 失败
- 点击节点查看详情：输入/输出/耗时

### 模块三：数据图表中心
- ECharts 交互式图表（替代 chart_tool 静态 PNG）
- 多公司指标并排对比视图
- 时间轴趋势动画

### 模块四：知识库管理
- 已接入文档列表（财报、研报）
- 索引状态展示（向量化状态、分块数量）
- 公司目录

### 模块五：系统设置与监控
- Agent 参数调节（Temperature、Max Steps、Top-N）
- 工具开关（检索/计算/对比/图表/验证）
- 系统健康状态面板

---

## 6. 分阶段交付策略（核心）

### Phase 1: 最小化对话界面（本次交付）
**目标**：替换 Streamlit 的核心问答功能，验证前后端分离架构可行性

| 交付物 | 说明 |
|--------|------|
| React 项目脚手架 | Vite + TypeScript + Ant Design 搭建 |
| API 对接层 | 封装现有 `/api/query`, `/api/health` 接口 |
| 对话首页 | 对话式交互界面 + 会话管理 |
| 基础侧边栏 | 公司选择、检索配置、模式切换 |
| 亮色/暗色主题 | Ant Design ConfigProvider 主题切换 |

**不做**：DAG 看板、交互图表、知识库管理、Agent 配置面板（留待 Phase 2/3）

### Phase 2: Agent 可视化 + 交互图表
- Agent 思维链流式展示
- DAG 任务规划可视化
- ECharts 交互式图表升级

### Phase 3: 管理后台 + 完善
- 知识库管理页面
- 系统监控面板
- 响应式适配、性能优化

---

## 7. 风险与应对

| 风险 | 应对策略 |
|------|---------|
| 前端开发周期长 | 采用 Phase 1 最小化交付，先跑通架构，再迭代功能 |
| 后端接口不足（无流式、无 Agent 详情） | Phase 1 不依赖流式，直接调用现有 REST 接口；后续按需扩展后端 |
| 与 Streamlit 并存维护成本 | Streamlit 不做任何改动，仅作为备用入口 |

---

## 8. 版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v3.0-dev | 2026-06-25 | 初始化提案 |
