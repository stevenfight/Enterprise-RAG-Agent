# Spec: Agent 记忆系统

> 编码: UTF-8 | 变更: rag-to-agent

---

## 概述

`src/agent_memory.py` 实现三层记忆系统：工作记忆（当前任务）、情景记忆（历史会话）、长期记忆（知识积累）。

---

## Requirement: 工作记忆 (Working Memory)

工作记忆 SHALL 存储当前 Agent 任务的每一步 Thought/Action/Observation。

### Scenario: 添加步骤记录
- **WHEN** Agent 完成一个 Thought→Action→Observation 循环
- **THEN** 调用 memory.add(thought, action, observation)
- **AND** 步骤记录追加到工作记忆列表

### Scenario: 工作记忆上下文生成
- **WHEN** 调用 memory.get_working_context()
- **THEN** 返回格式化的文本：
  ```
  步骤 1:
    Thought: ...
    Action: retrieve
    Observation: 找到 5 条结果...
  
  步骤 2:
    Thought: ...
  ```

### Scenario: 工作记忆上限
- **WHEN** 工作记忆超过 10 条记录（config.working_memory_limit）
- **THEN** 自动淘汰最早的记录

### Scenario: 任务开始重置
- **WHEN** 新查询开始，调用 memory.reset_working()
- **THEN** 工作记忆列表清空

---

## Requirement: 情景记忆 (Episodic Memory)

情景记忆 SHALL 存储已完成会话的摘要，支持跨轮对话的上下文关联。

### Scenario: 工作记忆→情景记忆转移
- **WHEN** 当前 Agent 任务完成
- **THEN** 调用 memory.summarize_to_episodic()
- **AND** 工作记忆被压缩为摘要文本
- **AND** 摘要追加到情景记忆列表

### Scenario: 获取历史上下文
- **WHEN** 调用 memory.get_episodic_context(max_turns=3)
- **THEN** 返回最近 3 轮会话的摘要文本
- **AND** 格式为：
  ```
  历史会话 1 (2 步, 工具: retrieve):
  用户问: ...
  Agent 答: ...(前100字)...
  ```

### Scenario: 情景记忆上限
- **WHEN** 情景记忆超过 5 条记录（config.episodic_memory_turns）
- **THEN** 自动淘汰最早的记录

---

## Requirement: 长期记忆 (Long Term Memory)

长期记忆 SHALL 存储可复用的知识，如公司基本信息、财务术语定义。

### Scenario: 长期记忆查询
- **WHEN** Agent 需要获取公司基本背景信息
- **THEN** 调用 memory.get_long_term("company_info", "中芯国际")
- **AND** 返回预设的公司简介文本

### Scenario: 长期记忆可选关闭
- **WHEN** 配置文件 enable_long_term = false
- **THEN** 长期记忆模块不初始化
- **AND** get_long_term() 始终返回 None

---

## Requirement: 对话历史兼容

Agent 记忆系统 SHALL 兼容现有的 ConversationManager 接口。

### Scenario: 与 ConversationManager 互操作
- **WHEN** AgentMemory 和 ConversationManager 同时存在
- **THEN** ConversationManager.get_context_string() 仍可正常工作
- **AND** AgentMemory 不干扰原有对话记忆的读写

---

## 配置项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| working_memory_limit | 10 | 工作记忆最大步数 |
| episodic_memory_turns | 5 | 情景记忆保留轮数 |
| enable_long_term | false | 是否启用长期记忆 |
