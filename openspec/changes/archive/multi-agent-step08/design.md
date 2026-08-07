# 架构设计: 多 Agent 升级 - 阶段五 调优（第一轮）

> 编码: UTF-8
> 日期: 2026-08-07

---

## 1. 整体架构

阶段五调优涉及 4 个文件的局部改动，不改变整体调用链路：

```
ToolRegistry.get_tool_descriptions()  ──增强──▶ 嵌套参数(items.properties)递归展示
                                                        │
                                                        ▼
OrchestratorAgent System Prompt (agent_prompts.yaml orchestrator 节)
                                                        │
                         ┌──────────────────────────────┘
                         ▼
                  DelegateTool.run(tasks)
                         │  ──增强──▶ data 增加 parallel_batch_count / estimated_serial_ms
                         ▼
                Worker Agent 执行（不变）
                         │
                         ▼
api_service._handle_multi_agent_query()
                         │  ──增强──▶ 日志记录 total_tokens + worker_count（观测）
                         ▼
                AgentQueryResponse（契约不变）
```

## 2. 详细设计

### 2.1 工具描述嵌套参数展示

**文件**: `src/tools/__init__.py`

**当前实现**（get_tool_descriptions）：
```python
for tool in self._tools.values():
    param_desc = ""
    if tool.parameters and "properties" in tool.parameters:
        props = tool.parameters["properties"]
        param_desc = ", ".join(
            f"{k}({v.get('description', '')})" for k, v in props.items()
        )
    lines.append(f"- {tool.name}: {tool.description}" +
                 (f" [参数: {param_desc}]" if param_desc else ""))
```

**问题**：delegate 的 `parameters["properties"]["tasks"]` 是数组结构（含 `items.properties`），当前只展示 `tasks(要委托的子任务列表)`，LLM 无法理解 `tasks` 数组内必须包含 `agent`/`task` 字段。

**增强设计**：当参数描述 `v` 为 dict 且含 `items` 且 `items.properties` 时，递归展开子字段说明：

```
- delegate: 将子任务委托给指定的 Worker Agent 执行。... [参数: tasks(要委托的子任务列表，每项含: agent(Worker Agent 名称), task(子任务描述), company_name(可选，指定公司名称))]
```

**实现方式**：新增私有辅助函数 `_format_param_desc(v)`，递归处理：

```python
    @staticmethod
    def _format_param_desc(v: dict) -> str:
        """格式化单个参数描述，支持嵌套 items.properties 递归展示"""
        desc = v.get("description", "")
        items = v.get("items")
        if isinstance(items, dict) and isinstance(items.get("properties"), dict):
            sub = ", ".join(
                f"{k}({ToolRegistry._format_param_desc(sv)})"
                for k, sv in items["properties"].items()
            )
            return f"{desc}（每项含: {sub}）" if desc else f"每项含: {sub}"
        return desc
```

### 2.2 orchestrator 节补充 delegate 调用示例

**文件**: `config/agent_prompts.yaml`

在 orchestrator 节「调度规则」后新增「调用示例」小节：

```yaml
    调用示例（delegate 的 Action Input 必须使用 tasks 数组格式）：
    Action Input: {"tasks": [{"agent": "DataAgent", "task": "查询中国移动2024年营业收入"}]}
    多任务并行示例：
    Action Input: {"tasks": [
        {"agent": "DataAgent", "task": "查询中国移动2024年营收", "company_name": "中国移动"},
        {"agent": "DataAgent", "task": "查询中国联通2024年营收", "company_name": "中国联通"}
    ]}
```

### 2.3 DelegateTool 并行批次统计

**文件**: `src/tools/delegate_tool.py`

在 `run()` 中复用 `_group_by_dependency()` 结果，向 `data` 增加观测字段：

```python
# 1. 按依赖关系分组批次（原有逻辑）
batches = self._group_by_dependency(tasks)

# 2. 逐批执行（原有逻辑）
results = []
worker_elapsed_list = []
for batch_index, batch in enumerate(batches):
    ...
    batch_results = self._run_batch_parallel(...)
    results.extend(batch_results)
    worker_elapsed_list.extend(r.get("elapsed_ms", 0) for r in batch_results)

# 3. 汇总结果（原有逻辑 + 新增统计字段）
data = {
    "summary": ...,
    "total": len(tasks),
    "results": results,
    "parallel_batch_count": len(batches),           # 新增：实际并行批次数
    "estimated_serial_ms": sum(worker_elapsed_list),  # 新增：预估串行耗时（各 worker 耗时之和）
}
```

**说明**：`parallel_batch_count` 为 1 时表示全部任务同批串行/并行执行；`estimated_serial_ms` 为各 worker 实际耗时求和，用于估算若全部串行执行的耗时。两者均为观测字段，不改变执行逻辑与 `ToolResult` 契约（`data` 为自由结构）。

### 2.4 api_service 成本观测日志

**文件**: `src/api_service.py`

在 `_handle_multi_agent_query()` 的日志处增加 total_tokens 统计（workers 保持不变）：

```python
logger.info("[api_service] 多 Agent 执行完成: success=%s, workers=%d, total_tokens=%d",
            result.success, len(shared_memory.agent_outputs),
            getattr(result, "total_tokens", 0))
```

**说明**：`AgentResult.total_tokens` 已在阶段零实现；`shared_memory.agent_outputs` 数量即 worker 结果数。仅追加日志字段，不改响应结构。

### 2.5 路由准确率观测

`QueryRouter.get_stats()` 已有 `by_mode` / `by_trace` / `regex_hit_rate` 统计能力（阶段零实现），路由逻辑不改。阶段五通过回归测试验证简单查询（如"中芯国际2024年营收是多少"）不被误路由到 `multi_agent`。

## 3. 变更文件汇总

| 文件 | 改动量 | 改动类型 |
|------|:--:|------|
| `src/tools/__init__.py` | ~12 行 | 修改：get_tool_descriptions 支持嵌套展示 |
| `src/tools/delegate_tool.py` | ~8 行 | 修改：run() 增加并行批次统计字段 |
| `config/agent_prompts.yaml` | ~7 行 | 修改：orchestrator 节增加 delegate 调用示例 |
| `src/api_service.py` | ~2 行 | 修改：multi_agent 日志增加 token + workers 统计 |

**不修改**：`src/agent_core.py`、`src/orchestrator_agent.py`、`src/router.py`、`src/shared_memory.py`、`src/agent_registry.py`、5 个 Worker、`src/reflector.py`、前端。
