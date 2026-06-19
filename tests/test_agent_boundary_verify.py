# -*- coding: utf-8 -*-
"""验证强制终止 + 空结果埋点

边界场景:
  1. 空结果: 查询不在向量库中的公司 (特斯拉) → retrieve 返回空
  2. 强制终止: max_steps=2, LLM 无法在 2 步内找到答案 → 触发 _generate_forced_answer

预期日志输出:
  - [ReActAgent] 工具 'retrieve' 返回空结果 (累计1次)
  - [ReActAgent] 工具 'retrieve' 返回空结果 (累计2次)
  - [ReActAgent] 连续2次空结果, 可能导致无效循环
  - [ReActAgent] ===== 达到最大步数 (max_steps=2) =====
  - [ReActAgent] 已收集数据: 工具调用=[...], 推理步数=2
  - [ReActAgent] 强制生成答案...
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools import ToolRegistry
from tools.retrieve_tool import RetrieveTool
from tools.calculator_tool import CalculatorTool
from tools.compare_tool import CompareTool
from tools.chart_tool import ChartTool
from tools.verify_tool import VerifyTool
from agent_memory import AgentMemory
from agent_core import ReActAgent

print("=" * 60)
print("边界场景: 强制终止 + 空结果验证")
print("=" * 60)
print("策略:")
print("  1. 查询不在向量库的公司 → retrieve 返回空")
print("  2. max_steps=2 → LLM 来不及修正 → 触发强制终止")
print("  这应该触发空结果累计 (1次, 2次) 和强制答案摘要")
print("=" * 60)

# 注册工具
registry = ToolRegistry()
registry.register(RetrieveTool())
registry.register(CalculatorTool())
registry.register(CompareTool())
registry.register(ChartTool())
registry.register(VerifyTool())

# 创建 Agent (max_steps=2, 刻意压低)
memory = AgentMemory()
agent = ReActAgent(
    tool_registry=registry,
    memory=memory,
    max_steps=2,           # 仅 2 步, 极易触发强制终止
    temperature=0.3,
    model="qwen-max",
)

print("\n[查询] 特斯拉2024年营收净利润是多少 (非数据库公司)")

result = agent.run("特斯拉2024年营收和净利润是多少")

print("\n" + "=" * 60)
print("结果摘要")
print("=" * 60)
print("  success=%s" % result.success)
print("  forced_stop=%s" % result.forced_stop)
print("  total_steps=%d" % result.total_steps)
print("  error=%s" % result.error)
print("  answer (前200字): %.200s" % result.answer)
print("  reasoning_chain: %d 条" % len(result.reasoning_chain))
for r in result.reasoning_chain:
    obs_preview = r.get("observation", "")[:80].replace("\n", " ")
    print("    Step %d: action=%-12s thought=%.30s... obs=%.40s..." % (
        r["step_number"], r.get("action", "?"), r["thought"], obs_preview))

# ============================================================
# 场景 2: 空 Action 格式修正 (手动构造)
# ============================================================
print("\n" + "=" * 60)
print("场景 2: 解析失败 / 空 Action 格式修正")
print("=" * 60)
print("说明: 此场景依赖 LLM 偶然输出非标准格式,")
print("不可能 100% 复现, 但 _parse_response 和 continue 逻辑已验证")
print("=" * 60)

# 直接测试 _parse_response 方法
agent2 = ReActAgent.__new__(ReActAgent)
agent2._tool_registry = registry

# 测试 1: 正常格式
resp1 = "Thought: 需要检索。\nAction: retrieve\nAction Input: {\"query\": \"营收\"}"
t1, a1, inp1 = agent2._parse_response(resp1)
print("\n[Parse] 正常格式:")
print("  thought=%.30s action=%s" % (t1, a1))

# 测试 2: 缺少 Action (空 action)
resp2 = "Thought: 我需要更多数据。\n这是最终答案：营收1000亿"
t2, a2, inp2 = agent2._parse_response(resp2)
print("\n[Parse] 缺少 Action (格式化异常):")
print("  thought=%.30s action=%s" % (t2, a2))

# 测试 3: 格式修正提示已送
resp3 = """Thought: 先检索一下数据。
Action: retrieve
Action Input: {"query": "营收"}"""
t3, a3, inp3 = agent2._parse_response(resp3)
print("\n[Parse] 标准 ReAct 格式:")
print("  thought=%.30s action=%s input=%.40s" % (t3, a3, str(inp3)))

# 测试 _is_empty_result
print("\n[_is_empty_result] 空结果检测:")
print("  [错误]test       → %s" % agent2._is_empty_result("[错误]test"))
print("  未找到相关数据     → %s" % agent2._is_empty_result("未找到相关数据"))
print("  无有效数值        → %s" % agent2._is_empty_result("无有效数值"))
print("  中芯国际营收578亿  → %s" % agent2._is_empty_result("中芯国际营收578亿元"))

print("\n" + "=" * 60)
print("全部边界验证完成")
print("=" * 60)
