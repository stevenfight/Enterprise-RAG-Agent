# 架构设计: 多 Agent 升级 - 阶段二 Orchestrator + 委托

> 编码: UTF-8
> 日期: 2026-08-06

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    api_service.py                       │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │    api_agent_query    │  │     api_agent_stream     │ │
│  │        (POST)         │  │         (SSE)            │ │
│  └──────────┬───────────┘  └──────────┬───────────────┘ │
│             │                          │                  │
│             ▼                          ▼                  │
│     QueryRouter.route()    QueryRouter.route()           │
│             │                          │                  │
│     ┌───────┼───────────┐     ┌───────┼───────────┐     │
│     │ rag   │ agent │multi_agent│ rag │ agent │multi_agent│
│     │       │       │     │       │       │            │     │
│     ▼       ▼       ▼     ▼       ▼       ▼            ▼     │
│   RAG   单Agent  ┌──────────┐  RAG   单Agent SSE  Orchestrator SSE│
│                 │Orchestrator│                         │
│                 └─────┬──────┘                         │
│                       │                                 │
│              ┌────────┼────────┐                       │
│              │  DelegateTool   │                       │
│              │  (AgentRegistry │                       │
│              │   SharedMemory) │                       │
│              └────────┬────────┘                       │
│                       │                                 │
│              ┌────────▼────────┐                       │
│              │  DataAgent(中芯)│  ...更多Worker        │
│              │   run() → result│                       │
│              └────────┬────────┘                       │
│                       │                                 │
│              ┌────────▼────────┐                       │
│              │  SharedMemory   │                       │
│              │ .add_agent_result│                      │
│              └─────────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

## 2. 模块设计

### 2.1 AgentRegistry — Agent 能力注册表

- **模式**：复用 `ToolRegistry` 的 register()/get() 接口风格
- **存储**：`Dict[str, AgentCapability]`，AgentCapability 是 dataclass
- **关键方法**：`get_agent_descriptions()` 生成 LLM 可用的描述文本，注入 Orchestrator System Prompt
- **Agent 实例化**：不在 Registry 中缓存，由 DelegateTool 按需创建（避免 ThreadPool 共享实例问题）

### 2.2 SharedMemory — 跨 Worker 共享记忆

- **写入隔离**：Worker 只写自己结果，`add_agent_result(agent_name, result)` 用 `threading.Lock` 保护（同步方法，因 DelegateTool.run() 在同步上下文中调用）
- **读取合并**：`get_context_for(agent_name, task)` 拼接所有上游结果
- **来源聚合**：`get_all_sources()` 遍历所有 `result.sources` 合并
- **Token 聚合**：`get_total_tokens()` 累加所有 `result.total_tokens`
- **生命周期**：每次新查询创建新实例，不跨请求复用

### 2.3 DelegateTool — 委托工具

- **继承**：`BaseTool`，`name="delegate"`
- **依赖注入**：`agent_registry`、`shared_memory`、`event_queue` 均通过构造函数传入
- **执行**：当前阶段串行执行任务列表，步骤 3.1 升级为 ThreadPoolExecutor 并行
- **Worker 创建**：根据 `AgentCapability.name` 按需创建 Worker 实例
- **StepCallback**：`_DelegateStepCallback` 通过 queue.Queue 推送到 SSE 流

### 2.4 OrchestratorAgent — 主控 Agent

- **继承**：`ReActAgent`，只持有 delegate 工具
- **配置**：`model="qwen-max"`、`temperature=0.3`、`max_steps=10`、`llm_timeout=120`
- **prompt_name**：`"orchestrator"`，需确保 `agent_prompts.yaml` 中有对应节
- **agent_descriptions 注入**：覆写 `_build_system_prompt()`，传入 `agent_descriptions` 参数

---

## 3. 数据流

```
用户查询 "三大运营商2024年营收对比"
  │
  ▼
QueryRouter.route()
  → category: multi_compare, companies: ["中国移动","中国联通","中国电信"]
  → mode: multi_agent
  │
  ▼
OrchestratorAgent.run(query)
  → System Prompt 含 agent_descriptions: "1. DataAgent: 从向量数据库精确检索财务数据 [工具: retrieve]"
  → LLM 分析：需要先检索三家公司的营收数据
  │
  ▼ (Step 1)
Action: delegate
Action Input: {"tasks": [
  {"agent": "DataAgent", "task": "中国移动2024年营收", "company_name": "中国移动"},
  {"agent": "DataAgent", "task": "中国联通2024年营收", "company_name": "中国联通"},
  {"agent": "DataAgent", "task": "中国电信2024年营收", "company_name": "中国电信"},
]}
  │
  ▼
DelegateTool.run(tasks)
  → 为每个 task 创建 DataAgent(retrieval_tool=RetrieveTool())
  → DataAgent.run(query=task["task"], company_name=company)
  → result → SharedMemory.add_agent_result("DataAgent(中国移动)", result)
  │
  ▼ (Step 2)
Observation: 委托执行完成: 3 个子任务...
  │
  ▼ (Step 3)
Action: Final Answer
Final Answer: 2024年三大运营商营收对比：
  - 中国移动: 1,250亿元
  - 中国联通: 993亿元
  - 中国电信: 897亿元
```

---

## 4. 接口设计

### 4.1 AgentRegistry 接口

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `register(cap)` | AgentCapability | None | 注册 Agent 能力 |
| `get(name)` | str | AgentCapability or None | 获取 Agent 能力 |
| `list_all()` | - | List[str] | 列出所有 Agent 名 |
| `get_agent_descriptions()` | - | str | LLM 可读描述 |

### 4.2 SharedMemory 接口

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `set_task_context(key, value)` | str, Any | None | 设置任务上下文 |
| `get_task_context(key)` | str | Any | 获取任务上下文 |
| `add_agent_result(name, result)` | str, AgentResult | None | 同步写入（threading.Lock 保护） |
| `get_agent_result(name)` | str | AgentResult or None | 获取结果 |
| `get_context_for(name, task)` | str, dict | str | 为下游构建上下文 |
| `get_all_sources()` | - | List[Dict] | 来源聚合 |
| `get_total_tokens()` | - | int | Token 聚合 |
| `clear()` | - | None | 清空 |

### 4.3 DelegateTool 接口

继承 `BaseTool`，`run(tasks, **kwargs) → ToolResult`。

tasks 格式：`[{"agent": "DataAgent", "task": "...", "company_name": "..."}]`

### 4.4 OrchestratorAgent 接口

继承 `ReActAgent`，无新增公开方法。构造函数参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `delegate_tool` | DelegateTool | 委托工具实例 |
| `agent_registry` | AgentRegistry | Agent 注册表 |
| `llm_provider` | BaseLLMProvider | LLM Provider |
| `shared_memory` | SharedMemory | 共享记忆 |

---

## 5. SSE 事件协议（阶段二）

| 事件类型 | 方向 | 阶段 | 说明 |
|------|------|:--:|------|
| `connected` | 后端→前端 | 0.3 | 连接确认 |
| `router_decision` | 后端→前端 | 0.3 | 路由决策 |
| `orchestrator_start` | 后端→前端 | **2.4 新增** | Orchestrator 启动，含已注册 Agent 列表 |
| `worker_step` | 后端→前端 | **2.3 新增** | Worker 执行步骤（步骤 3.1 并行升级后启用，当前阶段不推送） |
| `answer` | 后端→前端 | 0.1 | 最终答案 |
| `done` | 后端→前端 | 0.1 | 流结束 |

---

## 6. 技术决策

| 决策 | 理由 |
|------|------|
| Agent 不在 Registry 中实例化 | ThreadPool 并行时共享实例不安全，改为 DelegateTool 按需创建 |
| SharedMemory 用 threading.Lock | DelegateTool.run() 在同步上下文中调用（经由 ReActAgent → BaseTool 链），`asyncio.run()` 无法在已有事件循环中运行；用同步锁更简单可靠 |
| OrchestratorAgent 每个请求创建新实例 | 与现有 `_create_per_request_agent` 模式一致，避免并发问题 |
| api_service 中 multi_agent 代码直接内联 | 避免不必要抽象层，待步骤 3.1 并行升级后根据需要抽取辅助函数 |
| `agent_prompts.yaml` 已有 `orchestrator` 节（步骤 0.2 预留） | 无需新增 YAML 配置 |
