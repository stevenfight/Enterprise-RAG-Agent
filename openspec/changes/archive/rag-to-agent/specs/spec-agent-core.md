# Spec: Agent 核心 (ReAct 循环控制器)

> 编码: UTF-8 | 变更: rag-to-agent

---

## 概述

`src/agent_core.py` 是 Agent 系统的核心控制器，负责 ReAct（Reasoning + Acting）主循环。

---

## Requirement: ReAct 自主推理循环

Agent SHALL 支持多步推理与行动，通过 Thought → Action → Observation 循环完成复杂查询。

### Scenario: 单步检索完成简单查询
- **WHEN** 用户查询为"中芯国际2024年营收是多少"
- **AND** 配置 max_steps=5
- **THEN** Agent 在第一步调用 retrieve 工具后获得所需数据
- **AND** Agent 判定信息充分，输出 Final Answer
- **AND** 总步数 ≤ 2

### Scenario: 多步推理完成复合查询
- **WHEN** 用户查询为"中国移动和中国联通2024年营收增长率对比"
- **THEN** Agent 至少执行以下步骤：
  1. retrieve 获取中国移动营收数据
  2. retrieve 获取中国联通营收数据
  3. calculate 计算各自的同比增长率
  4. compare 生成对比结果
- **AND** 最终答案包含两家公司的营收数据和增长率对比

### Scenario: 超出最大步数强制停止
- **WHEN** 用户查询复杂，Agent 已执行 max_steps 步
- **AND** 仍未输出 Final Answer
- **THEN** Agent 强制输出当前收集到的最佳答案
- **AND** 日志记录"达到最大步数限制，强制终止"

---

## Requirement: 统一的 Thought/Action/Observation 模型

Agent 每一轮循环 SHALL 遵循标准的 Thought/Action/Observation 模式。

### Scenario: Thought 解析
- **WHEN** LLM 返回包含 "Thought:" 和 "Action:" 的响应
- **THEN** Agent 正确解析出 thought_text 和 action
- **AND** action 包含 name（工具名）和 input（参数字典）

### Scenario: Final Answer 识别
- **WHEN** LLM 返回包含 "Final Answer:" 的响应
- **THEN** Agent 不再调用工具，进入答案生成阶段
- **AND** 解析出 final_answer 文本

### Scenario: LLM 返回格式异常
- **WHEN** LLM 返回无法解析的格式（缺少 Thought/Action/Final Answer）
- **THEN** Agent 记录错误日志
- **AND** 重试 1 次（告知 LLM 格式要求）
- **AND** 重试仍失败则回退到管道模式

---

## Requirement: 工具调用与结果处理

Agent SHALL 通过 ToolRegistry 调度工具，并正确处理成功和失败结果。

### Scenario: 工具执行成功
- **WHEN** Action 指定工具 "retrieve" 且参数有效
- **THEN** ToolRegistry 找到对应工具并执行
- **AND** Observation 包含 ToolResult(data=检索结果, success=True)

### Scenario: 工具执行失败
- **WHEN** 工具执行抛出异常或返回 success=False
- **THEN** Observation 包含错误信息
- **AND** Agent 将该失败信息纳入下一轮 Thought
- **AND** Agent 不因单个工具失败而终止

### Scenario: 工具不存在
- **WHEN** Action 指定一个未注册的工具名
- **THEN** 返回错误 Observation
- **AND** Agent 在下一轮中选择其他可用工具

---

## Requirement: 超时与安全边界

Agent SHALL 设置合理的超时和资源边界。

### Scenario: 单步 LLM 调用超时
- **WHEN** LLM 生成超过 60 秒未返回
- **THEN** 抛出超时异常
- **AND** Agent 记录错误并优雅终止

### Scenario: 工具执行超时
- **WHEN** 单个工具执行超过 30 秒
- **THEN** 中断工具执行
- **AND** Observation 标记为超时错误

---

## Requirement: 推理链记录

Agent SHALL 记录完整的推理链，供调试和界面展示。

### Scenario: 推理链完整性
- **WHEN** Agent 完成一次查询（无论成功或失败）
- **THEN** AgentResult 包含完整的 reasoning_chain 列表
- **AND** 每个元素包含: step_number, thought, action, action_input, observation, elapsed_ms

---

## 配置项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| max_steps | 5 | 最大推理步数 |
| llm_timeout | 60 | LLM 调用超时(秒) |
| tool_timeout | 30 | 工具执行超时(秒) |
| temperature | 0.3 | LLM 温度 |
| max_retries | 1 | 格式异常重试次数 |
