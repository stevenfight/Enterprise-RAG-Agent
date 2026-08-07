# 架构设计: 多 Agent 升级 - 阶段四 API 端点统一

> 编码: UTF-8
> 日期: 2026-08-07

---

## 1. 整体架构

api_service.py 的 POST/GET 端点在处理多 Agent 请求时的分层关系：

```
FastAPI 端点层 (api_service.py)
├── POST /api/agent/query  ─── 新增 mode + company_name 参数
│   ├── mode="auto"  → router.route() → 自动判断
│   ├── mode="multi" → 直接走多 Agent 链路
│   └── mode="single" → 直接走单 Agent 链路
│
└── GET /api/agent/stream  ─── 新增 mode 参数
    ├── _stream_multi_agent()  ← 从闭包提取为独立 async generator
    │   事件流: connected → orchestrator_start → delegating
    │           → worker_step (N次) → workers_done
    │           → answer_chunk (N次) → answer → reflection → done
    │
    └── _stream_single_agent()  ← 现有 agent.run_stream() 封装
        事件流: connected → thought → action → observation → answer → done
```

## 2. 详细设计

### 2.1 POST AgentQueryRequest 参数扩展

```python
class AgentQueryRequest(BaseModel):
    """Agent 查询请求"""
    query: str = Field(..., description="查询文本")
    company_name: Optional[str] = Field(None, description="限定公司名（可选）")
    max_steps: int = Field(5, description="Agent 最大推理步数", ge=1, le=100)
    temperature: float = Field(0.3, description="LLM 温度", ge=0.0, le=2.0)
    conversation_id: Optional[str] = Field(None, description="对话ID")
    mode: str = Field("auto", description="模式: auto / single / multi")
```

### 2.2 GET /api/agent/stream 参数扩展

```python
@app.get("/api/agent/stream")
async def api_agent_stream(
    query: str,
    mode: str = "auto",           # auto / single / multi
    company_name: Optional[str] = None,
    max_steps: int = 5,
    temperature: float = 0.3,
    conversation_id: Optional[str] = None,
):
```

### 2.3 mode 参数语义

| mode 值 | 行为 |
|--------|------|
| `auto` (默认) | router.route() 自动判断 → multi_agent 或 single |
| `single` | 跳过 router，直接执行单 Agent ReAct 循环 |
| `multi` | 跳过 router，直接执行多 Agent Orchestrator 链路 |

`auto` 模式下 router 不可用时，fallback 到 single。

### 2.4 _stream_multi_agent 独立函数

从当前 `event_generator()` 闭包中提取 ~100 行 multi_agent 逻辑为独立函数：

```python
async def _stream_multi_agent(
    query: str,
    company_name: Optional[str],
    cm: ConversationManager,
) -> AsyncGenerator[str, None]:
    """多 Agent 流式 SSE 事件生成器

    事件序列:
        connected → orchestrator_start → delegating → worker_step(N) →
        workers_done → answer_chunk(N) → answer → reflection → done
    """
    import asyncio
    import queue
    import threading
    from src.shared_memory import SharedMemory
    from src.tools.delegate_tool import DelegateTool

    # ... 从 event_generator 闭包中提取逻辑 ...
    # 关键增强点:
    # 1. delegating 事件: 在 orchestrator_thread 启动前，推送含 Agent 列表的占位事件
    # 2. workers_done 事件: 在 orchestrator_thread 完成后，从 shared_memory 读取 worker_count 推送
    # 3. answer_chunk 事件: 拆分 answer 按句子推送
    # 4. reflection 独立事件: 不再嵌套在 answer payload 中
```

### 2.5 _stream_single_agent 独立函数

```python
async def _stream_single_agent(
    agent: ReActAgent,
    query: str,
    company_name: Optional[str],
    cm: ConversationManager,
):
    """单 Agent 流式 SSE 事件生成器"""
    yield f"data: {json.dumps({'type': 'connected', ...})}\n\n"

    for event in agent.run_stream(query, company_name=company_name):
        yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        await asyncio.sleep(0)
```

### 2.6 多 Agent SSE 事件协议（最终版）

| 事件类型 | 触发时机 | payload 关键字段 |
|---------|---------|-----------------|
| `connected` | SSE 连接建立 | timestamp |
| `orchestrator_start` | Orchestrator 开始推理 | registered_agents, timestamp |
| `delegating` | 开始委托 Worker 批次 | batch, task_count, agent_types |
| `worker_step` | Worker 每步进度 | agent, step, action, timestamp |
| `workers_done` | 批次全部完成 | batch, result_count, failed_count |
| `answer_chunk` | 答案流式增量 | content (单句) |
| `answer` | 最终完整答案 | content, workers, total_tokens |
| `reflection` | Reflector 检查结果 | score, issues, corrected_answer |
| `done` | 推理完全结束 | timestamp |

### 2.7 answer_chunk 拆分逻辑

OrchestratorAgent.run() 返回完整 answer 字符串后，api_service 按中文句号/换行符拆分句子，逐句推送：

```python
# 拆分 answer 为句子，流式推送
sentences = re.split(r'([。\n])', final_answer)
for i in range(0, len(sentences), 2):
    chunk = sentences[i]
    if i + 1 < len(sentences):
        chunk += sentences[i + 1]
    if chunk.strip():
        yield f"data: {json.dumps({'type': 'answer_chunk', 'content': chunk.strip()}, ensure_ascii=False)}\n\n"
```

### 2.8 delegating / workers_done 事件生成

`delegating` 事件在 `orchestrator_thread` **启动前**发送（含 agent_registry 中的 Agent 列表作为占位信息），`workers_done` 事件在 orchestrator_thread **完成后**从 `shared_memory.agent_outputs` 读取 worker_count 推送。

不改动 delegate_tool.py（遵循最小变更原则），所有 SSE 事件包装由 api_service 层完成。

### 2.9 company_name 传递链

```
api_service (POST/GET)
  └─ mode="multi" 时:
       orchestrator = OrchestratorAgent(...)
       result = orchestrator.run(query=query, company_name=company_name, ...)
                                     ↑ ReActAgent.run() 早已支持此参数
```

`ReActAgent.run()` 签名中已有 `company_name: Optional[str] = None`（[agent_core.py#L178](file:///d:/文件信息/AI应用开发/AI实战练习/github-project/企业级财务年报分析智能RAG—AGENT/src/agent_core.py#L178)），OrchestratorAgent 继承即可用。api_service 在调用时传入即可，**无需修改 orchestrator_agent.py**。

### 2.10 POST /api/agent/query mode 路由逻辑

```python
async def api_agent_query(request: AgentQueryRequest):
    # ...
    mode = request.mode  # auto / single / multi

    if mode == "multi":
        # 直接走多 Agent 链路，跳过 router
        return await _handle_multi_agent_query(request, cm, conversation_id)

    if mode == "auto" and router:
        route_result = router.route(request.query, ...)
        if route_result.mode == "multi_agent":
            return await _handle_multi_agent_query(request, cm, conversation_id)

    # mode == "single" 或 auto 下的非 multi_agent: 走单 Agent
    return await _handle_single_agent_query(request, cm)
```

## 3. 不改动清单

| 模块 | 文件 | 原因 |
|------|------|------|
| ReActAgent | `src/agent_core.py` | 核心推理逻辑不动 |
| OrchestratorAgent | `src/orchestrator_agent.py` | 完全不变（`run()` 继承自 ReActAgent，已含 `company_name` 参数） |
| DelegateTool | `src/tools/delegate_tool.py` | 委托调度逻辑不动 |
| Reflector | `src/reflector.py` | 反思核心逻辑不动 |
| Router | `src/router.py` | 路由分类逻辑不动 |
| Worker Agents | `src/worker_agents/*.py` | 5 个 Worker 全部不动 |
| SharedMemory / AgentRegistry | `src/shared_memory.py` / `src/agent_registry.py` | 阶段二已稳定 |
| RAG 管线 | `src/retrieval.py` / `src/query_processor.py` | 检索逻辑不动 |
| 前端 | `frontend/` | Phase 1 不做前端改动 |
