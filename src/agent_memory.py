# -*- coding: utf-8 -*-
"""
Agent 记忆系统

实现三层记忆架构：
  工作记忆 (Working Memory)  - 当前任务的 Thought/Action/Observation 序列
  情景记忆 (Episodic Memory) - 已完成会话的摘要
  长期记忆 (Long Term Memory) - 公司知识 + 跨会话持久化（JSON 文件）

对应 SDD: openspec/changes/rag-to-agent/specs/spec-memory.md
         openspec/changes/long-term-memory-persistence/specs/spec-persistence.md
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_memory")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


class AgentMemory:
    """Agent 三层记忆系统

    Attributes:
        working_memory: 当前任务的步骤记录列表
        episodic_memory: 历史会话摘要列表
        long_term_memory: 长期知识字典
        working_memory_limit: 工作记忆最大步数（默认 10）
        episodic_memory_turns: 情景记忆保留轮数（默认 5）
        enable_long_term: 是否启用长期记忆（默认 False）
        session_id: session 标识，非空时启用 JSON 持久化
        persist_dir: JSON 持久化文件目录
    """

    def __init__(
        self,
        working_memory_limit: int = 10,
        episodic_memory_turns: int = 5,
        enable_long_term: bool = False,
        session_id: str = "",
        persist_dir: str = "data/long_term_memory",
    ):
        """初始化记忆系统

        Args:
            working_memory_limit: 工作记忆保留的最大步数
            episodic_memory_turns: 情景记忆保留的对话轮数
            enable_long_term: 是否启用长期记忆
            session_id: session 标识（如 Streamlit session_id），非空时启用 JSON 持久化
            persist_dir: JSON 持久化文件的存储目录
        """
        self.working_memory: List[Dict[str, Any]] = []
        self.episodic_memory: List[Dict[str, str]] = []
        self.long_term_memory: Dict[str, Dict[str, str]] = {}

        self.working_memory_limit = working_memory_limit
        self.episodic_memory_turns = episodic_memory_turns
        self.enable_long_term = enable_long_term
        self.session_id = session_id
        self.persist_dir = persist_dir

        logger.info("[AgentMemory] 初始化记忆系统: working_limit=%d, episodic_limit=%d, long_term=%s",
                    working_memory_limit, episodic_memory_turns, enable_long_term)

        # 注意: AgentMemory 不是线程安全的。每个 Worker Agent 应持有独立实例。
        if self.enable_long_term:
            self._init_long_term_memory()
            logger.info("[AgentMemory] 长期记忆知识库已初始化，共 %d 个分类",
                        len(self.long_term_memory))
            # 从 JSON 文件加载历史情景记忆
            if self.session_id:
                self._load_persisted()

    # ============================================================
    # 工作记忆 (Working Memory)
    # ============================================================

    def add(self, thought: str, action: str, action_input: Any,
            observation: str, elapsed_ms: float = 0) -> None:
        """向工作记忆添加一个步骤记录

        Args:
            thought: Agent 的思考内容
            action: 执行的动作（工具名 或 "Final Answer"）
            action_input: 动作的输入参数
            observation: 动作执行后的观察结果
            elapsed_ms: 本步耗时（毫秒）
        """
        step = {
            "step_number": len(self.working_memory) + 1,
            "thought": thought,
            "action": action,
            "action_input": action_input,
            "observation": observation,
            "elapsed_ms": elapsed_ms,
        }
        self.working_memory.append(step)

        logger.info("[AgentMemory] 工作记忆写入: 步骤 %d, action=%s, 耗时=%.0fms",
                    step["step_number"], action, elapsed_ms)
        logger.debug("[AgentMemory] 工作记忆详细: thought=%s", thought[:80])

        # 超出上限时淘汰最早的记录
        while len(self.working_memory) > self.working_memory_limit:
            removed = self.working_memory.pop(0)
            logger.info("[AgentMemory] 工作记忆淘汰: 移除步骤 %d (超出上限 %d)",
                        removed["step_number"], self.working_memory_limit)
            # 重新编号
            for i, s in enumerate(self.working_memory):
                s["step_number"] = i + 1

    def reset_working(self) -> None:
        """清空工作记忆（新查询开始时调用）"""
        count = len(self.working_memory)
        self.working_memory.clear()
        logger.info("[AgentMemory] 工作记忆重置: 清空 %d 条记录", count)

    def get_working_context(self) -> str:
        """生成工作记忆的格式化文本，供 LLM 理解当前进度

        Returns:
            格式化的工作记忆上下文
        """
        if not self.working_memory:
            return "(尚未执行任何步骤)"

        lines = []
        for step in self.working_memory:
            obs = step["observation"]
            if len(obs) > 300:
                obs = obs[:300] + "..."
            lines.append(
                f"步骤 {step['step_number']}:\n"
                f"  Thought: {step['thought']}\n"
                f"  Action: {step['action']}\n"
                f"  Observation: {obs}"
            )
        return "\n\n".join(lines)

    # ============================================================
    # 情景记忆 (Episodic Memory)
    # ============================================================

    def summarize_to_episodic(self, user_query: str, final_answer: str) -> None:
        """将当前工作记忆压缩为摘要，存入情景记忆

        Args:
            user_query: 用户的原始问题
            final_answer: Agent 的最终答案
        """
        tools_used = list(set(
            step["action"] for step in self.working_memory
            if step["action"] not in ("Final Answer", "")
        ))

        summary = {
            "query": user_query,
            "answer_preview": final_answer[:100] + ("..." if len(final_answer) > 100 else ""),
            "steps_count": str(len(self.working_memory)),
            "tools_used": ", ".join(tools_used) if tools_used else "无",
            "timestamp": datetime.now().isoformat(),
        }
        self.episodic_memory.append(summary)

        logger.info("[AgentMemory] 情景记忆写入: query='%s', steps=%s, tools=%s",
                    user_query[:50], summary["steps_count"], summary["tools_used"])

        # 超出上限时淘汰最早的记录
        while len(self.episodic_memory) > self.episodic_memory_turns:
            removed = self.episodic_memory.pop(0)
            logger.info("[AgentMemory] 情景记忆淘汰: 移除 '%s'", removed["query"][:30])

        # 持久化到 JSON 文件
        self._save_persisted()

    def get_episodic_context(self, max_turns: int = 3) -> str:
        """获取情景记忆的格式化上下文

        Args:
            max_turns: 返回的最大对话轮数

        Returns:
            格式化的历史会话摘要
        """
        recent = self.episodic_memory[-max_turns:]
        if not recent:
            return "(无历史会话)"

        lines = []
        for i, ep in enumerate(recent, 1):
            lines.append(
                f"历史会话 {i} ({ep['steps_count']} 步, 工具: {ep['tools_used']}):\n"
                f"  用户问: {ep['query']}\n"
                f"  Agent 答: {ep['answer_preview']}"
            )

        logger.info("[AgentMemory] 获取情景记忆上下文: 返回 %d 轮", len(recent))
        return "\n".join(lines)

    # ============================================================
    # 长期记忆 (Long Term Memory)
    # ============================================================

    def get_long_term(self, category: str, key: str) -> Optional[str]:
        """从长期记忆中查询知识

        Args:
            category: 知识分类（如 "company_info"）
            key: 知识键（如 "中芯国际"）

        Returns:
            知识文本，未命中或关闭时返回 None
        """
        if not self.enable_long_term:
            logger.debug("[AgentMemory] 长期记忆未启用，跳过查询")
            return None

        result = self.long_term_memory.get(category, {}).get(key)
        if result:
            logger.info("[AgentMemory] 长期记忆命中: category=%s, key=%s", category, key)
        else:
            logger.info("[AgentMemory] 长期记忆未命中: category=%s, key=%s", category, key)
        return result

    def _init_long_term_memory(self) -> None:
        """初始化长期记忆（公司基本信息等静态知识）"""
        self.long_term_memory = {
            "company_info": {
                "中芯国际": "中芯国际集成电路制造有限公司，中国内地规模最大的集成电路晶圆代工企业。",
                "中国移动": "中国移动通信集团有限公司，全球网络规模最大的电信运营商。",
                "中国联通": "中国联合网络通信集团有限公司，综合性电信运营商。",
                "中国电信": "中国电信集团有限公司，全球领先的综合信息服务提供商。",
            }
        }
        logger.info("[AgentMemory] 长期记忆知识库加载完成")

    def _save_persisted(self) -> None:
        """将情景记忆全量写入 JSON 持久化文件

        仅在 enable_long_term=True 且 session_id 非空时执行。
        写入格式: [{timestamp, query, answer_preview, steps_count, tools_used}, ...]
        """
        if not self.enable_long_term or not self.session_id:
            return

        os.makedirs(self.persist_dir, exist_ok=True)
        filepath = os.path.join(self.persist_dir, f"{self.session_id}.json")

        data = []
        for ep in self.episodic_memory:
            item = {
                "timestamp": ep.get("timestamp", datetime.now().isoformat()),
                "query": ep["query"],
                "answer_preview": ep["answer_preview"],
                "steps_count": ep["steps_count"],
                "tools_used": ep["tools_used"],
            }
            data.append(item)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("[AgentMemory] 持久化写入: %s, %d 轮", filepath, len(data))

    def _load_persisted(self) -> None:
        """从 JSON 持久化文件加载情景记忆

        仅在 enable_long_term=True 且 session_id 非空时执行。
        加载最近 episodic_memory_turns 轮摘要。
        """
        if not self.enable_long_term or not self.session_id:
            return

        filepath = os.path.join(self.persist_dir, f"{self.session_id}.json")
        if not os.path.exists(filepath):
            logger.info("[AgentMemory] 持久化文件不存在，从空列表开始: %s", filepath)
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 只加载最近 episodic_memory_turns 轮
            recent = data[-self.episodic_memory_turns:] if len(data) > self.episodic_memory_turns else data
            self.episodic_memory = recent

            logger.info("[AgentMemory] 持久化加载: %s, 共 %d 轮, 加载 %d 轮",
                        filepath, len(data), len(recent))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("[AgentMemory] 持久化文件损坏或无法读取: %s, 错误: %s", filepath, e)
            self.episodic_memory = []

    # ============================================================
    # 对话摘要（供 Agent System Prompt 使用）
    # ============================================================

    def get_full_context(self, conversation_history: str = "") -> str:
        """获取完整上下文，组合情景记忆和工作记忆

        Args:
            conversation_history: 当前对话的原始历史文本

        Returns:
            组合后的上下文字符串
        """
        parts = []

        episodic = self.get_episodic_context()
        if episodic and episodic != "(无历史会话)":
            parts.append(f"## 历史会话摘要\n{episodic}")

        if conversation_history:
            parts.append(f"## 当前对话\n{conversation_history}")

        working = self.get_working_context()
        if working and working != "(尚未执行任何步骤)":
            parts.append(f"## 当前任务执行进度\n{working}")

        result = "\n\n".join(parts) if parts else conversation_history
        logger.info("[AgentMemory] 生成完整上下文: %d 个段落", len(parts))
        return result
