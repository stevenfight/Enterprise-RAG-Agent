# 变更日志

> 格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
> 版本号按迭代轮次递增

---
## [第二十七轮] — v5.18.1 — 2026-08-27 研究工作台高级视觉统一修正

### 变更

- 统一页面背景、卡片、抬升表面和输入表面的主题 token，暗色模式改为中性石墨层级。
- 收紧页面标题、摘要卡、空状态和辅助页工作区的间距与信息密度。
- 修正聊天输入框在深浅模式下的表面表现，保留现有发送、流式回答和证据交互。

### 验证

- 前端 Vitest：43 个文件、232 项通过。
- oxlint 通过；`tsc -b && vite build` 通过。
- 本地前端入口与后端健康检查均返回 200，图表、知识库、DAG、设置页逐页核查通过。
- 复核发现并修正暗色导航侧栏仍沿用旧紫色表面的遗漏，侧栏与主画布现统一使用中性页面层级。

---
## [第二十六轮] — v5.17 — 2026-08-27 财务研究工作台 D6 收口

### 变更

- 完成 DS-R01～R03、DS-R08～R09、RW-R04、RW-R06 遗留 TDD 补验并全部转为 GREEN。
- 补充深蓝主体色对比度实测、真实 Agent 流式期间外观切换验收及 OpenSpec/TDD/交接文档状态。
- 完成财务研究工作台 OpenSpec D6 文档收口，保留既有非阻断观察项。

### 验证

- 后端 `python -m pytest -q`：186 passed，1 skipped。
- 前端 Vitest：42 个文件、228 项通过；oxlint 通过；生产构建通过。
- 深蓝暗色 `#60A5FA` 对 `#17142A` 为 7.06:1，亮色 `#1D4ED8` 对白底为 6.70:1，均满足 WCAG AA 正文对比度。
- 真实 Agent 流式回答期间切换外观后，分析步骤由 2 步继续至 36 步，最终回答含 12 条证据及三家公司营业收入数据。

---
## [第二十五轮] — v5.16 OpenSpec 收口与质量发布门禁

### 变更

- 归档 `model-upgrade`、`quality-robustness-enhancement`、`prompt-injection-guard`、`sync-roadmap-status` 和 `workspace-hygiene-cleanup` 五个已完成 OpenSpec 变更。
- 新增可复用 Quality Gate：工作流静态检查、Python 3.11 后端编译与无密钥测试白名单、Node 20 前端测试与生产构建；Docker Build & Push 在构建和推送镜像前调用该门禁。
- Docker 构建路径过滤纳入 `requirements.lock` 与 `quality-gate.yml`，避免锁文件或门禁规则变更绕过构建。
- 当前 Deploy to Server 暂时仅允许手动触发，等待 SSH 失败原因、GHCR 凭据和 SHA 镜像受控部署验证完成后再恢复自动触发。
- 根目录 README 同步当前前端依赖、OpenSpec 归档结构与本地/远端验证边界。

### 验证

- 后端 `compileall` 和 pytest 白名单 32 项通过。
- 前端 Vitest 150 项通过，生产构建通过。
- GitHub Actions 运行 `32759245372` 的 Quality Gate 与前后端镜像构建/推送均成功；main 分支保护和服务器受控部署仍待完成。

---
## [第二十四轮] — v5.15 OpenSpec 变更归档与交接文档精简

### 变更

- 归档 `openspec/changes/` 下已完成变更目录至 `openspec/changes/archive/`（v5.0~v5.13 共 30 个目录：frontend 视觉优化类、multi-agent-step01~15、p0-critical-fixes、modern-ui、backend-memory-config-dedup 等），根目录仅保留仍处规划中的 `model-upgrade`、`prompt-injection-guard`、`quality-robustness-enhancement`
- 精简交接文档「三、已完成的任务」历史会话记录为压缩摘要（169KB/1580 行 → 111KB/954 行，约 -34% 体积），保留各轮核心成果、验证数据、TDD 数量与 OpenSpec 归档路径，关键信息无丢失

### 验证

- 归档目录移动全部成功（30 个目录，无缺失）
- 交接文档章节结构完整（一~十二）、32 条踩坑记录保留、无中文乱码
- v5.10~v5.14 详细小节与「四、当前卡在哪里」「五、下一步计划」保持不变

---
## [第二十三轮] — v5.14 运行环境修复与后端回归

### 修复

- 健康检查 `agent_loaded` 改为读取 Agent 共享组件初始化状态，修复 per-request 模式下误报 `agent_loaded=false`
- 冒烟测试从 `config/agent_config.json` 读取 API Key 并携带 Bearer 鉴权头，请求字段对齐 `conversation_id`
- 图表列表与 Agent 规划冒烟断言对齐当前响应契约（`{charts, total}` 与 `{nodes, edges, execution_order}`）

### 验证

- `/api/health`：`agent_loaded=true`，`rag_generator_loaded=true`
- API 冒烟测试：4 PASS / 0 FAIL
- 后端相关测试：13 passed（统一入口 3 项 + AgentMemory 相关 10 项）
- Python 语法编译通过

---
## [第二十二轮] — v5.13 API 会话记忆配置一致性

### 修复

- 新增统一 API 会话记忆创建入口，集中传递工作记忆、情景记忆、长期记忆和 `session_id` 配置
- 普通 Agent 查询、SSE、LangBot 兼容接口和 OpenAI 兼容接口统一复用会话记忆入口
- 同一 `conversation_id` 复用记忆实例，不同会话使用独立的持久化会话标识

### 验证

- 会话记忆专项测试：3 项通过
- `api_service.py` 与测试文件 Python 语法编译通过
- 相关 API 冒烟测试受当前运行服务未初始化和鉴权状态影响，未将环境失败归因于本次改动

---
## [第二十一轮] — v5.12 前端审查问题收敛

### 修复

- 新增共享 `ChartData` 类型模块，解除图表服务层对组件层类型的反向依赖
- 从 DAG 任务类型常量导出 `DagNodeType`，由服务层、页面、组件与测试夹具统一复用
- 将 `ChartTable` 分页测试从 Ant Design 内部 `list` role 断言改为第二页可见页码断言

### 验证

- 专项 Vitest：4 个测试文件、41 项通过
- 全量 Vitest：22 个测试文件、150 项通过
- TypeScript 检查与 Vite 生产构建产物生成通过（保留既有 chunk 体积警告）

---

## [第二十轮] — v5.11 图表与 DAG 接口鉴权收紧

### 修复

- 从 `APIAuthMiddleware.SKIP_PATHS` 移除 `/api/charts/list` 与 `/api/agent/plan`，恢复这两个接口的 API Key 鉴权
- 保留 `/api/agent/stream` 豁免（EventSource 无法携带自定义请求头）
- 保留 `/api/charts/images/` 前缀豁免（静态图片标签无法携带鉴权头）

### 变更背景

第一阶段已将前端图表与 DAG 请求统一到 `apiClient`，请求拦截器自动附加 `Authorization` 头，因此这两个接口已具备恢复正常鉴权的前提。

### 验证

- 后端语法编译通过
- 前端 Vitest：22 个测试文件、150 项通过（无回归）
- 鉴权测试用例新增至 `tests/test_p0_fixes.py`（无 Key / 错误 Key / 正确 Key）

---

## [第十九轮] — v5.10 第一阶段重复逻辑收敛

### 新增

- 新增图表服务 `chartService.ts`，`ChartsPage` 图表列表请求迁移到统一 `apiClient`
- 新增 DAG 服务 `dagService.ts`，`DagBoardPage` 任务规划请求迁移到统一 `apiClient`
- 新增通用状态概览组件 `StatusOverview`，知识库概览与设置页系统状态概览统一复用
- 新增通用图表表格组件 `ChartTable`，`ChartsPage` 表格视图与 `ChartContainer` 表格类型统一复用
- `AppLayout` 健康检查复用 `chatService.checkHealth`，删除页面层原生 fetch
- 概览网格、卡片、状态样式统一为 `status-overview-*`，保留四列/五列与紧凑两种视觉形态

### 验证

- 第一阶段专项测试 7 项通过（服务层、StatusOverview、ChartTable）
- 前端 Vitest：22 个测试文件、150 项通过
- TypeScript 检查通过
- 生产构建通过

---

## [第十八轮] — v5.9 图表中心视觉增强

### 新增

- 图表模式改为桌面端两列、移动端单列的响应式网格
- 图表和表格卡片增加横轴、纵轴、来源文件和生成时间元信息
- 图表模式与表格模式分别使用网格和全宽列表，提升数据阅读空间
- 优化无图表和筛选无结果时的空状态提示

### 验证

- ChartMeta 专项测试 2 项通过
- 前端 Vitest：19 个测试文件、139 项通过
- TypeScript 检查通过
- 生产构建通过

---

## [第十七轮] — v5.8 DAG 看板视觉增强

### 新增

- DAG 页面新增任务摘要：任务类型、节点数、依赖连线数和执行批次数
- 新增执行批次时间线，直观展示每批节点及执行阶段
- DAG 节点边框根据等待、执行中、成功、失败和跳过状态显示不同颜色
- 增加摘要和时间线的桌面端、中等屏幕和移动端响应式布局

### 验证

- DAG 视觉组件测试 3 项通过
- 前端 Vitest：18 个测试文件、137 项通过
- TypeScript 检查通过
- 生产构建通过

---

## [第十六轮] — v5.7 知识库页面 KPI 概览

### 新增

- 知识库页面新增文档总数、已索引、待索引和索引完成率四项概览卡片
- 统计数据直接基于现有文档列表计算，不新增接口和数据字段
- 增加桌面端四列、中等屏幕两列、移动端单列的响应式布局
- 保留上传、删除、刷新、表格筛选和索引状态展示

### 验证

- KnowledgeOverview 专项测试 2 项通过
- 前端 Vitest：17 个测试文件、134 项通过
- TypeScript 检查通过
- 生产构建通过

---

## [第十五轮] — v5.6 修复前端生产构建

### 修复

- 修复 ThoughtChainDrawer 测试数据与 `ReasoningStep` 类型不一致问题
- 修复 G6 DAG 节点点击事件类型和未使用 React 导入
- 修复图表表格数据和 Ant Design Table 列类型问题
- 修复知识库表格过滤器类型问题
- 移除未使用的 HeaderBar 导入和 EventSource 辅助函数
- 使用 `vitest/config` 提供 Vite 测试配置类型支持

### 验证

- TypeScript 检查通过
- 前端 Vitest：16 个测试文件、132 项通过
- `npm run build` 成功，产物生成于 `frontend/dist`
- 构建仍提示大 chunk 警告，但不影响构建成功

---

## [第十四轮] — v5.5 设置页仪表盘改造

### 新增

- 设置页新增系统状态概览 KPI 卡片：Agent、向量数据库、长期记忆、LangSmith 追踪和工具注册
- 根据现有系统状态自动显示成功、告警和异常状态，不新增接口
- 增加桌面端 5 列、中等屏幕 3 列、移动端单列的响应式布局
- 保留原有 Agent 配置、系统健康和已注册工具详情卡片

### 测试

- SettingsOverview 组件测试 2 项通过
- TypeScript 检查命令受环境 npm 日志沙箱限制，需在允许 npm cache 日志目录后复核

---
## [第十三轮] — v5.4 页面容器与卡片规范统一

### 新增

- 新增 `PageShell` / `PageHeader` 公共组件，统一 DAG、图表、知识库和系统设置页面的内容宽度、标题结构和页面间距
- 新增页面级卡片规范，统一圆角、边框、背景和阴影，并通过主题变量支持亮色/暗色模式
- 新增移动端页面容器适配：页面水平内边距收敛为 16px

### 测试

- PageShell 组件测试 2 项通过
- 前端 Vitest 130 项通过
- TypeScript 检查通过
- 生产构建仍存在项目既有类型错误，未在本轮扩大修复范围

---

## [第十二轮] — v5.3 前端观感优化（A/B/C/D）+ DAG 看板修复

### 新增

- **聊天 UI 全面升级 @ant-design/x**：手写聊天组件替换为 Sender / Bubble / Conversations / Welcome（后端 SSE 流式、多Agent状态、思维链逻辑不变）
- **财务指标卡片化**（方向 A）：`frontend/src/utils/financialFormat.ts` 自动提取 KPI + `FinancialKPICards.tsx` AI 消息顶部渲染指标卡片；Markdown 表格美化（表头渐变、斑马纹、数字等宽右对齐、圆角阴影、行 hover）
- **主题切换 + 消息微交互**（方向 B+C）：HeaderBar 太阳/月亮按钮（localStorage 持久化）；MessageBubble hover 显示复制/重新生成；气泡入场动画 `fade-in-up-smooth`
- **欢迎页快捷指令 + 图表暗色适配**（方向 D）：ChatContainer `quickCommands` 胶囊；ChartContainer `dark` prop 亮/暗双配色；ChartsPage 跟随全局主题
- **planner DAG 分解增强**：`CHART_KEYWORDS`、`CALC_KEYWORDS` 增加"涨幅/增长/同比"；`_build_multi_compare` 补齐 retrieve→compare→(calc)→(chart)→verify 子任务链；`COMPARE_KEYWORDS` 移除连接词防单公司误判，trend 分类放宽
- **planner 三大运营商别名识别**：`COMPANY_ALIASES` + `_extract_companies`；`COMPANY_NAMES` set→list 修复顺序不稳定

### 修复

- **DAG 节点无文字**：G6 v5 `labelText` 空字符串/模板 `${data.label}` 不解析，改用函数形式 `(datum) => datum.data?.label ?? ''`
- **DAG 节点详情**：点击节点弹出详情 Modal（任务 ID / 类型 / 描述 / 工具 / 状态 / 工具参数 JSON）
- **后端检索缺失中国移动**：`_adjust_top_n_for_companies` 按公司数自动扩容 top_n
- **单公司趋势误判对比**：连接词"及"不再触发 multi_compare，"中芯国际近几年主营业务及营收变化，图表展示"正确走 trend

### 测试

- 前端 Vitest 126 用例全绿（14 个测试文件）
- planner TDD 11 用例全绿（AL-01~AL-11）
- 后端既有测试无回归（18 passed + 342 passed）

---

## [第十一轮] — v5.2 Phase 3 前端现代化 UI（管理后台）

### 新增

- **知识库管理页面（KnowledgePage）**：文档列表 + 索引状态展示 + PDF 拖拽上传（50MB 限制）
- **后端知识库服务 `knowledge_service.py`**：文档 CRUD + 路径遍历防护 + 索引状态查询
- **系统设置监控页面（SettingsPage）**：只读监控面板（Agent / 向量数据库 / 长期记忆 / LangSmith 追踪 / 工具注册 五项 KPI），后端新增系统状态接口
- **响应式适配**：`responsive.css` 移动端适配（侧边栏 fixed 布局）
- **生产构建优化**：`App.tsx` 改用 `React.lazy` 四路由代码分割（分包构建），优化首屏加载
- **前端服务层**：`knowledgeService.ts`、`systemService.ts` 封装知识库与系统状态 API；`types/chat.ts` 扩展知识库/系统状态类型
- **OpenSpec 规范文档**：proposal.md、design.md、tasks.md、spec-frontend-ui.md、tdd-frontend-ui.md（`openspec/changes/archive/modern-ui/`）

### 变更

- 后端 `api_service.py`：新增 5 个模型 + 5 条路由（知识库文档列表/上传/删除、索引状态、系统状态）
- 知识库关键路径日志补全（knowledge_service.py / api_service.py / KnowledgePage.tsx）

### 验证

- `python -m py_compile` / `npx tsc --noEmit` / `npx vite build` 全部通过（分包构建成功）
- TC-FE-011 知识库管理 7/7 绿，TC-FE-012 系统设置 6/6 绿，TC-FE-013 生产就绪 5/7 绿
- 2 项留待后续：移动端汉堡菜单 + Nginx 部署配置（对应 TC-FE-013 2 项红）

---

## [第十轮] — v5.1 P0 关键缺陷修复

### 修复

- **#1 empty_result_count 重置逻辑修复**（`agent_core.py:262`）：`max(0, n-1)` 阶梯递减改为直接 `= 0`，符合"连续空结果次数"语义
- **#2 run_stream 强制答案传入正确推理链**（`agent_core.py:456-467, 470`）：流式模式中累积 `reasoning_chain`，强制答案时传入而非空列表
- **#3 memory 配置生效**（`api_service.py:385-407` + `_load_agent_config()`）：`AgentMemory()` 从 `config/agent_config.json` 的 `memory` 段读取 `working_memory_limit`、`episodic_memory_turns`、`enable_long_term`
- **#4 Agent 并发安全重构**（`api_service.py:589-595` + 全局变量重构）：全局 `agent` 单例改为 per-request 创建 `ReActAgent` 实例，消除并发请求互相覆盖 memory 和参数的问题
- **#5 API Key 鉴权**（`api_service.py` + `config/agent_config.json`）：
  - 新增 `APIAuthMiddleware`（`BaseHTTPMiddleware`），校验 `Authorization: Bearer <key>` 请求头
  - `/api/health`, `/docs`, `/openapi.json`, `/redoc` 白名单豁免鉴权
  - `max_steps` 硬上限 15，防止客户端拉高 token 消耗
  - 鉴权失败返回 401，错误信息脱敏
  - TDD 测试: 20/20 全部通过（SP0-01~05）

### 新增

- `config/agent_config.json` 新增 `api` 配置节（`key`、`max_steps_hard_limit`）
- `_create_per_request_agent()` 工厂函数（`api_service.py`），统一 per-request Agent 实例创建

### 变更

- `_load_agent_config()` 新增 `memory` 和 `api` 配置段读取
- `api_agent_query()` 和 `api_agent_stream()` 改为 per-request 创建 Agent，不再修改全局单例
- `agent_planner` / `agent_reflector` 全局变量引用改为 `_shared_state["planner"]` / `_shared_state["reflector"]`
- 异常信息泄漏修复：HTTPException detail 从 `str(e)` 改为通用错误信息
- 专栏文章 19 同步更新：SQL `api_keys` 和 curl 命令新增 API Key

---

## [第九轮] — v5.0 LangSmith + OpenEvals 能力评测监控

### 新增

- **LangSmith 在线追踪**：自研 ReAct Agent 全链路追踪（plan → retrieve → rerank → generate → reflect）
  - `src/monitoring.py`：LangSmith Client 初始化 + traceable 装饰器工厂 + Windows 注册表回退 + 优雅降级
  - 11 个追踪节点覆盖 Agent 核心（react-loop / llm-call / tool-execute）+ 检索模块（vector-search / bm25-search / hybrid-search / rag-query / llm-generate）+ API 服务
  - 未配置 API Key 时不影响现有功能，所有 @traceable 装饰器自动降级为透传
- **OpenEvals 离线评测**：
  - `tests/eval_openevals.py`：基于 OpenEvals 的 LLM-as-Judge 生成质量评测（Correctness / Groundedness / Relevance 三维度评分）
  - `tests/eval_langsmith.py`：LangSmith 在线评测脚本，连接评测数据集到 LangSmith 平台
  - `tests/eval_datasets/generation_queries.json`：生成评测数据集（10 条用例 gen-001 ~ gen-010）
  - `tests/eval_datasets/retrieval_queries.json`：检索评测数据集
- **配置扩展**：`config/agent_config.json` 新增 `monitoring` 配置节，`env` 新增 LangSmith 环境变量
- **OpenSpec 规范文档**：proposal.md、design.md、tasks.md、spec-monitoring.md（含 7 个规范）、tdd-monitoring.md（TC-MON-01~08 + TC-EVAL-01~10）

### 优化

- **Prompt 规则迭代优化**（基于 OpenEvals 评测结果闭环优化）：
  - 规则5：单位换算（千元 ÷ 100,000 = 亿元），修复 gen-010 单位错误
  - 规则6：禁止汇率换算，避免 Agent 自行折算
  - 规则7：优先人民币数据
  - 规则9：优先年报来源，年报数据优先于研报
  - 规则10：年报检索强化，首次检索仅含研报时追加检索"年度报告"关键词
  - 规则11：同源对比原则，计算增长率时必须同源同币种

### 评测结果 (2026-07-24)

| 指标 | 值 |
|------|-----|
| 总用例数 | 10 |
| 通过数 | 8 (通过率 80%) |
| 平均正确性 | 0.77 |
| 平均忠实度 | 0.90 |
| 平均相关性 | 0.95 |
| 未通过用例 | gen-007 (数据来源混用), gen-008 (多步检索步数限制) |

### 待优化

- **tags 打标传参方案**：在 text_splitter.py 阶段打文档类型标签，检索时按标签加权，彻底解决 gen-007 年报数据被研报淹没问题（方案详见 _local/blog/Agent项目/后续优化想法/Tags打标传参方案.md）
- **test_monitoring.py 独立单元测试**：当前 TC-MON-01~08 通过集成验证，待补充独立单元测试文件

---

## [第八轮] — v4.0 Docker 容器化部署

### 新增

- **Docker 容器化部署方案**：前后端分离容器，一条命令完成系统启动
  - `Dockerfile.backend`：Python 3.11-slim 镜像，FastAPI 服务（端口 8000）
  - `Dockerfile.frontend`：多阶段构建（Node.js 编译 + Nginx 托管），前端静态服务（端口 80）
  - `docker-compose.yml`：编排文件，自动构建 + 启动前后端容器
  - `nginx.conf`：API 反向代理（/api/* → backend:8000）+ SPA 路由回退 + SSE 流式支持
  - `.env.docker`：Docker 环境变量模板（API Key 通过 env_file 注入）
  - `.dockerignore`：构建忽略规则，排除 node_modules、__pycache__、_local 等
- **OpenSpec 规范文档**：proposal.md、design.md、tasks.md

---

## [第七轮] — Phase 2: Agent 可视化 + 交互图表

### 新增

- **Agent 推理流式传输**：后端新增 `/api/agent/stream` SSE 端点，前端 EventSource 实时接收推理步骤
- **思维链侧边抽屉** (`ThoughtChainDrawer`)：时间线样式完整展示 Agent Think → Act → Observe 循环
- **DAG 任务规划看板** (`DagBoardPage` + `DagFlow`)：使用 @antv/g6 v5 渲染 Planner 子任务依赖关系图
- **交互式 ECharts 图表** (`ChartContainer`)：替换静态 PNG，支持柱状图/折线图/饼图、Tooltip、图例交互
- **图表中心页面** (`ChartsPage`)：从 `/api/charts/list` 加载历史图表，支持类型筛选
- **后端新接口**：`/api/charts/list`、`/api/agent/plan`
- **chart_tool 同步输出 JSON**：生成 PNG 同时产出结构化数据文件
- **前端单元测试**：47 条测试（ChartContainer 22 + ThoughtChainDrawer 17 + DagFlow 8）

### 优化

- **边缘情况修复**：tooltip formatter axis trigger 数组处理、labels/values 长度不一致截断、空数据占位
- **DagFlow 稳定性**：ResizeObserver 监听容器宽度、offsetWidth 兜底 200px、useMemo 稳定比较避免 G6 频繁重建
- **组件日志增强**：ChartContainer 和 DagFlow 关键渲染节点添加 console.debug 日志
- **侧边栏重构**：移除意图识别开关、新增 Agent 深度推理、高级选项折叠面板

---

## [第六轮] — Phase 1: 现代化前端基础界面

### 新增

- 独立 React 前端：Vite + React 18 + TypeScript + Ant Design 5
- 对话首页 (ChatPage)：聊天式界面、示例问题、Markdown 渲染、引用来源卡片
- 会话管理：多会话创建/切换、localStorage 持久化
- 亮色/暗色主题切换
- API 对接层：axios + Vite 代理到 FastAPI:8000
- 48 条 Phase 1 TDD 测试用例

---

## [第五轮] — 长期记忆 JSON 持久化

### 新增

- **长期记忆 JSON 持久化**：AgentMemory 情景记忆从纯内存扩展到 JSON 文件持久化
  - 每 session 独立 JSON 文件，进程重启后可恢复
  - 初始化时加载最近 N 轮历史
  - 27 项测试全量通过

---

## [第四轮] — ReAct 空结果安全阀

### 新增

- **ReAct 空结果安全阀**：三层防护机制防止 LLM 在无效检索上陷入死循环
  - `_is_empty_result()` 空结果检测：8 个关键词标记 + 2 个失败前缀，O(n) 字符串匹配
  - `empty_result_count` 计数器：连续空结果累加，有有效结果则退回，>=2 次输出 WARNING
  - `forced_stop` + `_generate_forced_answer()`：max_steps 耗尽时给出非空降级答案
- **日志埋点**：空结果判定 INFO 日志、计数器重置 INFO 日志，全链路可观测
- **纯 Mock 单元测试**：`tests/test_agent_mock_boundary.py`，覆盖 13 个标记判定、计数器全状态、NameError 修复验证、日志输出验证

### 修复

- **隐藏 bug**: `_generate_forced_answer()` 原代码引用 `run()` 局部变量 `reasoning_chain` 导致 `NameError`，改为显式传参
- **文档事实错误**: 引流汇总中 `max_steps=10` 修正为 `5`，`agent_core.py 200 多行` 修正为 `约 500 行`

### 文档

- 博客文章"坑 3"精简为与坑 1/坑 2 对齐的 8 行列表格式
- 效果验证表新增"空结果强制终止"行
- 经验总结新增第 6 条"罕见路径必须测试"

---

## [第三轮] — RAG 管道 → RAG-Agent 智能体

### 新增

- Agent 模式：ReAct 循环、工具调用、自我反思、任务规划
- 五个工具：retrieve、calculator、compare、chart、verify
- 三层记忆系统：工作记忆、情景记忆、长期记忆
- API 服务：`/api/agent/query` 端点

### 保留

- 管道模式（RAG Pipeline）向后兼容

---

## [第二轮] — 健壮性 + 功能完整性增强

### 新增

- 代码去重、API 超时控制、对话记忆、BM25 财经词典、表格文本预处理
- 对比查询优化（候选截断保护、营收数据保底）、查询改写上下文注入、检索日志增强

---

## [第一轮] — 模型升级 + 检索精准度

### 新增

- Embedding v3 (1024 维)、gte-rerank-v2 批量重排、qwen-max 生成
- 检索权重自适应、指令细分化 Prompt (4 种类型)
