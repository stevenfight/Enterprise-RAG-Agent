# 变更提案: 多 Agent 升级 - 步骤 0.3 三层路由

> 编码: UTF-8
> 状态: 实施中
> 日期: 2026-08-06

---

## 1. 变更背景

步骤 0.1 已完成 LLMProvider + AgentResult 扩展 + ReActAgent 改造，步骤 0.2 已完成 Prompt 配置化。步骤 0.3 需要实现三层路由的第一层：复用 planner 正则分类 + qwen-turbo 兜底分类，自动判断用户查询应走 rag / agent / multi_agent 模式。

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 查询路由器 | 新增 QueryRouter 类，支持 route() 方法返回 RouteResult |
| 正则分类复用 | 复用 planner._classify_query() 实现 0 API 成本的正则分类 |
| turbo 兜底分类 | qwen-turbo 三分类兜底，覆盖正则未命中场景 |
| API 入口集成 | /api/agent/query 和 /api/agent/stream 集成路由决策 |
| SSE 事件扩展 | 新增 router_decision 事件类型 |
| 向后兼容 | 现有端点行为不变，multi_agent 暂 fallback 到单 Agent |

---

## 3. 变更范围

### 3.1 新增模块

| 模块 | 文件名 | 职责 |
|------|--------|------|
| 查询路由器 | `src/router.py` | QueryRouter + RouteResult，三层路由第一层 |

### 3.2 修改模块

| 模块 | 文件名 | 改动说明 |
|------|--------|------|
| API 服务 | `src/api_service.py` | 入口集成路由决策，~30 行修改 |

### 3.3 不修改模块

`src/planner.py`、`src/agent_core.py`、`src/llm_provider.py`、所有工具、配置文件、前端、部署

---

## 4. 关联风险

- R-03: planner 分类复用（低危，_classify_query 稳定）
- turbo API 不可用（中危，有 agent 模式兜底）
