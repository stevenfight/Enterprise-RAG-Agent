# -*- coding: utf-8 -*-
"""
Agent 核心控制器

实现 ReAct (Reasoning + Acting) 自主推理循环：
  1. LLM 生成 Thought（思考下一步做什么）
  2. 如果需要数据，输出 Action（调用工具）
  3. 工具执行返回 Observation（观察结果）
  4. 循环直到输出 Final Answer 或达到 max_steps

对应 SDD: openspec/changes/rag-to-agent/specs/spec-agent-core.md
"""

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from dashscope import Generation
from utils import get_api_key

from tools import ToolRegistry, ToolResult
from agent_memory import AgentMemory

logger = logging.getLogger("agent_core")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


@dataclass
class AgentResult:
    """Agent 执行结果

    Attributes:
        answer: 最终答案文本
        success: 是否成功完成推理
        reasoning_chain: 完整推理链（每步的 Thought/Action/Observation）
        total_steps: 执行的总步数
        total_elapsed_ms: 总耗时（毫秒）
        forced_stop: 是否因达到 max_steps 而强制停止
        error: 错误信息（success=False 时填充）
    """
    answer: str
    success: bool
    reasoning_chain: List[Dict[str, Any]] = field(default_factory=list)
    total_steps: int = 0
    total_elapsed_ms: float = 0.0
    forced_stop: bool = False
    error: str = ""


class ReActAgent:
    """ReAct 自主推理 Agent

    Usage:
        registry = ToolRegistry()
        registry.register(retrieve_tool)
        memory = AgentMemory()
        agent = ReActAgent(tool_registry=registry, memory=memory)
        result = agent.run("中芯国际2024年营收是多少")
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        memory: Optional[AgentMemory] = None,
        api_key: Optional[str] = None,
        max_steps: int = 5,
        llm_timeout: int = 60,
        temperature: float = 0.3,
        max_retries: int = 1,
        model: str = "qwen-max",
        system_prompt: Optional[str] = None,
    ):
        """初始化 ReAct Agent

        Args:
            tool_registry: 工具注册表
            memory: Agent 记忆系统（可选，默认创建新实例）
            api_key: DashScope API Key（可选，自动从环境读取）
            max_steps: 最大推理步数（默认 5）
            llm_timeout: LLM 调用超时秒数（默认 60）
            temperature: LLM 温度参数（默认 0.3）
            max_retries: 格式异常时的重试次数（默认 1）
            model: DashScope 模型名称（默认 qwen-max）
            system_prompt: 自定义 System Prompt 模板
        """
        self.tool_registry = tool_registry
        self.memory = memory or AgentMemory()
        self.api_key = api_key or get_api_key()

        self.max_steps = max_steps
        self.llm_timeout = llm_timeout
        self.temperature = temperature
        self.max_retries = max_retries
        self.model = model

        self._default_system_prompt = (
            "你是一个企业财务年报分析专家Agent。\n\n"
            "工作模式：推理-行动-观察 (ReAct)。\n\n"
            "每次回复必须使用以下格式：\n\n"
            "Thought: <分析当前情况，决定下一步做什么>\n"
            "Action: <工具名称或 Final Answer>\n"
            "Action Input: <工具的JSON参数，格式 {{\"key\": \"value\"}}>\n\n"
            "如果已有足够信息可以回答，使用：\n\n"
            "Thought: 已收集足够信息，可以给出最终答案\n"
            "Final Answer: <完整的回答，包含来源引用>\n\n"
            "规则：\n"
            "1. 每步只能调用一个工具\n"
            "2. 数据不充分时不要贸然回答，继续检索\n"
            "3. 回答中涉及的数字必须标注来源\n"
            "4. 工具返回空结果时，尝试调整查询角度\n"
            "5. 【单位换算】检索文档中的财务数据原始单位为「千元」，给出答案时必须转换。千元 ÷ 100,000 = 亿元（如 57,795,570千元 = 577.96亿元），千元 ÷ 10 = 万元。严禁将千元数值直接当作元来换算\n\n"
            "可用工具：\n{tool_descriptions}\n\n"
            "上下文：\n{context}"
        )

        self._custom_system_prompt = system_prompt

        logger.info("[ReActAgent] 初始化 Agent: model=%s, max_steps=%d, tools=%s",
                    model, max_steps, tool_registry.list_all())

    # ============================================================
    # 核心 run 方法
    # ============================================================

    def run(
        self,
        query: str,
        conversation_history: str = "",
        company_name: Optional[str] = None,
    ) -> AgentResult:
        """执行 Agent 推理循环

        Args:
            query: 用户问题
            conversation_history: 对话历史文本
            company_name: 可选的指定公司名

        Returns:
            AgentResult: 包含答案、推理链等完整信息
        """
        logger.info("[ReActAgent] ===== 新查询开始 =====")
        logger.info("[ReActAgent] 查询: %s", query)
        if company_name:
            logger.info("[ReActAgent] 指定公司: %s", company_name)

        self.memory.reset_working()

        reasoning_chain = []
        start_time = time.time()

        # 构建 System Prompt
        tool_descriptions = self.tool_registry.get_tool_descriptions()
        context = self.memory.get_full_context(conversation_history)
        system_prompt = self._build_system_prompt(tool_descriptions, context)

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]
        if company_name:
            messages.append({
                "role": "system",
                "content": f"当前查询针对公司: {company_name}。优先检索该公司的数据。"
            })
        messages.append({"role": "user", "content": query})

        logger.info("[ReActAgent] 初始消息构建完成, 共 %d 条", len(messages))

        # ReAct 主循环
        tools_called = set()  # 记录已调用的工具类型，检测重复调用
        empty_result_count = 0  # 空结果次数，检测搜索枯竭

        for step in range(self.max_steps):
            step_start = time.time()
            logger.info("[ReActAgent] --- 步骤 %d/%d 开始 ---", step + 1, self.max_steps)

            # 步骤摘要: 当前已收集信息概览
            steps_done = len(reasoning_chain)
            if steps_done > 0:
                logger.info("[ReActAgent] 步骤摘要: 已完成%d步, 已调用工具=%s, 空结果次数=%d",
                           steps_done, sorted(tools_called), empty_result_count)
            if empty_result_count >= 2:
                logger.warning("[ReActAgent] 连续%d次空结果, 可能导致无效循环", empty_result_count)

            # 调用 LLM
            llm_response = self._call_llm(messages)
            if llm_response is None:
                logger.error("[ReActAgent] LLM 调用失败，终止推理")
                elapsed = (time.time() - start_time) * 1000
                return AgentResult(
                    answer="",
                    success=False,
                    reasoning_chain=reasoning_chain,
                    total_steps=step + 1,
                    total_elapsed_ms=elapsed,
                    error="LLM 调用失败",
                )

            logger.info("[ReActAgent] LLM 响应长度: %d 字符", len(llm_response))
            messages.append({"role": "assistant", "content": llm_response})

            # 解析 LLM 响应
            thought, action, action_input = self._parse_response(llm_response)
            logger.info("[ReActAgent] 解析结果: thought=%.60s..., action=%s",
                       thought, action)

            # 检测空解析 (格式错误)
            if not action:
                logger.warning("[ReActAgent] 解析失败: 未提取到有效 Action, 可能 LLM 格式异常")
                # 提示 LLM 修正格式
                messages.append({
                    "role": "user",
                    "content": "你的回复格式不正确。请严格使用 Thought/Action/Action Input 格式。"
                })
                continue

            # 检查是否为 Final Answer
            if action == "Final Answer":
                final_answer = action_input
                elapsed_ms = (time.time() - start_time) * 1000
                self.memory.summarize_to_episodic(query, final_answer)
                logger.info("[ReActAgent] ===== 推理完成 (Final Answer) =====")
                logger.info("[ReActAgent] 总步数: %d, 总耗时: %.1fs", step + 1, elapsed_ms / 1000)
                return AgentResult(
                    answer=final_answer,
                    success=True,
                    reasoning_chain=reasoning_chain,
                    total_steps=step + 1,
                    total_elapsed_ms=elapsed_ms,
                )

            # 执行工具
            logger.info("[ReActAgent] 执行行动: action=%s", action)
            observation = self._execute_action(action, action_input)

            # 记录工具调用类型，检测空结果
            tools_called.add(action)
            is_empty = self._is_empty_result(observation)
            if is_empty:
                empty_result_count += 1
                logger.warning("[ReActAgent] 工具 '%s' 返回空结果 (累计%d次)", action, empty_result_count)
            else:
                empty_result_count = max(0, empty_result_count - 1)  # 有结果则重置

            step_elapsed = (time.time() - step_start) * 1000
            self.memory.add(
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
                elapsed_ms=step_elapsed,
            )

            reasoning_chain.append({
                "step_number": step + 1,
                "thought": thought,
                "action": action,
                "action_input": action_input,
                "observation": observation,
                "elapsed_ms": step_elapsed,
            })

            logger.info("[ReActAgent] 步骤 %d 耗时: %.0fms", step + 1, step_elapsed)

            # 将观察结果反馈给 LLM
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        # 达到 max_steps，强制生成答案
        elapsed_ms = (time.time() - start_time) * 1000
        logger.warning("[ReActAgent] ===== 达到最大步数 %d，强制生成答案 =====", self.max_steps)
        forced_answer = self._generate_forced_answer(messages)

        return AgentResult(
            answer=forced_answer,
            success=True,
            reasoning_chain=reasoning_chain,
            total_steps=self.max_steps,
            total_elapsed_ms=elapsed_ms,
            forced_stop=True,
        )

    # ============================================================
    # 内部方法
    # ============================================================

    def _build_system_prompt(self, tool_descriptions: str, context: str) -> str:
        """构建 System Prompt"""
        template = self._custom_system_prompt or self._default_system_prompt
        prompt = template.format(
            tool_descriptions=tool_descriptions,
            context=context if context else "(无历史上下文)",
        )
        logger.debug("[ReActAgent] System Prompt 长度: %d 字符", len(prompt))
        return prompt

    def _call_llm(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """调用 DashScope LLM

        Args:
            messages: 完整的消息列表

        Returns:
            LLM 生成的文本，失败返回 None
        """
        logger.info("[ReActAgent] 调用 LLM: model=%s, messages=%d 条", self.model, len(messages))
        try:
            resp = Generation.call(
                model=self.model,
                messages=messages,
                api_key=self.api_key,
                temperature=self.temperature,
                result_format="message",
                timeout=self.llm_timeout,
            )
            if resp.status_code == 200:
                content = resp.output.choices[0].message.content
                # 提取 Token 用量
                usage = getattr(resp, "usage", None)
                if usage:
                    logger.info("[ReActAgent] LLM 调用成功: %d 字符, input_tokens=%d, output_tokens=%d",
                               len(content), usage.input_tokens, usage.output_tokens)
                else:
                    logger.info("[ReActAgent] LLM 调用成功: 返回 %d 字符", len(content))
                return content
            else:
                logger.error("[ReActAgent] LLM 调用失败: status=%s, message=%s",
                           resp.status_code, resp.message)
                return None
        except Exception as e:
            logger.error("[ReActAgent] LLM 调用异常: %s", str(e))
            return None

    def _parse_response(self, response: str) -> tuple:
        """解析 LLM 响应，提取 Thought/Action/Action Input

        Args:
            response: LLM 原始响应文本

        Returns:
            (thought, action, action_input) 三元组
        """
        logger.debug("[ReActAgent] 开始解析 LLM 响应...")

        thought = ""
        action = ""
        action_input = ""

        # 提取 Thought
        thought_match = re.search(r"Thought:\s*(.+?)(?=\n(?:Action|Final))", response, re.DOTALL)
        if not thought_match:
            thought_match = re.search(r"Thought:\s*(.+)", response)
        if thought_match:
            thought = thought_match.group(1).strip()
            logger.debug("[ReActAgent] 解析到 Thought: %.60s...", thought)
        else:
            logger.warning("[ReActAgent] 未解析到 Thought")

        # 检查 Final Answer
        if "Final Answer:" in response:
            fa_match = re.search(r"Final Answer:\s*(.+)", response, re.DOTALL)
            if fa_match:
                thought = thought or "已收集足够信息"
                answer = fa_match.group(1).strip()
                logger.info("[ReActAgent] 解析到 Final Answer: %.80s...", answer)
                return (thought, "Final Answer", answer)

        # 提取 Action
        action_match = re.search(r"Action:\s*(\S+)", response)
        if action_match:
            action = action_match.group(1).strip()
            logger.debug("[ReActAgent] 解析到 Action: %s", action)
        else:
            logger.warning("[ReActAgent] 未解析到 Action")

        # 提取 Action Input（JSON 格式优先）
        ai_match = re.search(r"Action Input:\s*(\{.+?\})", response, re.DOTALL)
        if ai_match:
            try:
                action_input = json.loads(ai_match.group(1))
                logger.debug("[ReActAgent] 解析到 Action Input (JSON): %s", action_input)
            except json.JSONDecodeError:
                action_input = ai_match.group(1).strip()
                logger.warning("[ReActAgent] Action Input 不是有效 JSON: %.60s", action_input)
        else:
            # 回退：尝试从整行提取
            ai_match = re.search(r"Action Input:\s*(.+?)$", response)
            if ai_match:
                raw = ai_match.group(1).strip()
                try:
                    action_input = json.loads(raw)
                    logger.debug("[ReActAgent] 解析到 Action Input (回退JSON): %s", action_input)
                except json.JSONDecodeError:
                    action_input = raw
                    logger.warning("[ReActAgent] Action Input (回退) 不是 JSON: %.60s", raw)

        return (thought, action, action_input)

    def _execute_action(self, action: str, action_input: Any) -> str:
        """执行工具并返回观察结果

        Args:
            action: 工具名称
            action_input: 工具参数（dict 或 str）

        Returns:
            Observation 文本
        """
        if not action:
            logger.error("[ReActAgent] Action 为空，无法执行")
            return "[错误] Action 为空，请指定有效的工具名称"

        params = action_input if isinstance(action_input, dict) else {}
        logger.info("[ReActAgent] 路由到 ToolRegistry.execute('%s', %s)", action, params)

        result = self.tool_registry.execute(action, **params)
        obs = result.to_observation()
        logger.info("[ReActAgent] Observation: %.100s...", obs)
        return obs

    def _generate_forced_answer(self, messages: List[Dict[str, str]]) -> str:
        """达到 max_steps 后强制生成答案

        Args:
            messages: 当前的完整消息列表

        Returns:
            强制生成的答案
        """
        logger.info("[ReActAgent] 强制生成答案...")
        # 统计已收集的工具结果类型
        collected_tools = set()
        for step_info in reasoning_chain:
            collected_tools.add(step_info.get("action", "unknown"))
        logger.info("[ReActAgent] 已收集数据: 工具调用=%s, 推理步数=%d",
                     sorted(collected_tools), len(reasoning_chain))
        force_prompt = (
            "已达到推理步数上限。请基于目前已收集的信息，"
            "用 Final Answer 格式给出最佳答案。"
            "如果信息不完整，请说明哪些信息缺失。"
        )
        messages.append({"role": "user", "content": force_prompt})

        for retry in range(self.max_retries + 1):
            logger.info("[ReActAgent] 强制答案重试 %d/%d", retry + 1, self.max_retries + 1)
            response = self._call_llm(messages)
            if response is None:
                logger.warning("[ReActAgent] 强制答案 LLM 调用失败 (第 %d 次)", retry + 1)
                continue
            _, action, answer = self._parse_response(response)
            if action == "Final Answer" and answer:
                logger.info("[ReActAgent] 强制答案生成成功")
                return answer

        logger.error("[ReActAgent] 强制答案生成失败")
        return "抱歉，推理超时，未能生成有效答案。请尝试简化您的问题。"

    # ============================================================
    # 辅助方法
    # ============================================================

    def _is_empty_result(self, observation: str) -> bool:
        """检测工具观察结果是否为空/无有效数据

        判定规则:
          - 含 [错误] 前缀
          - 含 "未找到" / "无数据" / "没有"
          - 长度为 0

        Args:
            observation: 工具返回的 Observation 文本

        Returns:
            True 表示为空结果
        """
        if not observation or len(observation.strip()) == 0:
            return True
        if observation.startswith("[错误]"):
            return True
        empty_markers = ["未找到相关数据", "无数据", "没有检索到", "没有找到",
                         "无有效数值", "来源文本不足", "unavailable"]
        for marker in empty_markers:
            if marker in observation:
                logger.debug("[ReActAgent] 空结果检测: 匹配到标记 '%s'", marker)
                return True
        return False
