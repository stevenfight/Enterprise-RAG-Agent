# 任务清单: 多 Agent 升级 - 阶段二 Orchestrator + 委托

> 编码: UTF-8
> 日期: 2026-08-06
> 状态: 全部完成（2026-08-07）

---

## 步骤 2.1：AgentRegistry（纯新增，无依赖）

- [x] 创建 `src/agent_registry.py`：AgentCapability dataclass + AgentRegistry 类
- [x] 在 `_init_globals()` 中初始化 AgentRegistry 并注册 DataAgent
- [x] 验证：单元测试 AgentCapability 3 项
- [x] 验证：单元测试 AgentRegistry 7 项

## 步骤 2.2：SharedMemory（纯新增，无依赖）

- [x] 创建 `src/shared_memory.py`：SharedMemory 类
- [x] 验证：单元测试 SharedMemory 6 项

## 步骤 2.3：DelegateTool（依赖 2.1 + 2.2）

- [x] 创建 `src/tools/delegate_tool.py`：DelegateTool + _DelegateStepCallback
- [x] 修复：失败分支的 results dict 补齐 `task`/`company` 键（避免 summary 生成 KeyError）
- [x] 验证：单元测试 DelegateTool 6 项

## 步骤 2.4：OrchestratorAgent + api_service 集成（依赖 2.1 + 2.2 + 2.3）

- [x] 创建 `src/orchestrator_agent.py`：OrchestratorAgent 类
- [x] 修改 `src/api_service.py` _init_globals()：初始化多 Agent 组件
- [x] 修改 `src/api_service.py` api_agent_query：multi_agent 分支执行多 Agent 链路
- [x] 修改 `src/api_service.py` api_agent_stream：multi_agent 分支执行多 Agent SSE 流
- [x] 验证：单元测试 OrchestratorAgent 6 项
- [ ] 验证：手动测试 POST 端点 multi_agent 模式（待用户验证）
- [ ] 验证：手动测试 SSE 端点 multi_agent 模式（待用户验证）

## 验证（全部步骤完成后）

- [x] 运行新增 28 项 TDD 测试 — 全部通过（其中 2 项需 API Key 已实际运行）
- [x] 运行现有 126 项回归测试（步骤 0.1/0.2/0.3/1.1） — 全部通过（5 项 skip）
- [x] 确认不改动模块无变化（api_service 导入验证 OK）

---

## 实施记录

| 日期 | 步骤 | 文件 | 操作 | 说明 |
|------|------|------|------|------|
| 2026-08-06 | 2.1 | `src/agent_registry.py` | 新增 | AgentCapability + AgentRegistry（99 行） |
| 2026-08-06 | 2.2 | `src/shared_memory.py` | 新增 | SharedMemory 跨 Agent 共享记忆（152 行） |
| 2026-08-06 | 2.3 | `src/tools/delegate_tool.py` | 新增 | DelegateTool + _DelegateStepCallback（250 行） |
| 2026-08-06 | 2.4 | `src/orchestrator_agent.py` | 新增 | OrchestratorAgent 主控 Agent（91 行） |
| 2026-08-06 | 2.4 | `src/api_service.py` | 修改 | _init_globals 注册 DataAgent；POST/SSE 端点 multi_agent 分支 |
| 2026-08-07 | 2.3 | `src/tools/delegate_tool.py` | 修复 | 失败分支 results dict 补齐 `task`/`company` 键 |
| 2026-08-07 | 验证 | `tests/tdd_multi_agent_step05.py` | 新增 | 28 项 TDD 测试，全部通过 |
