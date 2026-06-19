# -*- coding: utf-8 -*-
"""
对话管理器

管理用户-助手的原始对话历史，支持可选 AgentMemory 关联。

扩展功能 (阶段五):
  - 关联 AgentMemory，实现对话历史 + 三层记忆的统一上下文
  - 推理链关联存储：每条助手消息可附带 Agent 推理步骤
  - 向后兼容：不传 agent_memory 时行为与旧版完全一致
"""

from typing import Any, Dict, List, Optional


class ConversationManager:
    """对话历史管理器

    扩展后支持:
      - 可选的 AgentMemory 关联
      - 推理链 (reasoning_chain) 随消息存储
      - get_full_context() 组合对话历史 + AgentMemory 上下文
    """

    def __init__(self, max_turns: int = 5, agent_memory: Any = None):
        """初始化对话管理器

        Args:
            max_turns: 保留的对话轮数上限 (每轮 = 1 user + 1 assistant)
            agent_memory: 可选的 AgentMemory 实例，传入后启用记忆增强功能
        """
        self.messages: List[Dict[str, Any]] = []
        self.max_turns = max_turns
        self.agent_memory = agent_memory

    # ============================================================
    # 原有方法 (保持不变)
    # ============================================================

    def add_message(self, role: str, content: str) -> None:
        """添加一条对话消息 (原有接口不变)

        Args:
            role: "user" 或 "assistant"
            content: 消息文本
        """
        self.messages.append({"role": role, "content": content})
        # 截断存储: 超过 max_turns*4 时移除最早消息, 防止内存无限增长
        self._truncate_if_needed()

    def get_history(self, max_turns: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取最近 N 轮对话历史 (原有接口不变)

        Args:
            max_turns: 返回的对话轮数，默认使用 self.max_turns

        Returns:
            消息列表 (role + content)
        """
        turns = max_turns or self.max_turns
        return self.messages[-turns * 2:]

    def clear(self) -> None:
        """清空所有对话消息 (原有接口不变)"""
        self.messages = []

    def get_context_string(self, max_turns: Optional[int] = None) -> str:
        """生成对话历史的格式化文本 (原有接口不变)

        Args:
            max_turns: 返回的对话轮数

        Returns:
            格式化的对话历史字符串
        """
        history = self.get_history(max_turns)
        if not history:
            return ""
        lines = ["\n对话历史："]
        for msg in history:
            role_label = "用户" if msg["role"] == "user" else "助手"
            content = msg["content"]
            if len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"- {role_label}: {content}")
        return "\n".join(lines)

    # ============================================================
    # 新增方法 (阶段五: Agent 记忆结构扩展)
    # ============================================================

    def link_memory(self, agent_memory: Any) -> None:
        """关联 AgentMemory 实例，启用记忆增强功能

        Args:
            agent_memory: AgentMemory 实例
        """
        self.agent_memory = agent_memory

    def add_agent_message(
        self,
        role: str,
        content: str,
        reasoning_chain: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """添加一条附带推理链的 Agent 消息

        与 add_message 的区别: 支持存储该轮对话对应的 Agent 推理步骤，
        用于后续追溯"这个回答是怎么推理出来的"。

        Args:
            role: "user" 或 "assistant"
            content: 消息文本
            reasoning_chain: 该轮对应的推理步骤列表，每项包含:
                {"step": int, "thought": str, "action": str, "observation": str}
        """
        entry: Dict[str, Any] = {"role": role, "content": content}
        if reasoning_chain is not None:
            entry["reasoning_chain"] = reasoning_chain
        self.messages.append(entry)
        # 截断存储: reasoning_chain 消息同样受截断控制
        self._truncate_if_needed()

    def get_last_reasoning_chain(self) -> Optional[List[Dict[str, Any]]]:
        """获取最近一条包含推理链的消息的推理步骤

        Returns:
            推理步骤列表，没有则返回 None
        """
        for msg in reversed(self.messages):
            if "reasoning_chain" in msg:
                return msg["reasoning_chain"]
        return None

    def get_full_context(self, max_turns: Optional[int] = None) -> str:
        """获取完整上下文：对话历史 + AgentMemory 情景记忆 + 工作记忆

        如果已关联 AgentMemory，则通过 AgentMemory.get_full_context() 组合三层记忆；
        否则退化为纯对话历史。

        Args:
            max_turns: 对话历史保留轮数

        Returns:
            组合后的上下文字符串
        """
        conversation_context = self.get_context_string(max_turns)
        if self.agent_memory:
            return self.agent_memory.get_full_context(conversation_context)
        return conversation_context

    # ============================================================
    # 内部方法
    # ============================================================

    def _truncate_if_needed(self) -> None:
        """截断存储: 超过 max_turns * 4 时移除最早的消息

        保留 max_turns * 4 条消息 (即 max_turns * 2 轮的冗余),
        在保证 get_history 的正常输出窗口的同时防止内存无限增长。
        """
        max_stored = self.max_turns * 4
        while len(self.messages) > max_stored:
            self.messages.pop(0)