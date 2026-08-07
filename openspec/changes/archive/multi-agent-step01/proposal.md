# 变更提案: 多 Agent 升级 - 步骤 0.1 基础能力搭建

> 编码: UTF-8
> 状态: 实施中
> 日期: 2026-08-06

---

## 1. 变更背景

当前系统是单 Agent 架构（ReActAgent），所有推理、检索、计算、对比、图表、验证都由同一个 Agent 完成。在多 Agent 升级方案中，需要将系统升级为 Orchestrator + Worker 架构，每个 Worker 专注特定职责（DataAgent、CalcAgent 等）。

步骤 0.1 是多 Agent 升级的第一步，目标是为后续多 Agent 架构搭建基础能力，重点解决 7 项高危风险和 8 项中危风险。

---

## 2. 变更目标

| 目标 | 衡量标准 |
|------|---------|
| LLM 调用解耦 | 新增 LLMProvider 抽象层，ReActAgent 支持双路径调用 |
| AgentResult 扩展 | 新增 sources/total_tokens/reflection 字段 |
| Prompt 外部化 | 支持 prompt_name 参数，从 YAML 加载模板 |
| 步骤回调机制 | 新增 StepCallback，线程安全推送 Worker 事件 |
| 工具实例工厂 | 新增 WorkerToolFactory，按需创建 ToolRegistry |
| 向后兼容 | 不传 llm_provider 时行为与升级前一致 |

---

## 3. 变更范围

### 3.1 新增模块

| 模块 | 文件名 | 职责 |
|------|--------|------|
| LLM Provider | `src/llm_provider.py` | LLM 调用抽象层，支持 DashScope/OpenAI 兼容 |
| 步骤回调 | `src/step_callback.py` | Worker 步骤事件推送，线程安全 |
| 工具工厂 | `src/worker_tool_factory.py` | 为 Worker 创建独立的 ToolRegistry |

### 3.2 修改模块

| 模块 | 文件 | 修改内容 |
|------|------|---------|
| Agent 核心 | `src/agent_core.py` | AgentResult 扩展 + __init__ 新参数 + _build_system_prompt 升级 + _call_llm 双路径 + sources 收集 |
| API 服务 | `src/api_service.py` | LLMProvider 初始化 + _create_per_request_agent 新参数 |
| 检索工具 | `src/tools/retrieve_tool.py` | _get_retriever 线程安全（double-check lock） |
| Agent 配置 | `config/agent_config.json` | 新增 models 和 multi_agent 配置节 |

### 3.3 保留不变

- `src/agent_memory.py` - Agent 记忆系统
- `src/planner.py` - 任务规划器
- `src/reflector.py` - 反思模块
- `src/retrieval.py` - 混合检索
- 全部前端代码
- 全部 `data/` 文件

---

## 4. 技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| Prompt 模板引擎 | string.Template | 避免 str.format() 花括号转义问题（M-44） |
| 队列类型 | queue.Queue | asyncio.Queue 非线程安全，Worker 在 ThreadPool 运行（R-07） |
| LLM 双路径 | 有 provider 走 provider，无则走原有 dashscope | 完全向后兼容（R-02） |
| 工具实例策略 | 共享实例 | 所有工具无状态或并行安全，避免向量库重复加载（M-45） |
| yaml import | try/except 保护 | PyYAML 未安装时不影响其他功能 |

---

## 5. 风险与缓解

| 风险编号 | 风险 | 级别 | 缓解措施 |
|---------|------|:--:|---------|
| R-01 | AgentResult 缺少 sources 字段 | 高 | 新增 sources: List[Dict] 字段 |
| R-02 | __init__ 不接受 llm_provider | 高 | 新增 llm_provider 可选参数，双路径调用 |
| R-04 | shared_context 参数未传递 | 高 | run()/run_stream() 签名新增 shared_context |
| R-05 | shared_context 未加入 run() 签名 | 高 | 同 R-04 |
| R-06 | Worker 步骤无法 yield 到外层 SSE | 高 | 新增 StepCallback 机制 |
| R-07 | asyncio.Queue 非线程安全 | 高 | 使用 queue.Queue |
| R-43 | 并发 RetrieveTool 初始化竞态 | 高 | double-check locking |
| M-35 | prompt_name 参数缺失 | 中 | 新增 prompt_name 参数 |
| M-36 | agent_descriptions 模板变量 | 中 | _build_system_prompt 新增参数 |
| M-39 | sources 类型不匹配 | 中 | 在 R-01 中一并解决 |
| M-41 | reflection 属性不存在 | 中 | 新增 reflection 字段 |
| M-44 | str.format() 花括号隐患 | 中 | 改用 string.Template |
| M-45 | Worker 工具实例策略 | 中 | 新增 WorkerToolFactory |
| M-46 | retrieve 结果到 sources 映射 | 中 | _execute_action 中收集 |

---

## 6. 受影响的规范

- `openspec/changes/rag-to-agent/` - Agent 核心能力继承
- `openspec/changes/p0-critical-fixes/` - 并发安全修复

---

## 7. 前置文档

- [多Agent升级方案](_local/blog/Agent项目/多Agent升级/多Agent升级方案.md)
- [风险规避清单](_local/blog/Agent项目/多Agent升级/风险规避清单.md)
- [步骤0.1详细代码实现方案](_local/blog/Agent项目/多Agent升级/步骤0.1_详细代码实现方案.md)
