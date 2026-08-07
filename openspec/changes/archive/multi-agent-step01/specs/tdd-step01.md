# TDD: 步骤 0.1 多 Agent 基础能力搭建

> 编码: UTF-8 | 变更: multi-agent-step01
>
> 图例: :red_circle: 未通过 | :green_circle: 已通过
>
> 最后验证: 2026-08-06 | 64/64 通过

---

## TC-01: LLMProvider 抽象层

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-01-01 | DashScopeProvider 初始化 | 创建成功，api_key 被保存 | :green_circle: |
| TC-01-02 | BaseLLMProvider.chat 抛出 NotImplementedError | 调用时抛出异常 | :green_circle: |
| TC-01-03 | LLMUsage 默认值 | input_tokens=0, output_tokens=0 | :green_circle: |
| TC-01-04 | LLMResponse 默认值 | content="", success=True, error="", usage=LLMUsage() | :green_circle: |
| TC-01-05 | DashScopeProvider.chat 成功（mock） | 返回 LLMResponse(success=True, content=..., usage=...) | :green_circle: |
| TC-01-06 | DashScopeProvider.chat 失败 status!=200 | 返回 LLMResponse(success=False, error=...) | :green_circle: |
| TC-01-07 | DashScopeProvider.chat 超时 | 返回 LLMResponse(success=False, error="LLM 调用超时") | :green_circle: |
| TC-01-08 | DashScopeProvider.chat 异常 | 返回 LLMResponse(success=False, error="LLM 调用异常: ...") | :green_circle: |
| TC-01-09 | DashScopeProvider 累计调用次数 | 第 2 次调用后 _call_count == 2 | :green_circle: |

---

## TC-02: AgentResult 字段扩展

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-02-01 | AgentResult.sources 默认值 | [] | :green_circle: |
| TC-02-02 | AgentResult.total_tokens 默认值 | 0 | :green_circle: |
| TC-02-03 | AgentResult.reflection 默认值 | None | :green_circle: |
| TC-02-04 | AgentResult 完整构造 | sources=["a"], total_tokens=100, reflection={"ok": True} | :green_circle: |

---

## TC-03: ReActAgent.__init__ 新增参数

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-03-01 | 不传新参数（向后兼容） | llm_provider=None, prompt_name="default", step_callback=None | :green_circle: |
| TC-03-02 | 传入 llm_provider | self.llm_provider 为传入实例 | :green_circle: |
| TC-03-03 | 传入 prompt_name | self._prompt_name 为传入值 | :green_circle: |
| TC-03-04 | 传入 step_callback | self._step_callback 为传入实例 | :green_circle: |
| TC-03-05 | _sources 初始化为空列表 | self._sources == [] | :green_circle: |
| TC-03-06 | _total_tokens 初始化为 0 | self._total_tokens == 0 | :green_circle: |

---

## TC-04: _call_llm 双路径

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-04-01 | 有 provider 成功 | 返回 content 字符串, _total_tokens 累加 | :green_circle: |
| TC-04-02 | 有 provider 失败 | 返回 None, 记录错误日志 | :green_circle: |
| TC-04-03 | 无 provider 走原有路径成功 | 返回 content, _total_tokens 累加 | :green_circle: |
| TC-04-04 | 无 provider 走原有路径失败 | 返回 None | :green_circle: |
| TC-04-05 | 无 provider 走原有路径异常 | 返回 None, 记录异常日志 | :green_circle: |

---

## TC-05: _build_system_prompt 升级

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-05-01 | string.Template 替换变量 | $tool_descriptions 和 $context 被正确替换 | :green_circle: |
| TC-05-02 | 花括号 JSON 安全 | 模板含 {"key": "value"} 不报 KeyError | :green_circle: |
| TC-05-03 | shared_context 注入 | $shared_context 被替换为实际文本 | :green_circle: |
| TC-05-04 | shared_context 为空 | $shared_context 被替换为空字符串 | :green_circle: |
| TC-05-05 | agent_descriptions 注入 | $agent_descriptions 被替换为实际文本 | :green_circle: |
| TC-05-06 | custom_system_prompt 优先级 | 传入自定义模板时使用自定义模板 | :green_circle: |
| TC-05-07 | YAML 模板加载（文件存在） | 加载 YAML 中指定 prompt_name 的模板 | :green_circle: |
| TC-05-08 | YAML 不存在回退 | 回退到 _default_system_prompt | :green_circle: |

---

## TC-06: run()/run_stream() 签名扩展

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-06-01 | run() 传入 shared_context | _build_system_prompt 接收到 shared_context | :green_circle: |
| TC-06-02 | run() 重置 sources | 调用后 self._sources 为空 | :green_circle: |
| TC-06-03 | run() 重置 _total_tokens | 调用后 self._total_tokens 为 0 | :green_circle: |
| TC-06-04 | run() 返回值包含 sources | result.sources 为列表 | :green_circle: |
| TC-06-05 | run() 返回值包含 total_tokens | result.total_tokens >= 0 | :green_circle: |
| TC-06-06 | run_stream() 传入 shared_context | _build_system_prompt 接收到 shared_context | :green_circle: |

---

## TC-07: sources 收集

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-07-01 | retrieve 成功收集 sources | self._sources 追加来源信息 | :green_circle: |
| TC-07-02 | 来源信息包含必要字段 | source/content/pages/company_name | :green_circle: |
| TC-07-03 | 非 retrieve 工具不收集 | self._sources 不变 | :green_circle: |
| TC-07-04 | retrieve 失败不收集 | self._sources 不变 | :green_circle: |
| TC-07-05 | retrieve 返回空 results 不收集 | self._sources 不变 | :green_circle: |

---

## TC-08: StepCallback 机制

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-08-01 | 初始化 | agent_name 和 event_queue 被保存 | :green_circle: |
| TC-08-02 | on_step 推送事件 | event_queue 中出现 worker_step 事件 | :green_circle: |
| TC-08-03 | on_step 事件字段完整 | type/agent/step_type/step/content/timestamp | :green_circle: |
| TC-08-04 | on_done 推送完成事件 | event_queue 中出现 worker_done 事件 | :green_circle: |
| TC-08-05 | on_done 事件字段完整 | type/agent/success/total_steps/total_elapsed_ms/timestamp | :green_circle: |
| TC-08-06 | 内容超 500 字符截断 | 事件 content 长度 <= 500 | :green_circle: |
| TC-08-07 | 多线程并行推送不丢失 | 3 线程各推 3 条，主线程收到 9 条 | :green_circle: |

---

## TC-09: WorkerToolFactory

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-09-01 | 创建含指定工具的 Registry | registry.list_all() 包含请求的工具 | :green_circle: |
| TC-09-02 | 请求不存在的工具 | 跳过，记录 WARNING，返回空 Registry | :green_circle: |
| TC-09-03 | 共享实例复用 | 两次 create_registry 返回的 retrieve 是同一实例 | :green_circle: |
| TC-09-04 | 初始化日志 | 记录共享工具列表 | :green_circle: |

---

## TC-10: RetrieveTool 线程安全

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-10-01 | 多线程首次调用只加载一次 | HybridRetriever 只被实例化一次 | :green_circle: |
| TC-10-02 | _init_lock 存在 | RetrieveTool._init_lock 是 threading.Lock 实例 | :green_circle: |

---

## TC-11: agent_config.json 扩展

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-11-01 | models 配置加载 | result["models"] 包含各角色模型分配 | :green_circle: |
| TC-11-02 | multi_agent 配置加载 | result["multi_agent"] 包含容错配置 | :green_circle: |
| TC-11-03 | models 缺失回退 | result["models"] 为空字典 | :green_circle: |

---

## TC-12: api_service LLMProvider 集成

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-12-01 | _create_per_request_agent 传递 provider | 创建的 Agent 的 llm_provider 不为 None | :green_circle: |
| TC-12-02 | _create_per_request_agent 传 prompt_name | 创建的 Agent 的 _prompt_name == "default" | :green_circle: |

---

## TC-13: 向后兼容性

| 编号 | 测试场景 | 预期结果 | 状态 |
|:--:|------|------|:--:|
| TC-13-01 | 不传 llm_provider 时原有路径可用 | Agent 正常运行，结果与升级前一致 | :green_circle: |
| TC-13-02 | 不传 shared_context 时原有行为不变 | Agent 正常运行 | :green_circle: |
| TC-13-03 | AgentResult 新字段不影响旧代码访问 | answer/success/reasoning_chain 仍可正常访问 | :green_circle: |

---

## 测试统计

| 类别 | 数量 | 通过 | 未通过 |
|------|:--:|:--:|:--:|
| TC-01 LLMProvider | 9 | 9 | 0 |
| TC-02 AgentResult | 4 | 4 | 0 |
| TC-03 __init__ 新参数 | 6 | 6 | 0 |
| TC-04 _call_llm 双路径 | 5 | 5 | 0 |
| TC-05 _build_system_prompt | 8 | 8 | 0 |
| TC-06 run/run_stream 签名 | 6 | 6 | 0 |
| TC-07 sources 收集 | 5 | 5 | 0 |
| TC-08 StepCallback | 7 | 7 | 0 |
| TC-09 WorkerToolFactory | 4 | 4 | 0 |
| TC-10 RetrieveTool 线程安全 | 2 | 2 | 0 |
| TC-11 agent_config | 3 | 3 | 0 |
| TC-12 api_service 集成 | 2 | 2 | 0 |
| TC-13 向后兼容 | 3 | 3 | 0 |
| **总计** | **64** | **64** | **0** |
