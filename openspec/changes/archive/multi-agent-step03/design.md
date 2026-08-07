# SDD: 步骤 0.3 三层路由

> 编码: UTF-8 | 变更: multi-agent-step03

---

## 1. 架构设计

```
用户查询
  |
  v
QueryRouter.route(query, context)
  |
  +-- 1a: planner._classify_query() 正则分类
  |     - single + no calc + no chart -> rag
  |     - trend/compound + companies<2 -> agent
  |     - multi_compare / companies>=2 -> multi_agent
  |     - 未命中 -> 1b
  |
  +-- 1b: qwen-turbo 兜底三分类
        - simple -> rag
        - compound -> agent
        - multi -> multi_agent
        - 失败 -> agent (安全兜底)
  |
  v
RouteResult(mode, trace, category, reasoning)
```

---

## 2. 核心类设计

### 2.1 RouteResult

| 字段 | 类型 | 说明 |
|------|------|------|
| mode | str | 路由模式: "rag" / "agent" / "multi_agent" |
| trace | str | 来源追踪: "regex" / "turbo" |
| category | QueryCategory | planner 分类详情（turbo 路径无） |
| reasoning | str | 路由决策说明 |

### 2.2 QueryRouter

| 方法 | 说明 |
|------|------|
| __init__(turbo_llm) | 初始化路由器，传入 LLM Provider |
| route(query, context) | 路由决策主入口 |
| _turbo_classify(query, context) | turbo 兜底分类 |
| _record(result) | 记录路由统计 |
| get_stats() | 获取路由统计信息 |

---

## 3. API 集成

### 3.1 初始化

在 `_init_globals()` 中，DashScopeProvider 初始化之后创建 QueryRouter 实例，存入 `_shared_state["query_router"]`。

### 3.2 端点集成

- `/api/agent/query`: Agent 创建之前插入路由决策
- `/api/agent/stream`: event_generator() 闭包内，connected 事件之后插入路由决策
- multi_agent 模式暂 fallback 到单 Agent（日志标注）

### 3.3 SSE 事件

新增 `router_decision` 事件，payload 含 mode/trace/category/reasoning。

---

## 4. 依赖关系

- 依赖步骤 0.1: LLMProvider 抽象层（turbo Provider 实例）
- 被步骤 2.4 依赖: route_result.mode=="multi_agent"
- 被步骤 4.1 依赖: 路由基础设施
