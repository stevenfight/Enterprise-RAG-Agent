# -*- coding: utf-8 -*-
"""TDD: Agent 记忆系统中对话中断与上下文恢复测试

测试场景:
  场景A - 单轮内API超时中断: Agent执行retrieve后崩溃, summarize未调用
  场景B - 强制退出后重启: ConversationManager重建, AgentMemory保留, 情景记忆独立恢复
  场景C - 多次中断恢复: 5轮对话中第2、4轮中断, 验证无缺漏无重复

测试状态标记系统:
  RED   - 功能未实现或验证不通过
  GREEN - 功能已实现且验证通过

测试ID: TC-IR01 ~ TC-IR13
  TC-IR01~03  场景A - API超时中断 (工作记忆残留/情景记忆无污染/对话历史unanswered)
  TC-IR04~07  场景B - 强制退出重启 (情景记忆独立/对话独立/上下文恢复/公司信息保留)
  TC-IR08~13  场景C - 多次中断恢复 (累积正确/消息完整/各轮恢复/无重复/角色交替/追问)

对应 SDD: openspec/changes/rag-to-agent/specs/spec-memory.md
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ============================================================
# 测试状态登记表
# ============================================================
TEST_STATUS = {
    "TC-IR01": "GREEN",   # 场景A: 工作记忆残留
    "TC-IR02": "GREEN",   # 场景A: 情景记忆无污染
    "TC-IR03": "GREEN",   # 场景A: 对话未回复user
    "TC-IR04": "GREEN",   # 场景B: 情景记忆独立于对话
    "TC-IR05": "GREEN",   # 场景B: 对话历史独立重建
    "TC-IR06": "GREEN",   # 场景B: full_context仍有情景记忆
    "TC-IR07": "GREEN",   # 场景B: 情景记忆含公司信息
    "TC-IR08": "GREEN",   # 场景C: 情景记忆累积正确
    "TC-IR09": "GREEN",   # 场景C: 对话历史完整
    "TC-IR10": "GREEN",   # 场景C: 中断轮恢复正确
    "TC-IR11": "GREEN",   # 场景C: 无重复摘要
    "TC-IR12": "GREEN",   # 场景C: 角色交替正确
    "TC-IR13": "GREEN",   # 场景C: 恢复后可追问
}

passed = 0
failed = 0
red_count = 0
green_count = 0


def check(test_id, name, condition, detail=""):
    """统一的测试断言函数"""
    global passed, failed, red_count, green_count
    status = TEST_STATUS.get(test_id, "RED")
    if status == "GREEN":
        green_count += 1
        if condition:
            print(f"  [GREEN] [{test_id}] {name}")
            passed += 1
        else:
            print(f"  [FAIL] [{test_id}] {name} - 预期通过但失败: {detail}")
            failed += 1
    else:
        red_count += 1
        if condition:
            print(f"  [WARN] [{test_id}] {name} - 已通过但标记为RED, 请更新 TEST_STATUS 为 GREEN")
            passed += 1
        else:
            print(f"  [RED] [{test_id}] {name} - 模块未实现")
            failed += 1


# ============================================================
# 导入模块
# ============================================================
_MEMORY_AVAILABLE = False
_MEMORY_IMPORT_ERROR = ""
try:
    from agent_memory import AgentMemory
    _MEMORY_AVAILABLE = True
except ImportError as e:
    _MEMORY_IMPORT_ERROR = str(e)

_CONV_AVAILABLE = False
_CONV_IMPORT_ERROR = ""
try:
    from conversation import ConversationManager
    _CONV_AVAILABLE = True
except ImportError as e:
    _CONV_IMPORT_ERROR = str(e)

print("=" * 60)
print("TDD: Agent 记忆系统对话中断与上下文恢复测试")
print(f"AgentMemory 模块可用: {_MEMORY_AVAILABLE}")
if not _MEMORY_AVAILABLE:
    print(f"  (导入错误: {_MEMORY_IMPORT_ERROR})")
print(f"ConversationManager 可用: {_CONV_AVAILABLE}")
print("=" * 60)


# ============================================================
# 共享测试数据: 前 3 轮正常对话
# ============================================================
BASELINE_3_ROUNDS = [
    {
        "round": 1,
        "user_message": "中芯国际营收",
        "assistant_answer": "中芯国际2024年营业总收入为 577.96 亿元。",
        "working_steps": [
            {"thought": "需要查询中芯国际的营收数据", "action": "retrieve",
             "action_input": {"query": "营收", "company_name": "中芯国际"},
             "observation": "找到 5 条结果，营收 577.96 亿元", "elapsed_ms": 1200},
            {"thought": "数据已获取，直接回答", "action": "Final Answer",
             "action_input": None, "observation": "回答完成", "elapsed_ms": 500},
        ],
    },
    {
        "round": 2,
        "user_message": "中国移动净收入",
        "assistant_answer": "中国移动2024年净收入为 1563 亿元。",
        "working_steps": [
            {"thought": "需要查询中国移动的净收入数据", "action": "retrieve",
             "action_input": {"query": "净收入", "company_name": "中国移动"},
             "observation": "找到 4 条结果，净收入 1563 亿元", "elapsed_ms": 1100},
            {"thought": "数据已获取，直接回答", "action": "Final Answer",
             "action_input": None, "observation": "回答完成", "elapsed_ms": 450},
        ],
    },
    {
        "round": 3,
        "user_message": "那他的营收呢",
        "assistant_answer": "中国移动2024年营业总收入为 9373 亿元。",
        "working_steps": [
            {"thought": "需要查询中国移动的营收数据", "action": "retrieve",
             "action_input": {"query": "营收", "company_name": "中国移动"},
             "observation": "找到 5 条结果，营收 9373 亿元", "elapsed_ms": 1150},
            {"thought": "数据已获取，直接回答", "action": "Final Answer",
             "action_input": None, "observation": "回答完成", "elapsed_ms": 430},
        ],
    },
]


def execute_round(memory, conv, rd):
    """执行一轮完整对话 (add_message + working steps + summarize + add_message)"""
    conv.add_message("user", rd["user_message"])
    memory.reset_working()
    for step in rd["working_steps"]:
        memory.add(thought=step["thought"], action=step["action"],
                   action_input=step["action_input"],
                   observation=step["observation"],
                   elapsed_ms=step.get("elapsed_ms", 0))
    memory.summarize_to_episodic(user_query=rd["user_message"],
                                  final_answer=rd["assistant_answer"])
    conv.add_message("assistant", rd["assistant_answer"])


# ============================================================
# TC-IR01~03: 场景A - API 超时中断
# ============================================================
print("\n--- 场景A: API 超时中断 (retrieve后崩溃, summarize未调用) ---")

def test_ir01():
    """TC-IR01: 中断后工作记忆残留1步"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    # 前3轮正常
    for rd in BASELINE_3_ROUNDS:
        execute_round(memory, conv, rd)
    # 第4轮: retrieve 后中断
    conv.add_message("user", "中芯国际净利润")
    memory.reset_working()
    memory.add(thought="需要查询中芯国际净利润", action="retrieve",
               action_input={"query": "净利润", "company_name": "中芯国际"},
               observation="找到 5 条结果，净利润 36.69 亿元", elapsed_ms=1200)
    # 模拟中断: summarize 未调用, assistant 未写入
    ok = len(memory.working_memory) == 1
    return ok, f"工作记忆残留 {len(memory.working_memory)} 步 (预期1步)"

check("TC-IR01", "场景A: 中断后工作记忆残留1步(未调用summarize)",
      test_ir01()[0], detail=test_ir01()[1])


def test_ir02():
    """TC-IR02: 中断后情景记忆未被污染"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    for rd in BASELINE_3_ROUNDS:
        execute_round(memory, conv, rd)
    conv.add_message("user", "中芯国际净利润")
    memory.reset_working()
    memory.add(thought="需要查询中芯国际净利润", action="retrieve",
               action_input={"query": "净利润", "company_name": "中芯国际"},
               observation="找到 5 条结果，净利润 36.69 亿元", elapsed_ms=1200)
    ok = len(memory.episodic_memory) == 3
    queries = [ep["query"] for ep in memory.episodic_memory]
    return ok, f"情景记忆 {len(memory.episodic_memory)} 条(预期3条), 摘要: {queries}"

check("TC-IR02", "场景A: 中断后情景记忆未被污染(仍为前3轮)",
      test_ir02()[0], detail=test_ir02()[1])


def test_ir03():
    """TC-IR03: 中断后对话历史有未回复的user消息"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    for rd in BASELINE_3_ROUNDS:
        execute_round(memory, conv, rd)
    conv.add_message("user", "中芯国际净利润")
    memory.reset_working()
    memory.add(thought="需要查询中芯国际净利润", action="retrieve",
               action_input={"query": "净利润", "company_name": "中芯国际"},
               observation="找到 5 条结果，净利润 36.69 亿元", elapsed_ms=1200)
    ok = len(conv.messages) == 7 and conv.messages[-1]["role"] == "user"
    return ok, f"对话历史 {len(conv.messages)} 条, 最后一条 role={conv.messages[-1]['role']}"

check("TC-IR03", "场景A: 中断后对话历史有未回复的user消息(7条, 最后为user)",
      test_ir03()[0], detail=test_ir03()[1])


# ============================================================
# TC-IR04~07: 场景B - 强制退出重启
# ============================================================
print("\n--- 场景B: 强制退出后重启 (ConversationManager重建, AgentMemory保留) ---")

def test_ir04():
    """TC-IR04: 重启后情景记忆独立于对话历史"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    for rd in BASELINE_3_ROUNDS:
        execute_round(memory, conv, rd)
    # 模拟关闭窗口, 重建 ConversationManager, 保留 AgentMemory
    conv_new = ConversationManager(max_turns=5, agent_memory=memory)
    ok = (len(memory.episodic_memory) == 3 and
          len(conv_new.messages) == 0)
    return ok, (f"情景记忆={len(memory.episodic_memory)}条(仍在), "
                f"对话历史={len(conv_new.messages)}条(空)")

check("TC-IR04", "场景B: 重启后情景记忆独立于对话历史(3条摘要仍在, 对话为空)",
      test_ir04()[0], detail=test_ir04()[1])


def test_ir05():
    """TC-IR05: 重启后 ConversationManager 独立重建"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    for rd in BASELINE_3_ROUNDS:
        execute_round(memory, conv, rd)
    conv_new = ConversationManager(max_turns=5, agent_memory=memory)
    ctx = conv_new.get_context_string()
    ok = ctx == "" and len(conv_new.messages) == 0
    return ok, f"get_context_string='{ctx[:20]}', messages={len(conv_new.messages)}条"

check("TC-IR05", "场景B: 重启后get_context_string返回空(对话历史独立重建)",
      test_ir05()[0], detail=test_ir05()[1])


def test_ir06():
    """TC-IR06: 重启后 get_full_context 仍包含情景记忆"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    for rd in BASELINE_3_ROUNDS:
        execute_round(memory, conv, rd)
    conv_new = ConversationManager(max_turns=5, agent_memory=memory)
    full_ctx = conv_new.get_full_context()
    ok = ("历史会话摘要" in full_ctx or "历史会话" in full_ctx)
    return ok, f"full_context {len(full_ctx)} 字符, 含情景记忆={ok}"

check("TC-IR06", "场景B: 重启后get_full_context仍包含情景记忆",
      test_ir06()[0], detail=test_ir06()[1])


def test_ir07():
    """TC-IR07: 重启后情景记忆包含公司信息"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    for rd in BASELINE_3_ROUNDS:
        execute_round(memory, conv, rd)
    conv_new = ConversationManager(max_turns=5, agent_memory=memory)
    full_ctx = conv_new.get_full_context()
    ok = "中芯国际" in full_ctx and "中国移动" in full_ctx
    return ok, (f"中芯国际={'OK' if '中芯国际' in full_ctx else 'MISS'}, "
                f"中国移动={'OK' if '中国移动' in full_ctx else 'MISS'}")

check("TC-IR07", "场景B: 重启后full_context含公司信息(中芯国际+中国移动)",
      test_ir07()[0], detail=test_ir07()[1])


# ============================================================
# TC-IR08~13: 场景C - 多次中断恢复
# ============================================================
print("\n--- 场景C: 多次中断恢复 (5轮中第2、4轮各中断1次) ---")

def test_ir08():
    """TC-IR08: 情景记忆累积正确, 每轮1条共5条"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)

    interrupt_rounds = {2, 4}

    # 5轮数据 (第1~5轮)
    rounds_5 = BASELINE_3_ROUNDS + [
        {
            "round": 4,
            "user_message": "他们对比怎么样",
            "assistant_answer": "营收对比: 中芯577.96亿 vs 移动9373亿。",
            "working_steps": [
                {"thought": "查询中芯营收", "action": "retrieve",
                 "action_input": {"query": "营收", "company_name": "中芯国际"},
                 "observation": "营收 577.96 亿元", "elapsed_ms": 1180},
                {"thought": "查询移动营收", "action": "retrieve",
                 "action_input": {"query": "营收", "company_name": "中国移动"},
                 "observation": "营收 9373 亿元", "elapsed_ms": 1130},
                {"thought": "对比分析", "action": "compare",
                 "action_input": {"companies": ["中芯国际", "中国移动"], "metrics": ["营收"]},
                 "observation": "对比完成", "elapsed_ms": 900},
                {"thought": "完成", "action": "Final Answer",
                 "action_input": None, "observation": "回答完成", "elapsed_ms": 420},
            ],
        },
        {
            "round": 5,
            "user_message": "那中国联通呢",
            "assistant_answer": "中国联通2024年营收 3726 亿元。",
            "working_steps": [
                {"thought": "查询联通营收", "action": "retrieve",
                 "action_input": {"query": "营收", "company_name": "中国联通"},
                 "observation": "营收 3726 亿元", "elapsed_ms": 1100},
                {"thought": "加入对比", "action": "compare",
                 "action_input": {"companies": ["中芯国际", "中国移动", "中国联通"], "metrics": ["营收"]},
                 "observation": "三家对比完成", "elapsed_ms": 850},
                {"thought": "完成", "action": "Final Answer",
                 "action_input": None, "observation": "回答完成", "elapsed_ms": 400},
            ],
        },
    ]

    for rd in rounds_5:
        rn = rd["round"]
        conv.add_message("user", rd["user_message"])
        memory.reset_working()

        if rn in interrupt_rounds:
            # 模拟中断: 只执行到 retrieve
            step0 = rd["working_steps"][0]
            memory.add(thought=step0["thought"], action=step0["action"],
                       action_input=step0["action_input"],
                       observation=step0["observation"],
                       elapsed_ms=step0.get("elapsed_ms", 0))
            # 恢复: 清理 + 重新完整执行
            memory.reset_working()
            for step in rd["working_steps"]:
                memory.add(thought=step["thought"], action=step["action"],
                           action_input=step["action_input"],
                           observation=step["observation"],
                           elapsed_ms=step.get("elapsed_ms", 0))
        else:
            for step in rd["working_steps"]:
                memory.add(thought=step["thought"], action=step["action"],
                           action_input=step["action_input"],
                           observation=step["observation"],
                           elapsed_ms=step.get("elapsed_ms", 0))

        memory.summarize_to_episodic(user_query=rd["user_message"],
                                      final_answer=rd["assistant_answer"])
        conv.add_message("assistant", rd["assistant_answer"])

    ok = len(memory.episodic_memory) == 5
    queries = [ep["query"] for ep in memory.episodic_memory]
    return ok, f"情景记忆 {len(memory.episodic_memory)} 条, 摘要: {queries}"

check("TC-IR08", "场景C: 情景记忆累积5条无缺漏",
      test_ir08()[0], detail=test_ir08()[1])


def test_ir09():
    """TC-IR09: 对话历史10条完整"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    interrupt_rounds = {2, 4}
    rounds_5 = BASELINE_3_ROUNDS + [
        {"round": 4, "user_message": "他们对比怎么样",
         "assistant_answer": "营收对比: 中芯577.96亿 vs 移动9373亿。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
        {"round": 5, "user_message": "那中国联通呢",
         "assistant_answer": "中国联通2024年营收 3726 亿元。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
    ]
    def _add_safe(conv, role, content):
        if conv.messages and conv.messages[-1]["role"] == role:
            return
        conv.add_message(role, content)

    for rd in rounds_5:
        rn = rd["round"]
        _add_safe(conv, "user", rd["user_message"])
        memory.reset_working()
        if rn in interrupt_rounds:
            step0 = rd["working_steps"][0]
            memory.add(thought=step0["thought"], action=step0["action"],
                       action_input=step0["action_input"],
                       observation=step0["observation"])
            memory.reset_working()
        for step in rd["working_steps"]:
            memory.add(thought=step["thought"], action=step["action"],
                       action_input=step["action_input"],
                       observation=step["observation"])
        memory.summarize_to_episodic(user_query=rd["user_message"],
                                      final_answer=rd["assistant_answer"])
        _add_safe(conv, "assistant", rd["assistant_answer"])

    ok = len(conv.messages) == 10
    return ok, f"对话历史 {len(conv.messages)} 条 (预期10条 = 5轮×2)"

check("TC-IR09", "场景C: 对话历史10条完整",
      test_ir09()[0], detail=test_ir09()[1])


def test_ir10():
    """TC-IR10: 第2轮和第4轮中断后正确恢复"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    interrupt_rounds = {2, 4}
    rounds_5 = BASELINE_3_ROUNDS + [
        {"round": 4, "user_message": "他们对比怎么样",
         "assistant_answer": "营收对比: 中芯577.96亿 vs 移动9373亿。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
        {"round": 5, "user_message": "那中国联通呢",
         "assistant_answer": "中国联通2024年营收 3726 亿元。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
    ]
    for rd in rounds_5:
        rn = rd["round"]
        conv.add_message("user", rd["user_message"])
        memory.reset_working()
        if rn in interrupt_rounds:
            step0 = rd["working_steps"][0]
            memory.add(thought=step0["thought"], action=step0["action"],
                       action_input=step0["action_input"],
                       observation=step0["observation"])
            memory.reset_working()
        for step in rd["working_steps"]:
            memory.add(thought=step["thought"], action=step["action"],
                       action_input=step["action_input"],
                       observation=step["observation"])
        memory.summarize_to_episodic(user_query=rd["user_message"],
                                      final_answer=rd["assistant_answer"])
        conv.add_message("assistant", rd["assistant_answer"])

    ep_queries = [ep["query"] for ep in memory.episodic_memory]
    ok = ("中国移动净收入" in ep_queries and "他们对比怎么样" in ep_queries)
    return ok, (f"第2轮摘要={'OK' if '中国移动净收入' in ep_queries else 'MISS'}, "
                f"第4轮摘要={'OK' if '他们对比怎么样' in ep_queries else 'MISS'}")

check("TC-IR10", "场景C: 第2轮和第4轮中断后摘要均存在",
      test_ir10()[0], detail=test_ir10()[1])


def test_ir11():
    """TC-IR11: 无重复摘要"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    interrupt_rounds = {2, 4}
    rounds_5 = BASELINE_3_ROUNDS + [
        {"round": 4, "user_message": "他们对比怎么样",
         "assistant_answer": "营收对比: 中芯577.96亿 vs 移动9373亿。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
        {"round": 5, "user_message": "那中国联通呢",
         "assistant_answer": "中国联通2024年营收 3726 亿元。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
    ]
    def _add_safe(conv, role, content):
        if conv.messages and conv.messages[-1]["role"] == role:
            return
        conv.add_message(role, content)

    for rd in rounds_5:
        rn = rd["round"]
        _add_safe(conv, "user", rd["user_message"])
        memory.reset_working()
        if rn in interrupt_rounds:
            step0 = rd["working_steps"][0]
            memory.add(thought=step0["thought"], action=step0["action"],
                       action_input=step0["action_input"],
                       observation=step0["observation"])
            memory.reset_working()
        for step in rd["working_steps"]:
            memory.add(thought=step["thought"], action=step["action"],
                       action_input=step["action_input"],
                       observation=step["observation"])
        memory.summarize_to_episodic(user_query=rd["user_message"],
                                      final_answer=rd["assistant_answer"])
        _add_safe(conv, "assistant", rd["assistant_answer"])

    ep_queries = [ep["query"] for ep in memory.episodic_memory]
    ok = len(set(ep_queries)) == len(ep_queries)
    return ok, f"摘要数={len(ep_queries)}, 唯一数={len(set(ep_queries))}, 无重复"

check("TC-IR11", "场景C: 无重复摘要",
      test_ir11()[0], detail=test_ir11()[1])


def test_ir12():
    """TC-IR12: 对话历史 user/assistant 交替正确"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    interrupt_rounds = {2, 4}
    rounds_5 = BASELINE_3_ROUNDS + [
        {"round": 4, "user_message": "他们对比怎么样",
         "assistant_answer": "对比完成。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
        {"round": 5, "user_message": "那中国联通呢",
         "assistant_answer": "联通3726亿。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
    ]
    def _add_safe(conv, role, content):
        if conv.messages and conv.messages[-1]["role"] == role:
            return
        conv.add_message(role, content)

    for rd in rounds_5:
        rn = rd["round"]
        _add_safe(conv, "user", rd["user_message"])
        memory.reset_working()
        if rn in interrupt_rounds:
            step0 = rd["working_steps"][0]
            memory.add(thought=step0["thought"], action=step0["action"],
                       action_input=step0["action_input"],
                       observation=step0["observation"])
            memory.reset_working()
        for step in rd["working_steps"]:
            memory.add(thought=step["thought"], action=step["action"],
                       action_input=step["action_input"],
                       observation=step["observation"])
        memory.summarize_to_episodic(user_query=rd["user_message"],
                                      final_answer=rd["assistant_answer"])
        _add_safe(conv, "assistant", rd["assistant_answer"])

    roles = [m["role"] for m in conv.messages]
    ok = roles == ["user", "assistant"] * 5
    return ok, f"角色序列={roles}"

check("TC-IR12", "场景C: 对话历史 user/assistant 交替正确",
      test_ir12()[0], detail=test_ir12()[1])


def test_ir13():
    """TC-IR13: 中断恢复后可以正常追问"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5, agent_memory=memory)
    interrupt_rounds = {2, 4}
    rounds_5 = BASELINE_3_ROUNDS + [
        {"round": 4, "user_message": "他们对比怎么样",
         "assistant_answer": "对比完成。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
        {"round": 5, "user_message": "那中国联通呢",
         "assistant_answer": "联通3726亿。",
         "working_steps": [{"thought": "t", "action": "retrieve",
                            "action_input": {}, "observation": "ok", "elapsed_ms": 100},
                           {"thought": "t", "action": "Final Answer",
                            "action_input": None, "observation": "ok", "elapsed_ms": 100}]},
    ]
    def _add_safe(conv, role, content):
        if conv.messages and conv.messages[-1]["role"] == role:
            return
        conv.add_message(role, content)

    for rd in rounds_5:
        rn = rd["round"]
        _add_safe(conv, "user", rd["user_message"])
        memory.reset_working()
        if rn in interrupt_rounds:
            step0 = rd["working_steps"][0]
            memory.add(thought=step0["thought"], action=step0["action"],
                       action_input=step0["action_input"],
                       observation=step0["observation"])
            memory.reset_working()
        for step in rd["working_steps"]:
            memory.add(thought=step["thought"], action=step["action"],
                       action_input=step["action_input"],
                       observation=step["observation"])
        memory.summarize_to_episodic(user_query=rd["user_message"],
                                      final_answer=rd["assistant_answer"])
        _add_safe(conv, "assistant", rd["assistant_answer"])

    # 中断恢复后追问
    full_ctx = conv.get_full_context()
    ok = "中芯国际" in full_ctx and "中国移动" in full_ctx
    return ok, (f"full_context {len(full_ctx)} 字符, "
                f"中芯={'OK' if '中芯国际' in full_ctx else 'MISS'}, "
                f"移动={'OK' if '中国移动' in full_ctx else 'MISS'}")

check("TC-IR13", "场景C: 中断恢复后full_context含公司信息, 可继续追问",
      test_ir13()[0], detail=test_ir13()[1])


# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
total = passed + failed
red_pct = (red_count / max(total, 1)) * 100
green_pct = (green_count / max(total, 1)) * 100
print(f"测试汇总: {passed} PASS, {failed} FAIL, 共 {total} 项")
print(f"状态分布: {red_count} RED ({red_pct:.0f}%) | {green_count} GREEN ({green_pct:.0f}%)")
if red_count == total:
    print("状态: 全部 RED - 中断恢复功能尚未完成")
elif red_count > 0:
    print(f"状态: 部分通过 - 还有 {red_count} 项 RED 待开发")
else:
    print("状态: 全部 GREEN - 中断恢复功能完成")
print("=" * 60)
print("\n测试场景对应关系 (13 项):")
print("  场景A - API超时中断 (TC-IR01~03):")
print("    TC-IR01 工作记忆残留  | TC-IR02 情景记忆无污染  | TC-IR03 对话未回复")
print("  场景B - 强制退出重启 (TC-IR04~07):")
print("    TC-IR04 情景独立对话   | TC-IR05 对话空重建       | TC-IR06 full_ctx含情景")
print("    TC-IR07 含公司信息")
print("  场景C - 多次中断恢复 (TC-IR08~13):")
print("    TC-IR08 累积5条无缺漏  | TC-IR09 消息10条完整     | TC-IR10 中断轮恢复")
print("    TC-IR11 无重复摘要     | TC-IR12 角色交替正确     | TC-IR13 恢复后追问")
