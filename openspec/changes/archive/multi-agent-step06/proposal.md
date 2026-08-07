# 变更提案: 多 Agent 升级 - 阶段三 并行 + 其余 Worker + Reflector 接入

> 编码: UTF-8
> 状态: 已完成
> 日期: 2026-08-07

---

## 1. 变更背景

阶段一（1.1 DataAgent）和阶段二（2.1 AgentRegistry + 2.2 SharedMemory + 2.3 DelegateTool + 2.4 OrchestratorAgent）已完成。当前 Orchestrator 已能把子任务委托给 DataAgent 执行并聚合结果，但存在三个不足：

1. **串行执行慢**：DelegateTool.run() 对同批任务（如 3 家公司的数据检索）逐个串行执行，4 公司对比场景延迟约 8s。
2. **Worker 能力单一**：目前只有 DataAgent（纯检索）。计算、对比、图表、审核能力尚未成为独立 Worker，Orchestrator 无法委托这些专业任务。
3. **质量保障缺失**：多 Agent 链路的最终答案尚未接 Reflector 反思（该工作已在阶段二 api_service 集成时提前完成，阶段三仅需验证收尾）。

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| 并行执行 | 同批次独立任务并行运行，4 公司对比延迟从 ~8s 降至 ~3s |
| CalcAgent | 继承 ReActAgent，持有 calculator+retrieve，qwen-plus (temp 0.1)，只做计算 |
| CompareAgent | 继承 ReActAgent，持有 compare+retrieve，qwen-max (temp 0.3)，输出 Markdown 对比表 |
| ChartAgent | 继承 ReActAgent，持有 chart，qwen-max (temp 0.3)，从 SharedMemory 提取数据生成图表 |
| VerifyAgent | 继承 ReActAgent，持有 verify+retrieve，qwen-plus (temp 0.1)，输出审核报告 |
| Reflector 接入 | 多 Agent 链路答案经 Reflector 反思（已在阶段二完成，验证收尾） |
| 向后兼容 | 阶段二 28 项 TDD + 现有 126 项回归测试全部通过 |

## 3. 变更范围

### 3.1 新增模块

| 模块 | 文件名 | 职责 |
|------|--------|------|
| CalcAgent | `src/worker_agents/calc_agent.py` | 财务计算 Worker |
| CompareAgent | `src/worker_agents/compare_agent.py` | 横向对比 Worker |
| ChartAgent | `src/worker_agents/chart_agent.py` | 图表渲染 Worker |
| VerifyAgent | `src/worker_agents/verify_agent.py` | 数据审核 Worker |

### 3.2 修改模块

| 模块 | 说明 |
|------|------|
| `src/tools/delegate_tool.py` | ThreadPoolExecutor 并行执行同批任务；`_create_agent` 支持 4 个新 Worker；Worker 超时/重试（读取 multi_agent 配置） |
| `src/api_service.py` | AgentRegistry 注册 4 个新 Worker 能力描述（仅注册元数据，不改执行链路） |

### 3.3 不修改模块

| 模块 | 说明 |
|------|------|
| `src/agent_core.py` | ReActAgent 不变 |
| `src/agent_registry.py` / `src/shared_memory.py` | 阶段二已实现，接口不变 |
| `src/orchestrator_agent.py` | 不变（Orchestrator 通过 delegate 自主决策） |
| 4 个工具文件 | calculator/compare/chart/verify 工具不变 |
| `src/worker_tool_factory.py` / `src/step_callback.py` | 阶段一已实现，复用 |
| `config/agent_prompts.yaml` | 4 个 Worker 模板节已在步骤 0.2 定义，不变 |
| `config/agent_config.json` | models 配置已在步骤 0.1 定义，不变 |
| `src/planner.py` / `src/router.py` | 不变 |
| 前端 / 部署脚本 | 不变 |

## 4. 前置依赖

- 步骤 0.1: ReActAgent 支持 llm_provider/prompt_name/temperature/model；AgentResult 含 sources/total_tokens
- 步骤 0.2: agent_prompts.yaml 含 calc_agent/compare_agent/chart_agent/verify_agent 节
- 步骤 0.3: 三层路由已标记 multi_agent 模式
- 步骤 1.1: DataAgent 模式确立（Worker 继承 ReActAgent 的范式）
- 步骤 2.1~2.4: AgentRegistry/SharedMemory/DelegateTool/OrchestratorAgent 已就绪

## 5. 关联风险

| 风险 | 等级 | 缓解 |
|------|:--:|------|
| ThreadPool 并行时 DashScope SDK 线程安全 | 中 | 每次 Generation.call() 为独立 HTTP 调用，无共享状态；TDD 加并行调用测试验证 |
| ChartTool/VerifyTool 不自行检索，需要输入注入 | 高 | DelegateTool 已通过 shared_context 参数向 Worker 注入 SharedMemory 上下文（阶段二已实现） |
| CompareTool 内部独立创建 HybridRetriever | 中 | CompareAgent 优先从 SharedMemory 获取数据，避免重复加载向量库 |
| Worker 整体执行超时 | 中 | multi_agent 配置已有 worker_timeout（30s）/worker_max_retries（1），并行批次用 future.result(timeout=) 控制 |
| 同批任务并行写 SharedMemory 竞态 | 低 | add_agent_result 已用 threading.Lock 保护（阶段二已实现） |

## 6. 验证策略

- TDD: 新增 30 项测试（3.1 并行 7 项 + 3.2~3.5 各 5 项 + 3.6 收尾 3 项），先标红后转绿
- 回归: 阶段二 28 项 + 现有 126 项测试全部通过
- 性能: 同批 3 个 Mock Worker 并行执行耗时显著低于串行（TDD 断言）
