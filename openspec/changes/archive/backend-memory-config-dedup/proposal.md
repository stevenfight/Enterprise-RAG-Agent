# 变更提案：统一 API 会话记忆创建入口

## 背景

API 层的普通查询、SSE、LangBot 兼容接口和 OpenAI 兼容接口都在首次创建会话时直接调用 `AgentMemory()`。这些调用没有传入 `agent_config.json` 的 memory 配置，也没有传入会话标识，导致系统状态显示和实际运行状态不一致。

## 目标

- 建立统一的 API 会话记忆创建与绑定入口。
- 让所有 API 入口使用相同的 `working_memory_limit`、`episodic_memory_turns`、`enable_long_term` 配置。
- 使用 `conversation_id` 作为当前 API 会话的持久化 `session_id`，保证相同会话可恢复、不同会话隔离。
- 保持现有接口、响应结构、路由和 Agent 执行逻辑不变。

## 非目标

- 不修改 Streamlit 独立入口。
- 不修改 `AgentMemory` 内部数据结构和持久化格式。
- 不处理配置文件读取器与 `orchestrator_agent.py` 的重复问题。
- 不处理 `max_steps=100` 的独立 500 问题。
