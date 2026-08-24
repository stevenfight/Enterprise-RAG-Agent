# SDD 规范: P0 关键缺陷修复 (v5.1)

> 编码: UTF-8
> 状态: 规划中
> 对应变更: openspec/changes/p0-critical-fixes/

---

## 1. 规范说明

本规范定义了 5 个 P0 缺陷修复后的目标行为。每个规范项描述"修复后应该怎样"，用于指导开发实现和 TDD 测试用例编写。

---

## 2. 规范项

### 规范 1: empty_result_count 重置逻辑 (SP0-01)

**位置**: `src/agent_core.py:262`

**当前行为**:
```python
empty_result_count = max(0, empty_result_count - 1)  # 阶梯递减
```
如 `empty_result_count=2` 遇到空结果后变为 3，遇到有效结果后降为 2（不归零）。

**目标行为**:
```python
empty_result_count = 0  # 有结果直接归零
```
`empty_result_count` 的语义是"连续空结果次数"，有有效结果时归零。`_is_empty_result()` 返回 False 时计数器直接设为 0。

**约束**:
- 不影响 `_is_empty_result()` 的判断逻辑
- 不影响空结果警告阈值的比较逻辑

---

### 规范 2: run_stream 强制答案传入正确推理链 (SP0-02)

**位置**: `src/agent_core.py:463`

**当前行为**: `self._generate_forced_answer(messages, [])`，传入空列表。

**目标行为**: `self._generate_forced_answer(messages, reasoning_chain)`，传入流式模式中累积的推理步骤列表。

`reasoning_chain` 列表结构:
```python
reasoning_chain.append({
    "step": step + 1,
    "thought": thought,
    "action": action,
    "observation": observation_summary,
})
```
在 while 循环每个有效步骤结束后 `append`，最终在达到 max_steps 时传入 `_generate_forced_answer()`。

**约束**:
- 不影响 run_stream yield 的事件格式
- 不影响正常完成（非 max_steps 触发）的逻辑
- reasoning_chain 的格式与 run() 方法一致

---

### 规范 3: memory 配置生效 (SP0-03)

**位置**: `src/api_service.py:385` + `config/agent_config.json:11-14`

**当前行为**: `AgentMemory()` 使用所有默认值，`enable_long_term` 始终为 `False`。

**目标行为**: 从 `config/agent_config.json` 的 `memory` 段读取参数，传入 `AgentMemory()`:
```python
mem_cfg = config.get("memory", {})
memory = AgentMemory(
    working_memory_limit=mem_cfg.get("working_memory_limit", 10),
    episodic_memory_turns=mem_cfg.get("episodic_memory_turns", 5),
    enable_long_term=mem_cfg.get("enable_long_term", False),
)
```
使用 `.get()` 并提供默认值，兼容 config 缺少 `memory` 段的历史配置。

**约束**:
- AgentMemory 类本身不修改
- 不改变 AgentMemory 的初始化语义
- 不影响 ConversationManager 的 memory 管理逻辑

---

### 规范 4: Agent 实例按请求创建，消除全局单例并发竞争 (SP0-04)

**位置**: `src/api_service.py:585-596` + `api_agent_query()` + `api_agent_query_stream()`

**当前行为**: 全局 `agent` 对象在每次请求时被直接修改 `agent.memory`、`agent.max_steps`、`agent.temperature`，并发请求互相覆盖。

**目标行为**:
1. `startup()` 中将 `tool_registry`、`planner`、`reflector`、`ag_cfg` 绑定到模块级全局变量（`_shared_tool_registry`, `_shared_planner`, `_shared_reflector`, `_ag_cfg`），这些是无状态的资源
2. `api_agent_query()` 和 `api_agent_query_stream()` 中每个请求创建独立的 `ReActAgent` 实例:
```python
agent = ReActAgent(
    tool_registry=_shared_tool_registry,
    memory=cm.agent_memory,
    max_steps=min(request.max_steps, max_steps_hard_limit),
    temperature=request.temperature,
    model=_ag_cfg["model"],
    llm_timeout=_ag_cfg["llm_timeout"],
    max_retries=_ag_cfg["max_retries"],
)
```
3. 全局 `agent` 变量不再被请求处理函数引用

**约束**:
- 不影响 ConversationManager 会话隔离机制
- 不影响 API 接口的请求/响应格式
- Agent 实例创建性能开销可忽略（仅属性赋值，无 IO）

---

### 规范 5: API Key 鉴权 (SP0-05)

**位置**: `src/api_service.py` + `config/agent_config.json`

**目标行为**:

**5.1 中间件**: 在 FastAPI 应用中注册 `APIAuthMiddleware`，拦截所有请求:
- 白名单路径（无需鉴权）: `/api/health`, `/docs`, `/openapi.json`, `/redoc`
- 从 `Authorization` 请求头提取 `Bearer <token>`
- token 与配置中的 `api_key` 对比
- 匹配失败返回 `401 {"detail": "未授权: 缺少或无效的 API Key"}`
- 匹配成功放行

**5.2 API Key 来源**: 优先级: 环境变量 `API_KEY` > `config/agent_config.json` 的 `api.key`。都未设置时使用默认值 `"no-key-needed"` 并打印 WARNING。

**5.3 max_steps 硬上限**: `max_steps = min(request.max_steps, max_steps_hard_limit)`，`max_steps_hard_limit` 默认 15（从 `config/agent_config.json` 的 `api.max_steps_hard_limit` 读取）。

**5.4 错误信息脱敏**: HTTPException 的 detail 不返回原始 `str(e)`，改为通用错误信息 + 日志记录详细错误。

**约束**:
- `/api/health` 健康检查不收鉴权限制（供监控系统使用）
- 鉴权失败不暴露配置信息
- 向后兼容: 默认 Key 为 `"no-key-needed"`，启动时 WARNING 日志提醒修改

---

## 3. 配置变更

`config/agent_config.json` 新增:

```json
{
    "api": {
        "key": "no-key-needed",
        "max_steps_hard_limit": 15
    }
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `api.key` | string | `"no-key-needed"` | API Key，环境变量 `API_KEY` 优先级更高 |
| `api.max_steps_hard_limit` | int | 15 | max_steps 硬上限，防止客户端拉高 token 消耗 |
