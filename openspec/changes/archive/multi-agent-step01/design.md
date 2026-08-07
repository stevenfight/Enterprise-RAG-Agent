# 设计文档: 步骤 0.1 多 Agent 基础能力搭建

> 编码: UTF-8 | 变更: multi-agent-step01

---

## 1. 架构概览

步骤 0.1 不改变整体架构（仍为单 Agent），但为多 Agent 架构搭建基础能力：

```
                        +-----------------+
                        | api_service.py  |
                        |  (新增 Provider |
                        |   初始化+传递)  |
                        +--------+--------+
                                 |
                    +------------v------------+
                    |      ReActAgent         |
                    |  (新增参数: llm_provider |
                    |   prompt_name            |
                    |   step_callback)         |
                    +------+-------+----------+
                           |       |
              +------------+       +------------+
              |                                   |
    +---------v--------+              +----------v----------+
    |  LLMProvider     |              |  StepCallback       |
    |  (抽象层)         |              |  (线程安全事件队列) |
    |  - DashScope     |              |  - on_step()        |
    |  - OpenAI(预留)   |              |  - on_done()        |
    +------------------+              +---------------------+
              |
    +---------v--------+
    | WorkerToolFactory |
    | (按需创建Registry)|
    +-------------------+
```

---

## 2. 核心设计

### 2.1 LLMProvider 双路径

```
_call_llm():
  if self.llm_provider:
    response = self.llm_provider.chat(messages, model, temperature, timeout)
    if response.success:
      self._total_tokens += response.usage.total
      return response.content
    else:
      return None
  else:
    # 原有 dashscope.Generation.call() 路径
    resp = Generation.call(...)
    if resp.status_code == 200:
      self._total_tokens += usage.total
      return content
    else:
      return None
```

### 2.2 Prompt 外部化链路

```
_build_system_prompt(tool_desc, context, shared_context, agent_desc):
  template = custom_system_prompt OR _load_prompt_template()
  Template.safe_substitute(
    tool_descriptions=tool_desc,
    context=context,
    shared_context=shared_context,
    agent_descriptions=agent_desc
  )

_load_prompt_template():
  yaml_path = config/agent_prompts.yaml
  if yaml exists:
    section = yaml[prompt_name]
    return section["template"]
  else:
    return _default_system_prompt  # 硬编码回退
```

### 2.3 StepCallback 事件流

```
Worker 线程:
  callback.on_step("thought", 1, "内容")  → event_queue.put({type: "worker_step", ...})
  callback.on_step("action", 1, "retrieve") → event_queue.put(...)
  callback.on_step("observation", 1, "...") → event_queue.put(...)
  callback.on_done(result)                 → event_queue.put({type: "worker_done", ...})

SSE 消费线程:
  event = asyncio.to_thread(event_queue.get)
  yield SSE event
```

### 2.4 sources 收集链路

```
_execute_action(action, action_input):
  result = tool_registry.execute(action, **params)
  if action == "retrieve" and result.success:
    for r in result.data["results"]:
      self._sources.append({
        source: r["source_file"],
        content: r["text"][:200],
        pages: r["pages"],
        company_name: r["company_name"]
      })
  return result.to_observation()
```

---

## 3. 文件改动明细

| 文件 | 操作 | 改动点 |
|------|:--:|------|
| `src/llm_provider.py` | 新增 | LLMUsage + LLMResponse + BaseLLMProvider + DashScopeProvider + OpenAICompatibleProvider |
| `src/step_callback.py` | 新增 | StepCallback (on_step + on_done) |
| `src/worker_tool_factory.py` | 新增 | WorkerToolFactory (create_registry) |
| `src/agent_core.py` | 修改 | AgentResult 3 字段 + __init__ 3 参数 + _build_system_prompt + _load_prompt_template + _call_llm 双路径 + run/run_stream 签名 + sources 收集 |
| `src/api_service.py` | 修改 | _init_globals Provider 初始化 + _create_per_request_agent 新参数 + _load_agent_config 新配置节 |
| `src/tools/retrieve_tool.py` | 修改 | _init_lock + double-check locking |
| `config/agent_config.json` | 修改 | 新增 models + multi_agent 配置节 |

---

## 4. 向后兼容策略

所有新增参数为可选，默认值保证原有行为不变：

| 参数 | 默认值 | 不传时行为 |
|------|--------|---------|
| llm_provider | None | 走原有 dashscope.Generation.call() |
| prompt_name | "default" | 使用 _default_system_prompt |
| step_callback | None | 不推送事件 |
| shared_context | "" | 不注入上下文 |
| agent_descriptions | "" | 不注入 Agent 描述 |
