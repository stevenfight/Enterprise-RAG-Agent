# Spec: 步骤 0.1 多 Agent 基础能力搭建

> 编码: UTF-8 | 变更: multi-agent-step01

---

## 概述

本文档定义步骤 0.1 的所有需求规格，涵盖 LLMProvider 抽象层、StepCallback 机制、WorkerToolFactory、ReActAgent 扩展、retrieve_tool 线程安全和 agent_config 扩展。

---

## Requirement: LLMProvider 抽象层 (R-02)

系统 SHALL 提供 LLMProvider 抽象层，将 LLM 调用从 ReActAgent 中解耦，支持多模型切换。

### Scenario: DashScopeProvider 成功调用
- **WHEN** 创建 DashScopeProvider 并调用 chat()
- **AND** DashScope 返回 status_code=200
- **THEN** 返回 LLMResponse(success=True)
- **AND** content 字段包含 LLM 生成文本
- **AND** usage 字段包含 input_tokens 和 output_tokens

### Scenario: DashScopeProvider 调用失败
- **WHEN** DashScope 返回 status_code != 200
- **THEN** 返回 LLMResponse(success=False)
- **AND** error 字段包含状态码和错误信息

### Scenario: DashScopeProvider 超时
- **WHEN** LLM 调用抛出 TimeoutError
- **THEN** 返回 LLMResponse(success=False)
- **AND** error 字段包含超时提示

### Scenario: BaseLLMProvider 子类未实现 chat
- **WHEN** 直接实例化 BaseLLMProvider 并调用 chat
- **THEN** 抛出 NotImplementedError

---

## Requirement: AgentResult 字段扩展 (R-01, R-39, M-41)

AgentResult SHALL 新增 sources、total_tokens、reflection 三个字段。

### Scenario: sources 字段默认值
- **WHEN** 创建 AgentResult 不传 sources
- **THEN** sources 为空列表

### Scenario: total_tokens 默认值
- **WHEN** 创建 AgentResult 不传 total_tokens
- **THEN** total_tokens 为 0

### Scenario: reflection 默认值
- **WHEN** 创建 AgentResult 不传 reflection
- **THEN** reflection 为 None

---

## Requirement: ReActAgent.__init__ 新增参数 (R-02, M-35, R-06)

ReActAgent.__init__ SHALL 新增 llm_provider、prompt_name、step_callback 三个可选参数。

### Scenario: 不传新参数（向后兼容）
- **WHEN** 使用原有参数构造 ReActAgent
- **THEN** llm_provider 为 None
- **AND** prompt_name 为 "default"
- **AND** step_callback 为 None
- **AND** Agent 行为与升级前一致

### Scenario: 传入 llm_provider
- **WHEN** 构造 ReActAgent 时传入 llm_provider 实例
- **THEN** self.llm_provider 被保存
- **AND** _call_llm 走 provider 路径

### Scenario: 传入 prompt_name
- **WHEN** 构造 ReActAgent 时传入 prompt_name="data_agent"
- **THEN** self._prompt_name 为 "data_agent"
- **AND** _load_prompt_template 尝试从 YAML 加载 data_agent 节

### Scenario: 传入 step_callback
- **WHEN** 构造 ReActAgent 时传入 step_callback 实例
- **THEN** self._step_callback 被保存

---

## Requirement: _call_llm 双路径 (R-02)

_call_llm SHALL 支持双路径：有 llm_provider 走 provider.chat()，无则走原有 dashscope.Generation.call()。

### Scenario: 有 provider 成功路径
- **WHEN** self.llm_provider 不为 None
- **AND** provider.chat() 返回 success=True
- **THEN** 返回 content 字符串
- **AND** self._total_tokens 累加 input+output tokens

### Scenario: 有 provider 失败路径
- **WHEN** self.llm_provider 不为 None
- **AND** provider.chat() 返回 success=False
- **THEN** 返回 None
- **AND** 记录错误日志

### Scenario: 无 provider 走原有路径
- **WHEN** self.llm_provider 为 None
- **THEN** 调用 Generation.call()
- **AND** 行为与升级前一致
- **AND** 成功时累加 _total_tokens

---

## Requirement: _build_system_prompt 升级 (R-04, R-05, M-36, M-44)

_build_system_prompt SHALL 使用 string.Template，新增 shared_context 和 agent_descriptions 参数。

### Scenario: 使用 string.Template 替换
- **WHEN** 模板包含 $tool_descriptions 和 $context
- **THEN** 使用 Template.safe_substitute 替换变量
- **AND** 不因花括号 JSON 内容报错

### Scenario: shared_context 注入
- **WHEN** 传入 shared_context="上游数据..."
- **THEN** 模板中 $shared_context 被替换为实际文本

### Scenario: shared_context 为空
- **WHEN** 不传 shared_context
- **THEN** $shared_context 被替换为空字符串

### Scenario: YAML 模板加载
- **WHEN** prompt_name="data_agent" 且 agent_prompts.yaml 存在
- **THEN** 加载 data_agent 节的 template
- **AND** 返回该模板字符串

### Scenario: YAML 不存在回退
- **WHEN** agent_prompts.yaml 不存在
- **THEN** 回退到 _default_system_prompt
- **AND** 记录日志"使用硬编码默认模板"

---

## Requirement: run()/run_stream() 签名扩展 (R-04, R-05)

run() 和 run_stream() SHALL 新增 shared_context 参数，并在返回的 AgentResult 中填充 sources 和 total_tokens。

### Scenario: run() 传入 shared_context
- **WHEN** 调用 agent.run(query, shared_context="上游数据")
- **THEN** _build_system_prompt 接收到 shared_context
- **AND** System Prompt 包含上游数据

### Scenario: run() 重置 sources 和 tokens
- **WHEN** 调用 run()
- **THEN** self._sources 被重置为空列表
- **AND** self._total_tokens 被重置为 0

### Scenario: AgentResult 填充 sources
- **WHEN** run() 返回 AgentResult
- **THEN** result.sources 包含检索来源
- **AND** result.total_tokens 包含累计 Token 用量

### Scenario: run_stream() 同 run()
- **WHEN** 调用 run_stream(query, shared_context="...")
- **THEN** 行为与 run() 一致

---

## Requirement: sources 收集 (R-01, M-46)

_execute_action SHALL 在 retrieve 工具成功时收集 sources 信息。

### Scenario: retrieve 成功收集 sources
- **WHEN** action="retrieve" 且 result.success=True
- **AND** result.data 是字典且包含 results 列表
- **THEN** self._sources 追加来源信息
- **AND** 每条来源包含 source/content/pages/company_name

### Scenario: 非 retrieve 工具不收集
- **WHEN** action="calculator"
- **THEN** self._sources 不变

### Scenario: retrieve 失败不收集
- **WHEN** action="retrieve" 且 result.success=False
- **THEN** self._sources 不变

---

## Requirement: StepCallback 机制 (R-06, R-07)

StepCallback SHALL 使用 queue.Queue 线程安全推送 Worker 步骤事件。

### Scenario: on_step 推送事件
- **WHEN** 调用 callback.on_step("thought", 1, "内容")
- **THEN** event_queue 中出现 worker_step 事件
- **AND** 事件包含 agent/step_type/step/content/timestamp

### Scenario: on_done 推送完成事件
- **WHEN** 调用 callback.on_done(result)
- **THEN** event_queue 中出现 worker_done 事件
- **AND** 事件包含 success/total_steps/total_elapsed_ms

### Scenario: 多线程并行推送
- **WHEN** 3 个线程同时调用 on_step
- **THEN** 所有事件都被推入队列
- **AND** 无事件丢失

### Scenario: 内容超长截断
- **WHEN** on_step 的 content 超过 500 字符
- **THEN** 事件中 content 被截断为 500 字符

---

## Requirement: WorkerToolFactory (M-45)

WorkerToolFactory SHALL 从共享工具实例创建独立的 ToolRegistry。

### Scenario: 创建含指定工具的 Registry
- **WHEN** 调用 factory.create_registry(["retrieve", "calculator"])
- **THEN** 返回 ToolRegistry 实例
- **AND** registry.list_all() 包含 retrieve 和 calculator

### Scenario: 请求不存在的工具
- **WHEN** 调用 factory.create_registry(["unknown_tool"])
- **THEN** 跳过该工具
- **AND** 记录 WARNING 日志
- **AND** 返回空 ToolRegistry

### Scenario: 共享实例复用
- **WHEN** 两次调用 create_registry(["retrieve"])
- **THEN** 两次返回的 Registry 中的 retrieve 工具是同一实例

---

## Requirement: RetrieveTool 线程安全 (R-43)

RetrieveTool._get_retriever SHALL 使用 double-check locking 保证多线程首次调用只加载一次向量库。

### Scenario: 多线程首次调用
- **WHEN** 3 个线程同时首次调用 _get_retriever
- **THEN** HybridRetriever 只被实例化一次
- **AND** 3 个线程获得同一实例

### Scenario: 单线程多次调用
- **WHEN** 同一线程多次调用 _get_retriever
- **THEN** 只在第一次实例化 HybridRetriever

---

## Requirement: agent_config.json 扩展 (R-02)

config/agent_config.json SHALL 新增 models 和 multi_agent 配置节。

### Scenario: models 配置加载
- **WHEN** _load_agent_config 读取 agent_config.json
- **THEN** result["models"] 包含 orchestrator/data/calc/compare/chart/verify/router 的模型分配

### Scenario: multi_agent 配置加载
- **WHEN** _load_agent_config 读取 agent_config.json
- **THEN** result["multi_agent"] 包含 worker_max_retries/worker_timeout/continue_on_worker_failure

### Scenario: models 缺失回退
- **WHEN** agent_config.json 中没有 models 节
- **THEN** result["models"] 为空字典
- **AND** 不影响其他配置加载

---

## Requirement: api_service 集成 LLMProvider (R-02)

api_service SHALL 在 _init_globals 中初始化 DashScopeProvider 并传递给 Agent。

### Scenario: 全局 LLMProvider 初始化
- **WHEN** _init_globals 执行
- **THEN** _shared_state["llm_provider"] 为 DashScopeProvider 实例

### Scenario: _create_per_request_agent 传递 provider
- **WHEN** 调用 _create_per_request_agent
- **THEN** 创建的 ReActAgent 的 llm_provider 为全局 provider

### Scenario: _create_per_request_agent 向后兼容
- **WHEN** 调用 _create_per_request_agent 不传 llm_provider
- **THEN** 创建的 ReActAgent 的 llm_provider 为 None

---

## 配置项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| models.orchestrator | qwen-max | 编排 Agent 模型 |
| models.data | qwen-turbo | 数据 Agent 模型 |
| models.calc | qwen-plus | 计算 Agent 模型 |
| models.compare | qwen-max | 对比 Agent 模型 |
| models.chart | qwen-max | 图表 Agent 模型 |
| models.verify | qwen-plus | 验证 Agent 模型 |
| models.router | qwen-turbo | 小模型路由模型 |
| multi_agent.worker_max_retries | 1 | Worker 最大重试次数 |
| multi_agent.worker_timeout | 30 | Worker 超时秒数 |
| multi_agent.orchestrator_timeout | 120 | 编排 Agent 超时秒数 |
| multi_agent.continue_on_worker_failure | true | Worker 失败是否继续 |
