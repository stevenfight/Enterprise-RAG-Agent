# 技术设计：统一 API 会话记忆创建入口

## 统一辅助函数

在 `src/api_service.py` 增加 `_get_or_create_conversation_memory(conversation_id)`：

1. 调用已有 `_ensure_conversation` 获取会话管理器。
2. 如果会话已有 `agent_memory`，直接复用，避免同一会话重复创建。
3. 如果没有，则从 `_shared_state["ag_cfg"]` 读取 memory 配置。
4. 创建 `AgentMemory` 时传入三个配置参数和 `session_id=conversation_id`。
5. 绑定到 `ConversationManager` 并返回会话管理器与记忆实例。

## API 迁移范围

替换以下四处直接 `cm.link_memory(AgentMemory())`：

- `/api/agent/query`
- `/api/agent/stream`
- LangBot 兼容接口
- OpenAI 兼容接口

所有入口继续保留各自的 Agent 创建、路由、流式响应和错误处理逻辑。

## 配置来源

优先使用启动阶段已经保存的 `_shared_state["ag_cfg"]`，避免每个请求重新读取配置文件。缺失字段使用 `AgentMemory` 当前默认值，确保内部测试和未初始化场景不改变既有行为。
