# 架构设计: 多 Agent 升级 - 阶段三 并行 + 其余 Worker + Reflector 接入

> 编码: UTF-8
> 变更: multi-agent-step06
> 日期: 2026-08-07

---

## 1. 架构概览

```
OrchestratorAgent (src/orchestrator_agent.py, 阶段二不变)
  │
  ▼
DelegateTool (src/tools/delegate_tool.py)  ← 本次升级
  │
  ├─ 批次分组: _group_by_dependency(tasks) → [[无依赖批次], [有依赖批次], ...]
  │
  ├─ 同批并行: ThreadPoolExecutor(max_workers=len(batch))
  │     ┌────────────┬────────────┬────────────┐
  │     │ DataAgent  │ CalcAgent  │ ChartAgent │  ← Worker 并行执行
  │     │ (检索)     │ (计算)     │ (图表)     │
  │     └────┬───────┴─────┬──────┴─────┬──────┘
  │          └──────┬──────┴──────┬──────┘
  │                 ▼             ▼
  │     SharedMemory (threading.Lock 保护)
  │       ├── add_agent_result(name, result)
  │       └── get_context_for(name, task) → 下游 Worker 输入
  │
  ├─ Worker 超时: future.result(timeout=worker_timeout) + 重试
  │
  └─ _create_agent(cap)  ← 本次扩展: 支持 DataAgent/CalcAgent/CompareAgent/ChartAgent/VerifyAgent

AgentRegistry (阶段二不变) ← 本次 api_service 注册 5 个 Worker 能力
  ├── DataAgent    (qwen-turbo,  tools=[retrieve])
  ├── CalcAgent    (qwen-plus,   tools=[calculator, retrieve])
  ├── CompareAgent (qwen-max,    tools=[compare, retrieve])
  ├── ChartAgent   (qwen-max,    tools=[chart])
  └── VerifyAgent  (qwen-plus,   tools=[verify, retrieve])

api_service.py ← 本次仅注册元数据（执行链路阶段二已接好，含 Reflector 反思）
```

## 2. 模块设计

### 2.1 DelegateTool 并行升级（步骤 3.1）

**改动原则**：保留阶段二串行逻辑为回退路径，新增并行分支；不改动外部调用签名。

| 新方法 | 职责 |
|------|------|
| `_group_by_dependency(tasks)` | 批次分组：无依赖任务（如多公司检索）进同一批并行；下游任务（如对比）进后续批 |
| `_run_worker_task(task, worker_timeout, max_retries)` | 单任务执行单元：从 task 中获取 agent 名 → 查 Registry 获取 cap → 从 SharedMemory 获取 shared_ctx → 创建 Worker → 执行（含超时/重试）→ 写 SharedMemory → 返回结果 dict |
| `_run_batch_parallel(batch, worker_timeout, max_retries)` | 同批并行执行：ThreadPoolExecutor + future.result(timeout=worker_timeout)；单任务时直接串行调用 _run_worker_task（原设计 _execute_single 已合并至此） |

**并行安全**：
- SharedMemory.add_agent_result 已用 threading.Lock 保护（阶段二）
- DashScope SDK 每次调用独立 HTTP 请求，线程安全（TDD 验证）
- 每批并行结束后才进入下一批，保证下游 Worker 读到完整上游数据

**超时与重试**：从 `agent_config.json` 的 multi_agent 节读取：
- `worker_timeout=30`（秒）：`future.result(timeout=)` 控制单 Worker 整体超时
- `worker_max_retries=1`：超时/异常后重试次数
- `continue_on_worker_failure=true`：单 Worker 失败不影响整批其他 Worker

**批次依赖判断**（第一版实现简化）：
- 仅依据 `agent` 类型分组：DataAgent/CalcAgent 检索类任务视为无依赖 → 同批并行
- CompareAgent/ChartAgent/VerifyAgent 视为下游 → 单批（等上游数据写入后再执行）
- 拓扑排序完整算法按方案标注"可选复用 planner._build_execution_order"，当前不引入复杂依赖图

### 2.2 四个新 Worker（步骤 3.2~3.5）

统一范式（与 DataAgent 一致）：

```python
class CalcAgent(ReActAgent):
    def __init__(self, calculator_tool, retrieval_tool, llm_provider=None):
        registry = ToolRegistry()
        registry.register(calculator_tool)
        registry.register(retrieval_tool)
        super().__init__(
            tool_registry=registry,
            llm_provider=llm_provider,
            prompt_name="calc_agent",   # agent_prompts.yaml 对应节
            max_steps=5,                # 计算/对比/图表/审核任务 2-5 步
            temperature=0.1,            # 计算类需稳定输出
            model="qwen-plus",          # agent_config.json models.calc
        )
```

| Agent | prompt_name | 工具 | 模型 | 温度 | max_steps | 输入来源 |
|------|:--:|------|:--:|:--:|:--:|------|
| CalcAgent | `calc_agent` | calculator + retrieve | qwen-plus | 0.1 | 5 | SharedMemory 上游数值（shared_context 注入） |
| CompareAgent | `compare_agent` | compare + retrieve | qwen-max | 0.3 | 5 | SharedMemory 上游数据，优先直接对比 |
| ChartAgent | `chart_agent` | chart | qwen-max | 0.3 | 5 | SharedMemory 结构化数据（提取 data 字典） |
| VerifyAgent | `verify_agent` | verify + retrieve | qwen-plus | 0.1 | 5 | SharedMemory 待验证陈述 + 来源 |

**shared_context 注入链路**（阶段二已打通，本阶段直接受益）：
```
DelegateTool.run()
  → shared_ctx = shared_memory.get_context_for(agent_name, task)
  → worker.run(query=sub_task, company_name=company, shared_context=shared_ctx)
    → ReActAgent._build_system_prompt(shared_context=shared_ctx)
      → string.Template 替换模板中 $shared_context 占位符
```

**ChartAgent 关键点**：只持有 chart 工具，Prompt（chart_agent 节）已指示"从 {shared_context} 中提取结构化数值，构造 chart 工具所需 data 参数"。数据来源为上游 DataAgent 结果（answer 文本 + sources）。

**VerifyAgent 关键点**：持有 verify + retrieve。claim 从 SharedMemory 获取（Orchestrator 陈述），source_text 由 retrieve 检索获得，或直接用上游来源文本。

**CompareAgent 关键点**：持有 compare + retrieve。SharedMemory 有充足上游数据时，CompareAgent 直接基于 shared_context 对比（不触发 CompareTool 内部重新检索）；数据不足时才调用 compare 工具（其内部已复用 retriever 延迟加载）。

### 2.3 DelegateTool._create_agent 扩展

```python
def _create_agent(self, cap, step_callback=None):
    from src.worker_agents.data_agent import DataAgent
    from src.worker_agents.calc_agent import CalcAgent
    from src.worker_agents.compare_agent import CompareAgent
    from src.worker_agents.chart_agent import ChartAgent
    from src.worker_agents.verify_agent import VerifyAgent
    from src.tools.retrieve_tool import RetrieveTool
    from src.tools.calculator_tool import CalculatorTool
    from src.tools.compare_tool import CompareTool
    from src.tools.chart_tool import ChartTool
    from src.tools.verify_tool import VerifyTool

    if cap.name == "DataAgent":
        return DataAgent(retrieval_tool=RetrieveTool())
    if cap.name == "CalcAgent":
        return CalcAgent(calculator_tool=CalculatorTool(), retrieval_tool=RetrieveTool())
    if cap.name == "CompareAgent":
        return CompareAgent(compare_tool=CompareTool(), retrieval_tool=RetrieveTool())
    if cap.name == "ChartAgent":
        return ChartAgent(chart_tool=ChartTool())
    if cap.name == "VerifyAgent":
        return VerifyAgent(verify_tool=VerifyTool(), retrieval_tool=RetrieveTool())
    logger.warning("[DelegateTool] 不支持的 Agent 类型: %s", cap.name)
    return None
```

### 2.4 api_service 注册（步骤 3.2~3.5 收尾）

`_init_globals()` 中 AgentRegistry 追加注册 4 个新 Worker（仅元数据，执行链路阶段二已接好）：

```python
agent_registry.register(AgentCapability(
    name="CalcAgent",
    description="财务计算专家：执行增长率/CAGR/利润率计算，输入来自上游数据",
    tools=["calculator", "retrieve"],
    max_parallel=2,
    llm_model="qwen-plus",
))
agent_registry.register(AgentCapability(name="CompareAgent", ...))
agent_registry.register(AgentCapability(name="ChartAgent", ...))
agent_registry.register(AgentCapability(name="VerifyAgent", ...))
```

Orchestrator 的 `_agent_descriptions` 随之自动包含 5 个 Worker 的能力描述（阶段二已实现动态注入）。

### 2.5 Reflector 接入（步骤 3.6，阶段二已提前完成）

阶段二 api_service 的 POST/SSE multi_agent 分支已实现：
- Orchestrator 输出答案后，调用 `reflector.verify(result.answer, shared_memory.get_all_sources(), query)`
- 有 corrected_answer 时覆盖结果，`result.reflection` 填充反思信息

本阶段仅补充 3 项收尾 TDD 验证，不改动 reflector.py。

## 3. 数据流示例（并行）

```
用户查询 "三大运营商2024年营收对比"
  → OrchestratorAgent
    → Action: delegate {"tasks": [
        {"agent": "DataAgent", "task": "中国移动2024年营收", "company_name": "中国移动"},
        {"agent": "DataAgent", "task": "中国联通2024年营收", "company_name": "中国联通"},
        {"agent": "DataAgent", "task": "中国电信2024年营收", "company_name": "中国电信"},
      ]}
    → DelegateTool.run()
      → _group_by_dependency → 批次1 = 3 个 DataAgent（无依赖）
      → ThreadPoolExecutor(3) 并行执行（~3s，原串行 ~8s）
      → 每完成一个 → SharedMemory.add_agent_result("DataAgent(中国移动)", result)
    → Observation: 委托执行完成: 3 个子任务
    → Action: delegate {"tasks": [
        {"agent": "CompareAgent", "task": "对比三家公司2024年营收", "company_name": ""},
      ]}
      → 批次2 = CompareAgent（依赖批次1，读到完整 shared_context）
      → 基于 shared_context 直接输出 Markdown 对比表
    → Final Answer: 2024年三大运营商营收对比表...
  → api_service: Reflector 反思（get_all_sources 聚合来源）
```

## 4. 接口变更汇总

| 文件 | 变更 | 兼容性 |
|------|------|:--:|
| `delegate_tool.py` | 新增 `_group_by_dependency`/`_run_batch_parallel`/`_run_worker_task`；`_create_agent` 扩展 | run(tasks, **kwargs) 签名不变 |
| `worker_agents/calc_agent.py` | 新增 | - |
| `worker_agents/compare_agent.py` | 新增 | - |
| `worker_agents/chart_agent.py` | 新增 | - |
| `worker_agents/verify_agent.py` | 新增 | - |
| `api_service.py` | _init_globals 注册 4 个 Worker 元数据 | 执行链路不变 |

## 5. 技术决策

| 决策 | 理由 |
|------|------|
| 并行批次按 agent 类型分组，不引入复杂依赖图 | 当前任务模型简单（检索类可并行、分析类下游依赖），避免过度设计；方案标注拓扑排序为可选 |
| 每批内 ThreadPoolExecutor(max_workers=len(batch)) | 同批任务数量即最大并行度，避免资源浪费 |
| Worker 超时用 future.result(timeout=) | ThreadPoolExecutor 天然支持超时，无需额外 watchdog 线程 |
| 4 个 Worker 独立文件、复用 DataAgent 范式 | 每个 ~40 行，结构与 DataAgent 一致，可读性/可测性最佳 |
| api_service 仅注册元数据 | 执行链路（POST/SSE multi_agent 分支）阶段二已完整实现，遵循最小变更原则 |
| Reflector 接入不改 reflector.py | 阶段二已按方案完成接入，本阶段仅验证 |
