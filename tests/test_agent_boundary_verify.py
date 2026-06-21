# -*- coding: utf-8 -*-
"""验证强制终止 + 空结果埋点

边界场景:
  1. 真实 LLM 空结果: 用非注册公司 (特斯拉) + company_name 参数,
     配合修复后的 _is_empty_result (增加 "[工具执行失败]" 和 "未检索到相关数据" 标记),
     观察 LLM 是否调用 retrieve 并触发空结果累计

  2. 合成空结果: monkey-patch _execute_action 返回 "[工具执行失败]",
     max_steps=2, 100% 可靠触发: 空结果累计(1次→2次) → forced_stop=True →
     _generate_forced_answer() 降级答案

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

# 注册工具
registry = ToolRegistry()
registry.register(RetrieveTool())
registry.register(CalculatorTool())
registry.register(CompareTool())
registry.register(ChartTool())
registry.register(VerifyTool())

# ============================================================
# 场景 1: 真实 LLM 调用 —— 非注册公司 + company_name 参数
# ============================================================
print("=" * 60)
print("场景 1: 真实 LLM 空结果 —— 非注册公司 特斯拉")
print("=" * 60)
print("策略:")
print("  - 传 company_name='特斯拉' 到 agent.run()")
print("  - System Prompt 追加 '优先检索该公司的数据'")
print("  - max_steps=2, LLM 可能尝试 retrieve → ValueError")
print("    → '[工具执行失败] 公司未注册' → _is_empty_result 捕获")
print("  - 也可能 LLM 直接 Final Answer (不调用 retrieve)")
print("=" * 60)

memory1 = AgentMemory()
agent1 = ReActAgent(
    tool_registry=registry,
    memory=memory1,
    max_steps=2,
    temperature=0.3,
    model="qwen-max",
)

print("\n[查询] 特斯拉2024年营收和净利润是多少 (company_name='特斯拉')")
result1 = agent1.run("特斯拉2024年营收和净利润是多少", company_name="特斯拉")

print("\n" + "-" * 40)
print("场景 1 结果摘要")
print("-" * 40)
print("  success     = %s" % result1.success)
print("  forced_stop = %s" % result1.forced_stop)
print("  total_steps = %d" % result1.total_steps)
print("  error       = %s" % result1.error)
print("  answer (前200字): %.200s" % result1.answer)
print("  reasoning_chain: %d 条" % len(result1.reasoning_chain))
for r in result1.reasoning_chain:
    obs_preview = r.get("observation", "")[:80].replace("\n", " ")
    print("    Step %d: action=%-12s thought=%.30s... obs=%.40s..." % (
        r["step_number"], r.get("action", "?"), r["thought"], obs_preview))

# ============================================================
# 场景 2: 合成空结果 —— monkey-patch _execute_action
#         100% 可靠触发: 每条工具调用都返回 "[工具执行失败]"
# ============================================================
print("\n" + "=" * 60)
print("场景 2: 合成空结果 —— monkey-patch _execute_action")
print("=" * 60)
print("策略:")
print("  - 替换 _execute_action, 所有工具调用都返回 '[工具执行失败] 模拟空结果'")
print("  - max_steps=2 → 必然触发:")
print("    空结果累计(1次→2次) → forced_stop=True → _generate_forced_answer()")
print("=" * 60)

memory2 = AgentMemory()
agent2 = ReActAgent(
    tool_registry=registry,
    memory=memory2,
    max_steps=2,
    temperature=0.3,
    model="qwen-max",
)

# Monkey-patch: 让所有工具调用都返回空结果
original_execute = agent2._execute_action
def fake_execute(action, action_input):
    return "[工具执行失败] 模拟空结果: 检索无匹配数据"
agent2._execute_action = fake_execute

print("\n[查询] 中芯国际2024年营收和净利润是多少 (合成空结果)")
result2 = agent2.run("中芯国际2024年营收和净利润是多少")

# 恢复原始方法
agent2._execute_action = original_execute

print("\n" + "-" * 40)
print("场景 2 结果摘要")
print("-" * 40)
print("  success     = %s" % result2.success)
print("  forced_stop = %s  <-- 预期 True" % result2.forced_stop)
print("  total_steps = %d  <-- 预期 %d" % (result2.total_steps, agent2.max_steps))
print("  error       = %s" % result2.error)
print("  answer (前300字): %.300s" % result2.answer)
print("  reasoning_chain: %d 条" % len(result2.reasoning_chain))
for r in result2.reasoning_chain:
    obs_preview = r.get("observation", "")[:80].replace("\n", " ")
    print("    Step %d: action=%-12s thought=%.30s... obs=%.40s..." % (
        r["step_number"], r.get("action", "?"), r["thought"], obs_preview))

# 断言验证
assert result2.forced_stop == True, "预期 forced_stop=True"
assert result2.total_steps == agent2.max_steps, "预期 total_steps=max_steps=%d" % agent2.max_steps
assert len(result2.answer) > 0, "预期强制降级答案非空"
print("\n  [PASS] 断言通过: forced_stop=True, total_steps=max_steps, 降级答案非空")

# ============================================================
# 场景 3: _parse_response 格式修正 和 _is_empty_result 标记验证
# ============================================================
print("\n" + "=" * 60)
print("场景 3: _parse_response 格式修正 + _is_empty_result 标记验证")
print("=" * 60)
print("说明: 此场景依赖 LLM 偶尔输出非标准格式,")
print("不可能 100% 复现, 但 _parse_response 和 continue 逻辑已验证")
print("=" * 60)

agent3 = ReActAgent.__new__(ReActAgent)
agent3._tool_registry = registry

# 测试 1: 正常格式
resp1 = "Thought: 需要检索。\nAction: retrieve\nAction Input: {\"query\": \"营收\"}"
t1, a1, inp1 = agent3._parse_response(resp1)
print("\n[Parse] 正常格式:")
print("  thought=%.30s action=%s" % (t1, a1))

# 测试 2: 缺少 Action (空 action)
resp2 = "Thought: 我需要更多数据。\n这是最终答案：营收1000亿"
t2, a2, inp2 = agent3._parse_response(resp2)
print("\n[Parse] 缺少 Action (格式化异常):")
print("  thought=%.30s action=%s" % (t2, a2))

# 测试 3: 标准 ReAct 格式
resp3 = """Thought: 先检索一下数据。
Action: retrieve
Action Input: {"query": "营收"}"""
t3, a3, inp3 = agent3._parse_response(resp3)
print("\n[Parse] 标准 ReAct 格式:")
print("  thought=%.30s action=%s input=%.40s" % (t3, a3, str(inp3)))

# 测试 _is_empty_result (含新增标记)
print("\n[_is_empty_result] 空结果检测 (含新增标记):")
tests = [
    ("[错误]test", True, "[错误] 前缀"),
    ("[工具执行失败] 公司 '特斯拉' 未在注册表中", True, "[工具执行失败] 前缀 (新增)"),
    ("未检索到相关数据。建议：调整查询关键词", True, "未检索到相关数据 (新增, retrieve空消息)"),
    ("未找到相关数据", True, "未找到相关数据"),
    ("无有效数值", True, "无有效数值"),
    ("中芯国际营收578亿元", False, "正常结果"),
    ("", True, "空字符串"),
]
all_pass = True
for text, expected, label in tests:
    actual = agent3._is_empty_result(text)
    status = "PASS" if actual == expected else "FAIL"
    if actual != expected:
        all_pass = False
    print("  [%s] %-60s → %s (expected %s)" % (status, label, actual, expected))

if all_pass:
    print("\n  [PASS] 全部 _is_empty_result 标记测试通过")
else:
    print("\n  [FAIL] 部分 _is_empty_result 标记测试失败")

print("\n" + "=" * 60)
print("全部边界验证完成")
print("=" * 60)
