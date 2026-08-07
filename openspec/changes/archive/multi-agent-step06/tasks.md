# 任务清单: 多 Agent 升级 - 阶段三 并行 + 其余 Worker + Reflector 接入

> 编码: UTF-8
> 日期: 2026-08-07
> 状态: 已完成

---

## 步骤 3.1：DelegateTool 并行升级（依赖 2.3）

- [x] `delegate_tool.py` 新增 `_group_by_dependency(tasks)`：按 agent 类型批次分组
- [x] `delegate_tool.py` 新增 `_run_batch_parallel(batch)`：ThreadPoolExecutor 并行执行同批任务
- [x] `delegate_tool.py` 新增 `_run_worker_task(task, cap, shared_ctx)`：单任务执行单元（创建 Worker → 执行 → 写 SharedMemory → 返回结果）
- [x] `delegate_tool.py` 保留串行回退路径（单任务/降级）
- [x] `delegate_tool.py` Worker 超时控制：future.result(timeout=worker_timeout)（从 multi_agent 配置读取）
- [x] `delegate_tool.py` Worker 失败重试：worker_max_retries（从 multi_agent 配置读取）
- [x] 验证：TDD 并行 7 项全部转绿

## 步骤 3.2：CalcAgent（依赖 0.1/0.2/1.1/2.x，与 3.3/3.4/3.5 同级并行）

- [x] 创建 `src/worker_agents/calc_agent.py`：继承 ReActAgent，持有 calculator+retrieve
- [x] 配置：prompt_name="calc_agent"、qwen-plus、temp 0.1、max_steps=5
- [x] 验证：TDD CalcAgent 5 项全部转绿

## 步骤 3.3：CompareAgent（依赖 0.1/0.2/1.1/2.x，与 3.2/3.4/3.5 同级并行）

- [x] 创建 `src/worker_agents/compare_agent.py`：继承 ReActAgent，持有 compare+retrieve
- [x] 配置：prompt_name="compare_agent"、qwen-max、temp 0.3、max_steps=5
- [x] 优先从 SharedMemory 获取数据（避免 CompareTool 重复加载向量库）
- [x] 验证：TDD CompareAgent 5 项全部转绿

## 步骤 3.4：ChartAgent（依赖 0.1/0.2/1.1/2.x，与 3.2/3.3/3.5 同级并行）

- [x] 创建 `src/worker_agents/chart_agent.py`：继承 ReActAgent，只持有 chart 工具
- [x] 配置：prompt_name="chart_agent"、qwen-max、temp 0.3、max_steps=5
- [x] 从 SharedMemory 提取结构化数值构造 chart data 参数
- [x] 验证：TDD ChartAgent 5 项全部转绿

## 步骤 3.5：VerifyAgent（依赖 0.1/0.2/1.1/2.x，与 3.2/3.3/3.4 同级并行）

- [x] 创建 `src/worker_agents/verify_agent.py`：继承 ReActAgent，持有 verify+retrieve
- [x] 配置：prompt_name="verify_agent"、qwen-plus、temp 0.1、max_steps=5
- [x] claim 从 SharedMemory 获取，source_text 由 retrieve 检索获得
- [x] 验证：TDD VerifyAgent 5 项全部转绿

## 步骤 3.5 收尾：DelegateTool._create_agent 扩展 + api_service 注册（依赖 3.1/3.2/3.3/3.4/3.5 全部完成）

- [x] `delegate_tool.py` `_create_agent` 支持 CalcAgent/CompareAgent/ChartAgent/VerifyAgent 实例化
- [x] `api_service.py` `_init_globals()` AgentRegistry 注册 4 个新 Worker 能力元数据
- [x] 验证：Orchestrator 的 agent_descriptions 自动包含 5 个 Worker

## 步骤 3.6：Reflector 接入验证（阶段二已提前实现）

- [x] 验证：POST/SSE multi_agent 分支 Reflector 反思已生效（get_all_sources 聚合来源）
- [x] 验证：TDD 收尾 3 项全部转绿

## 验证（全部步骤完成后）

- [x] 运行新增 30 项 TDD 测试全部通过
- [x] 运行阶段二 28 项 TDD 测试全部通过（回归）
- [x] 运行现有 126 项测试全部通过（回归）
- [x] 确认不改动模块无变化

---

## 实施记录

| 日期 | 步骤 | 文件 | 操作 | 说明 |
|------|------|------|:--:|------|
| 2026-08-07 | 3.1 | `src/tools/delegate_tool.py` | 修改 | 并行执行 + 批次分组 + 超时/重试 |
| 2026-08-07 | 3.2 | `src/worker_agents/calc_agent.py` | 新增 | CalcAgent |
| 2026-08-07 | 3.3 | `src/worker_agents/compare_agent.py` | 新增 | CompareAgent |
| 2026-08-07 | 3.4 | `src/worker_agents/chart_agent.py` | 新增 | ChartAgent |
| 2026-08-07 | 3.5 | `src/worker_agents/verify_agent.py` | 新增 | VerifyAgent |
| 2026-08-07 | 3.5 | `src/tools/delegate_tool.py` | 修改 | _create_agent 扩展 |
| 2026-08-07 | 3.5 | `src/api_service.py` | 修改 | 注册 4 个 Worker 元数据 |
| 2026-08-07 | 验证 | `tests/tdd_multi_agent_step06.py` | 新增 | 30 项 TDD |
