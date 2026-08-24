# 设计文档: P0 关键缺陷修复 (v5.1)

> 编码: UTF-8

---

## 1. 修复 #1: empty_result_count 重置逻辑

### 当前代码 (agent_core.py:262)

```python
else:
    empty_result_count = max(0, empty_result_count - 1)  # 有结果则重置
    if empty_result_count == 0:
        logger.info("[ReActAgent] 空结果计数器: 发现有效结果, 计数器已重置为0")
```

### 问题分析

假设场景: `empty_result_count` 当前为 2，下一次检索返回有效结果:
- 执行 `max(0, 2 - 1)` = 1，计数器未归零
- 如果再遇到 1 次空结果，计数器变为 2，触发空结果处理阈值
- 注释说"重置"，实际是"递减 1"，语义和实现不一致

### 修复后

```python
else:
    empty_result_count = 0  # 有结果则重置
    logger.info("[ReActAgent] 空结果计数器: 发现有效结果, 计数器已重置为0")
```

`empty_result_count` 的语义是"连续空结果次数"，有结果就应归零。

---

## 2. 修复 #2: run_stream 强制答案传入空推理链

### 当前代码 (agent_core.py:463)

```python
forced_answer = self._generate_forced_answer(messages, [])
```

### 问题分析

`run_stream()` 方法在流式循环中通过 `yield` 返回推理步骤，但没有将步骤收集到 `reasoning_chain` 变量中。强制答案时传入空列表 `[]`，导致日志中推理链为空白。

### 修复方案

在 `run_stream()` 的 while 循环中累积 `reasoning_chain` 变量，类似于 `run()` 方法中的做法:

```python
reasoning_chain = []
while step < self.max_steps:
    # ... 推理逻辑 ...
    reasoning_chain.append({
        "step": step,
        "thought": thought,
        "action": action,
        "observation": observation_summary
    })
    # ... 流式输出 ...

# 达到 max_steps，强制生成答案
forced_answer = self._generate_forced_answer(messages, reasoning_chain)
```

---

## 3. 修复 #3: memory 配置生效

### 当前代码 (api_service.py:382-392)

```python
# AgentMemory 不再全局共享，改为每个 conversation_id 独立持有
# 此处传入一个占位 AgentMemory, 每次请求时切换到对应会话的记忆
agent = ReActAgent(
    tool_registry=agent_registry,
    memory=AgentMemory(),         # <-- 未传配置参数
    max_steps=ag_cfg["max_steps"],
    ...
)
```

### 问题分析

`config/agent_config.json` 中 `memory` 段配置了 `working_memory_limit: 10, episodic_memory_turns: 5, enable_long_term: true`，但 `api_service.py:385` 创建 `AgentMemory()` 时未传参，所有参数走默认值（`enable_long_term=False`）。

### 修复方案

从配置中读取 `memory` 段参数，传入 `AgentMemory()`:

```python
mem_cfg = config.get("memory", {})
agent = ReActAgent(
    tool_registry=agent_registry,
    memory=AgentMemory(
        working_memory_limit=mem_cfg.get("working_memory_limit", 10),
        episodic_memory_turns=mem_cfg.get("episodic_memory_turns", 5),
        enable_long_term=mem_cfg.get("enable_long_term", False),
    ),
    max_steps=ag_cfg["max_steps"],
    ...
)
```

> `config` 是 `_load_config()` 返回的完整配置字典，函数已存在于 `api_service.py` 中。

---

## 4. 修复 #4: Agent 全局单例并发安全

### 当前代码 (api_service.py:585-596)

```python
conversation_id = request.conversation_id or str(uuid.uuid4())
cm = _ensure_conversation(conversation_id)
if cm.agent_memory is None:
    cm.link_memory(AgentMemory())
agent.memory = cm.agent_memory       # 直接覆盖全局单例状态

agent.max_steps = request.max_steps   # 直接覆盖全局单例状态
agent.temperature = request.temperature  # 直接覆盖全局单例状态
```

### 问题分析

`agent` 是模块级全局变量（在 `startup()` 中创建）。并发请求 A 和 B 同时到达:
1. B 的 `agent.memory = cm_B.agent_memory` 覆盖 A 设置的 memory
2. A 后续推理使用的是 B 的 memory，导致会话隔离失效

### 修复方案: per-request 创建 Agent 实例

不再在请求处理中修改全局 `agent` 状态，改为每个请求创建独立的 `ReActAgent` 实例。共享 `tool_registry`、`planner`、`reflector`（这些是无状态的），仅 Agent 实例按请求创建。

```python
# 请求处理函数中，不再修改全局 agent
agent = ReActAgent(
    tool_registry=_shared_tool_registry,  # 模块级共享，无状态
    memory=cm.agent_memory,
    max_steps=min(request.max_steps, 15),  # 硬上限
    temperature=request.temperature,
    model=ag_cfg["model"],
    llm_timeout=ag_cfg["llm_timeout"],
    max_retries=ag_cfg["max_retries"],
)
```

`_shared_tool_registry` 和 agent 基础配置 (`ag_cfg`) 在 `startup()` 中初始化一次，存储在模块级变量中供请求复用。

---

## 5. 修复 #5: API Key 鉴权

### 设计目标

- 所有 `/v1/*` 和 `/api/*` 接口（`/api/health` 除外）需鉴权
- API Key 来源: 环境变量 `API_KEY` > `config/agent_config.json` 中 `api.key` > 默认值 `"no-key-needed"`（开发模式）
- 鉴权失败返回 401
- `max_steps` 请求参数加硬上限 15

### 实现方案: FastAPI 中间件

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

SKIP_AUTH_PATHS = {"/api/health", "/docs", "/openapi.json", "/redoc"}

class APIAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_AUTH_PATHS:
            return await call_next(request)
        
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权: 缺少 API Key"}
            )
        
        token = auth_header[len("Bearer "):]
        if token != _api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权: API Key 无效"}
            )
        
        return await call_next(request)
```

### 配置项

`config/agent_config.json` 新增:

```json
{
    "api": {
        "key": "your-api-key-here",
        "max_steps_hard_limit": 15
    }
}
```

### LangBot 兼容性

修了之后，需要同步更新服务器 LangBot 数据库中 `model_providers` 表的 `api_keys` 字段:

```sql
-- 修改前
'["no-key-needed"]'
-- 修改后  
'["<your-api-key>"]'
```

同时文章 19 的 SQL 示例和 curl 命令也需要相应更新。
