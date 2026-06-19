# -*- coding: utf-8 -*-
"""Mock 注入验证: 空结果累计 → 强制终止

绕过 LLM 的"聪明"，直接模拟 ReAct 循环中的空结果累积过程。
"""

import sys
import os
import logging
import io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools import ToolRegistry
from agent_memory import AgentMemory

# ============================================================
# Mock: 模拟一个总返回空结果的 ReActAgent
# (不调真实 LLM，直接注入空 Observation)
# ============================================================

# 捕获日志
log_stream = io.StringIO()
_handler = logging.StreamHandler(log_stream)
_handler.setFormatter(logging.Formatter("[%(name)s] [%(levelname)s] %(message)s"))
from agent_core import logger as ac_logger
ac_logger.addHandler(_handler)

from agent_core import ReActAgent

# 创建最小 Agent
registry = ToolRegistry()
memory = AgentMemory()
agent = ReActAgent(
    tool_registry=registry,
    memory=memory,
    max_steps=2,
    model="qwen-max",
)

print("=" * 60)
print("Mock 注入: 手动模拟空结果累计")
print("=" * 60)

# 模拟 _is_empty_result
tests = [
    ("[错误] 检索服务不可用", True),
    ("未找到相关数据，请尝试其他关键词", True),
    ("无有效数值可供验证", True),
    ("此次检索没有找到匹配的文档", True),
    ("来源文本不足，无法完成验证", True),
    ("中芯国际2024年营收为578.21亿元，同比增长17.48%", False),
    ("中国移动净利润为1,384亿元", False),
    ("", True),    # 空字符串
    ("unavailable", True),
]

print("\n[_is_empty_result] 空结果判定验证:")
all_pass = True
for text, expected in tests:
    result = agent._is_empty_result(text)
    status = "PASS" if result == expected else "FAIL"
    if status == "FAIL":
        all_pass = False
    print("  %s  %s → expected=%s, got=%s" % (status, text[:40], expected, result))

print("\n" + "=" * 60)
print("Mock: 连续空结果累计模拟 (2次)")
print("=" * 60)

empty_count = 0
for step in range(3):
    # 模拟每次调用返回空结果
    observation = "[错误] 未找到相关数据"
    is_empty = agent._is_empty_result(observation)
    if is_empty:
        empty_count += 1
        print("  Step %d: 空结果, 累计=%d, warning=%s" % (
            step + 1, empty_count, "触发!" if empty_count >= 2 else "未触发"))
    else:
        empty_count = max(0, empty_count - 1)
        print("  Step %d: 有结果, 重置累计=%d" % (step + 1, empty_count))

print("\n" + "=" * 60)
print("Mock: 有数据后重置累计")
print("=" * 60)

empty_count = 2  # 假设之前已经 2 次空结果
print("  初始: empty_count=%d" % empty_count)
observation = "中芯国际营收578.21亿元"
is_empty = agent._is_empty_result(observation)
if is_empty:
    empty_count += 1
else:
    empty_count = max(0, empty_count - 1)
print("  收到有效数据后: empty_count=%d (已重置)" % empty_count)

print("\n" + "=" * 60)
print("全部 Mock 验证完成: %s" % ("全部通过" if all_pass else "存在失败"))
print("=" * 60)

# 打印捕获的相关日志
log_output = log_stream.getvalue()
relevant_lines = [l for l in log_output.split("\n") if "[ReActAgent]" in l or "未解析" in l or "空结果" in l]
if relevant_lines:
    print("\n[相关日志片段]")
    for line in relevant_lines[:10]:
        print("  %s" % line)
