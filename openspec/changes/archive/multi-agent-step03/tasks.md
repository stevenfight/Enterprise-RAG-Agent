# Tasks: 步骤 0.3 三层路由

> 编码: UTF-8 | 变更: multi-agent-step03

---

## 1. 新增 src/router.py

- [x] 1.1 创建 RouteResult 类（mode/trace/category/reasoning + to_dict()）
- [x] 1.2 创建 QueryRouter 类（__init__ + route + _turbo_classify + _record + get_stats）
- [x] 1.3 实现三层路由逻辑（single->rag, trend/compound->agent, multi_compare->multi_agent, turbo 兜底）

## 2. 修改 src/api_service.py

- [x] 2.1 _init_globals 中初始化 QueryRouter
- [x] 2.2 /api/agent/query 端点插入路由决策
- [x] 2.3 /api/agent/stream 端点插入路由决策 + router_decision SSE 事件

## 3. TDD 测试

- [x] 3.1 创建 tests/tdd_multi_agent_step03.py（21 项测试，全线标红）
- [x] 3.2 运行测试，逐步标绿（21/21 通过）
- [x] 3.3 运行现有测试确认无回归（步骤 0.1 + 0.2 共 89 项，全部通过）

## 4. 更新 TDD 文档

- [x] 4.1 每项测试通过后，将 tdd-step03.md 中对应 :red_circle: 改为 :green_circle:
