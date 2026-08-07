# TDD: 步骤 1.1 DataAgent

> 编码: UTF-8 | 变更: multi-agent-step04
> 
> 状态: 11/16 通过（5 项 skip 因无 API Key）
> 用例数: 16 项
> 核心规则：
> 1. 所有测试优先验证 DataAgent 类定义和参数配置，不验证 ReActAgent 已有逻辑
> 2. TC-40/41 组不需要 API Key（纯类定义和工具注册验证），TC-42 组需要真实 API Key（端到端检索验证）
> 3. 测试用例查询文本均为真实财务查询，匹配 planner 实际分类结果

---

## 一、TC-40: DataAgent 类定义（6 项）

| 编号 | 测试内容 | 分类 | 预期结果 | 状态 |
|------|------|:--:|------|:--:|
| TC-40-01 | DataAgent 是 ReActAgent 的子类 | 继承 | `issubclass(DataAgent, ReActAgent) == True` | :green_circle: |
| TC-40-02 | DataAgent 实例化成功 | 实例化 | `agent = DataAgent(retrieve_tool, provider)` 无异常 | :green_circle: |
| TC-40-03 | DataAgent 的 prompt_name 为 "data_agent" | 配置 | `agent._prompt_name == "data_agent"` | :green_circle: |
| TC-40-04 | DataAgent 的 model 为 "qwen-turbo" | 配置 | `agent.model == "qwen-turbo"` | :green_circle: |
| TC-40-05 | DataAgent 的 max_steps 为 3 | 配置 | `agent.max_steps == 3` | :green_circle: |
| TC-40-06 | DataAgent 的 temperature 为 0.2 | 配置 | `agent.temperature == 0.2` | :green_circle: |

### TC-40 注意说明

- TC-40-01~TC-40-06 均为纯类定义验证，不需要真实 API Key
- TC-40-02 的 `retrieve_tool` 可以用 Mock 对象（只要注册到 ToolRegistry 即可）

---

## 二、TC-41: DataAgent 工具注册（4 项）

| 编号 | 测试内容 | 分类 | 预期结果 | 状态 |
|------|------|:--:|------|:--:|
| TC-41-01 | DataAgent 只注册了 retrieve 工具 | 工具 | `agent.tool_registry.list_all() == ["retrieve"]` | :green_circle: |
| TC-41-02 | DataAgent 的 ToolRegistry 有 retrieve 工具 | 工具 | `agent.tool_registry.get("retrieve")` 非 None | :green_circle: |
| TC-41-03 | DataAgent 的 ToolRegistry 不包含其他工具 | 工具 | chart/compare/calculator/verify 均不在注册表中 | :green_circle: |
| TC-41-04 | DataAgent 实例化时传入 None llm_provider 仍可创建 | 实例化 | `DataAgent(retrieve_tool, llm_provider=None)` 无异常 | :green_circle: |

### TC-41 注意说明

- TC-41-01~TC-41-04 均为纯工具注册验证，不需要真实 API Key
- TC-41-04 验证 llm_provider 可选参数的正确性

---

## 三、TC-42: DataAgent 独立检索验证（6 项，需 API Key）

| 编号 | 测试内容 | 分类 | 预期结果 | 状态 |
|------|------|:--:|------|:--:|
| TC-42-01 | DataAgent 独立检索 "中芯国际2024年营收是多少" | 检索 | `result.success == True` 且 `answer` 非空 | :white_circle: |
| TC-42-02 | DataAgent 检索结果 sources 非空 | 来源 | `len(result.sources) > 0` | :white_circle: |
| TC-42-03 | DataAgent 检索结果 total_tokens > 0 | Token | `result.total_tokens > 0` | :white_circle: |
| TC-42-04 | DataAgent 检索结果 reasoning_chain 非空 | 推理链 | `len(result.reasoning_chain) >= 1` | :white_circle: |
| TC-42-05 | DataAgent 用 prompt_name="data_agent" 构建的 Prompt 不含规则 8 | Prompt | `data_agent` 节模板不含 "图表展示" 关键词 | :green_circle: |
| TC-42-06 | DataAgent 独立检索 "中芯国际2023年营收是多少" 再跑一次 | 检索 | `result.success == True`（验证可重复使用） | :white_circle: |

### TC-42 注意说明

- TC-42-01~TC-42-04、TC-42-06 为端到端检索测试，需要真实 DashScope API Key
- TC-42-05 不需要 API Key，直接验证 YAML 模板内容（已通过）
- TC-42-01~TC-42-04 和 TC-42-06 因无 API Key 标记为 skip（:white_circle:），待有 API Key 时标绿
- TC-42-01 和 TC-42-06 使用不同年份的查询，验证 DataAgent 可重复实例化和使用
