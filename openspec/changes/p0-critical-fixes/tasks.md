# 任务清单: P0 关键缺陷修复 (v5.1)

> 编码: UTF-8
> 每个阶段完成后运行 `python tests/tdd_all_optimizations.py` 确保管道回归通过

---

## 阶段一: 修复 #1 empty_result_count 重置逻辑

- [x] 1.1 修改 `src/agent_core.py` L262: `empty_result_count = max(0, empty_result_count - 1)` → `empty_result_count = 0`
- [x] 1.2 运行 Agent 核心测试验证修复
- [ ] 1.3 TDD: TC-P0-01 通过后标绿

---

## 阶段二: 修复 #2 run_stream 强制答案传入正确推理链

- [x] 2.1 修改 `src/agent_core.py` L463: `self._generate_forced_answer(messages, [])` → `self._generate_forced_answer(messages, reasoning_chain)`
- [x] 2.2 在 `run_stream()` 方法 while 循环中累积 `reasoning_chain` 变量
- [x] 2.3 运行流式响应测试验证修复
- [ ] 2.4 TDD: TC-P0-02 通过后标绿

---

## 阶段三: 修复 #3 memory 配置生效

- [x] 3.1 在 `startup()` 中读取 `config["memory"]` 段配置
- [x] 3.2 修改 `api_service.py` L385: `AgentMemory()` 传入 `working_memory_limit`, `episodic_memory_turns`, `enable_long_term`
- [x] 3.3 验证: 检查 `enable_long_term=True` 时长期记忆是否启用
- [ ] 3.4 TDD: TC-P0-03 通过后标绿

---

## 阶段四: 修复 #4 Agent 全局单例并发安全

- [x] 4.1 在 `startup()` 中将 `tool_registry`, `planner`, `reflector`, `ag_cfg` 存入模块级变量（无状态共享）
- [x] 4.2 修改 `api_agent_query()` 和 `api_agent_query_stream()`: 不修改全局 agent，改为 per-request 创建 ReActAgent 实例
- [x] 4.3 全局 `agent` 变量改为 None（不再用作单例）
- [x] 4.4 运行并发测试验证 session 隔离
- [ ] 4.5 TDD: TC-P0-04 通过后标绿

---

## 阶段五: 修复 #5 API Key 鉴权

- [x] 5.1 修改 `config/agent_config.json`: 新增 `api` 配置节（`key`, `max_steps_hard_limit`）
- [x] 5.2 在 `api_service.py` 中新增 `APIAuthMiddleware` 类
- [x] 5.3 在 `app` 中注册中间件，白名单豁免 `/api/health`, `/docs`, `/openapi.json`, `/redoc`
- [x] 5.4 修改 `api_agent_query()` 和 `api_agent_query_stream()`: `max_steps` 加硬上限 `min(request.max_steps, HARD_LIMIT)`
- [x] 5.5 验证: 无 API Key 返回 401，有效 Key 正常放行
- [ ] 5.6 TDD: TC-P0-05a (鉴权相关, 4 条) + TC-P0-05b (max_steps 硬上限) 通过后标绿

---

## 阶段六: 文章同步更新

- [x] 6.1 更新文章 19 L57: `api_keys` 从 `["no-key-needed"]` 改为 `["<your-api-key>"]`
- [x] 6.2 更新文章 19 L291-293: curl 命令新增 `Authorization: Bearer <key>` Header

---

## 阶段七: 文档与收尾

- [ ] 7.1 更新 `CHANGELOG.md` - 记录 v5.1 P0 修复
- [ ] 7.2 更新 `openspec/project.md` - 演进路线新增 v5.1
- [ ] 7.3 运行全量 TDD 回归测试
- [ ] 7.4 更新服务器 LangBot 数据库 `api_keys` 字段
- [ ] 7.5 更新 TDD `tdd-p0-fixes.md` - 所有 TC-P0 用例标绿
