# -*- coding: utf-8 -*-
"""验证 agent_core.py 日志埋点在实际 Agent 运行中的输出

测试内容:
  1. 步骤摘要 (已完成N步/已调用工具/空结果次数)
  2. 空 Action 检测 + 自动格式修正
  3. 空结果检测 (累计次数 + warning)
  4. Token 用量 (input_tokens/output_tokens)
  5. 强制答案摘要 (已收集数据)

前提: 确保环境已配好 DASHSCOPE_API_KEY
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
print("Agent 日志埋点实战验证")
print("=" * 60)

# ============================================================
# 准备环境
# ============================================================

# 注册全部 5 个工具
registry = ToolRegistry()
registry.register(RetrieveTool())
registry.register(CalculatorTool())
registry.register(CompareTool())
registry.register(ChartTool())
registry.register(VerifyTool())

# 创建 Agent
memory = AgentMemory()
agent = ReActAgent(
    tool_registry=registry,
    memory=memory,
    max_steps=3,          # 限制步数，观察 max_steps 终止日志
    temperature=0.3,
    model="qwen-max",
)

# ============================================================
# 测试 1: 简单检索 → 验证空结果检测 + 正常结果
# ============================================================
print("\n" + "=" * 60)
print("测试 1: 简单检索 (中芯国际2024年营收)")
print("=" * 60)

result = agent.run("中芯国际2024年营收是多少")

print("\n[结果]")
print("  答案: %.80s..." % result.answer if len(result.answer) > 80 else "  答案: %s" % result.answer)
print("  success=%s, steps=%d, elapsed=%.1fs" % (result.success, result.total_steps, result.total_elapsed_ms / 1000))
print("  forced_stop=%s" % result.forced_stop)
print("  reasoning_chain: %d 条" % len(result.reasoning_chain))
for r in result.reasoning_chain:
    print("    Step %d: action=%s, thought=%.40s..." % (
        r["step_number"], r["action"], r["thought"]))

# ============================================================
# 测试 2: 多公司对比 → 验证步骤摘要 + 工具调用追踪
# ============================================================
print("\n" + "=" * 60)
print("测试 2: 多公司对比 (移动和联通2024营收对比)")
print("=" * 60)

result2 = agent.run("中国移动和中国联通2024年营收对比")

print("\n[结果]")
print("  success=%s, steps=%d, forced_stop=%s" % (result2.success, result2.total_steps, result2.forced_stop))
print("  reasoning_chain: %d 条" % len(result2.reasoning_chain))
for r in result2.reasoning_chain:
    obs_preview = r.get("observation", "")[:60]
    print("    Step %d: action=%s, thought=%.40s... obs=%.40s..." % (
        r["step_number"], r["action"], r["thought"], obs_preview))

print("\n" + "=" * 60)
print("全部验证完成 请查看上方日志输出:")
print("  - [ReActAgent] 步骤摘要: 已完成N步, 已调用工具=...")
print("  - [ReActAgent] LLM 调用成功: input_tokens=...")
print("  - [ReActAgent] 工具 '...' 返回空结果 (累计N次)")
print("  - [ReActAgent] 已收集数据: 工具调用=...")
print("=" * 60)
