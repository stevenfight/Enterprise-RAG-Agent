# 变更日志

> 格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
> 版本号按迭代轮次递增

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
