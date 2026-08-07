# Tasks: 步骤 1.1 DataAgent

> 编码: UTF-8 | 变更: multi-agent-step04

---

## 1. 新增 src/worker_agents/__init__.py

- [x] 1.1 创建 worker_agents 包（含文件头注释）

## 2. 新增 src/worker_agents/data_agent.py

- [x] 2.1 创建 DataAgent 类（继承 ReActAgent）
- [x] 2.2 注册 retrieve 工具到 ToolRegistry
- [x] 2.3 设置 prompt_name="data_agent"
- [x] 2.4 设置 max_steps=3, temperature=0.2, model="qwen-turbo"

## 3. TDD 测试

- [x] 3.1 创建 tests/tdd_multi_agent_step04.py（16 项测试，全线标红）
- [x] 3.2 运行测试，逐步标绿（11 passed, 5 skipped 因无 API Key）
- [x] 3.3 运行现有测试确认无回归（步骤 0.1 + 0.2 + 0.3 共 110 项，全部通过）

## 4. 更新 TDD 文档

- [x] 4.1 每项测试通过后，将 tdd-step04.md 中对应 :red_circle: 改为 :green_circle:
- [ ] 4.2 独立检索验证（对比 DataAgent 与现有 Agent 的检索结果，需 API Key）
