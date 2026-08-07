# TDD: 步骤 0.3 三层路由

> 编码: UTF-8 | 变更: multi-agent-step03
>
> 图例: :green_circle: 未通过 | :green_circle: 已通过
>
> 最后验证: 2026-08-06 | 21/21 通过

---

## TC-30: QueryRouter 基础功能

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-30-01 | QueryRouter 实例化 | 功能 | 传入 DashScopeProvider 可创建 QueryRouter | :green_circle: |
| TC-30-02 | RouteResult 数据结构 | 格式 | mode/trace/category/reasoning 字段正确 | :green_circle: |
| TC-30-03 | RouteResult.to_dict() 输出 | 格式 | to_dict() 返回合法 dict | :green_circle: |
| TC-30-03b | RouteResult.to_dict() 无 category | 格式 | 无 category 时 to_dict() 不含 category 键 | :green_circle: |

---

## TC-31: 正则分类路由

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-31-01 | 单公司单指标查询路由到 rag | 路由 | "中芯国际2024年营收" -> mode="rag", trace="regex" | :green_circle: |
| TC-31-02 | 单公司趋势查询路由到 agent | 路由 | "中芯国际毛利率同比增长率" -> mode="agent", trace="regex" | :green_circle: |
| TC-31-03 | 单公司计算查询路由到 agent | 路由 | "中芯国际营收同比增长率" -> mode="agent", trace="regex" | :green_circle: |
| TC-31-04 | 双公司对比路由到 multi_agent | 路由 | "中国移动和中国联通2024年营收对比" -> mode="multi_agent", trace="regex" | :green_circle: |
| TC-31-05 | 三公司对比路由到 multi_agent | 路由 | "三大运营商营收对比" -> mode="multi_agent" | :green_circle: |

---

## TC-32: turbo 兜底分类

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-32-01 | planner 未命中走 turbo | 路由 | "中芯国际营收走势图" -> trace="turbo"（需 LLM 调用） | :green_circle: |
| TC-32-02 | turbo 返回 "simple" -> rag | 路由 | mock turbo 返回 "simple" -> mode="rag" | :green_circle: |
| TC-32-03 | turbo 返回 "compound" -> agent | 路由 | mock turbo 返回 "compound" -> mode="agent" | :green_circle: |
| TC-32-04 | turbo 返回 "multi" -> multi_agent | 路由 | mock turbo 返回 "multi" -> mode="multi_agent" | :green_circle: |

---

## TC-33: turbo 容错

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-33-01 | turbo 调用失败回退到 agent | 容错 | mock turbo success=False -> mode="agent" | :green_circle: |
| TC-33-02 | turbo 返回空内容回退到 rag | 容错 | mock turbo content="" -> mode="rag"（不匹配 multi/compound 走 else 分支） | :green_circle: |

---

## TC-34: 路由统计

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-34-01 | 路由统计正确累计 | 统计 | 多次调用后 get_stats() 返回正确计数 | :green_circle: |
| TC-34-02 | 正则命中率计算正确 | 统计 | get_stats()["regex_hit_rate"] 计算正确 | :green_circle: |

---

## TC-35: API 集成

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-35-01 | api_service 初始化 QueryRouter | 集成 | _shared_state["query_router"] 非 None | :green_circle: |
| TC-35-02 | /api/agent/query 正常返回（无回归） | 集成 | 简单查询正常返回结果 | :green_circle: |
| TC-35-03 | /api/agent/stream 发送 router_decision 事件 | 集成 | SSE 流中含 type=="router_decision" 事件（connected 事件之后） | :green_circle: |

---

## TC-36: multi_agent fallback

| 编号 | 测试项 | 类型 | 验证点 | 状态 |
|:--:|------|:--:|------|:--:|
| TC-36-01 | multi_agent 模式 fallback 到单 Agent | 集成 | 多公司对比查询走单 Agent（不报错） | :green_circle: |

---

## 测试说明

> 1. TC-32-01（turbo 兜底）依赖 LLM 调用，测试时需有有效 API Key。
> 2. TC-32-02 ~ TC-32-04、TC-33-01 ~ TC-33-02、TC-34-01 中涉及 turbo 路径的测试，需使用 **"中芯国际营收走势图"** 作为查询文本。该查询中 planner 返回 `single + need_chart=True + need_calculate=False`，恰好穿透三层 regex 条件到达 turbo 兜底。其他模糊查询（如"帮我看看"、"模糊查询"等）会被 planner 的 `single` catch-all 直接捕获为 `rag/regex`，不会触发 turbo。
