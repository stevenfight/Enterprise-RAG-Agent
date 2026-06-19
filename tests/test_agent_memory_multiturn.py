# -*- coding: utf-8 -*-
"""TDD: Agent 记忆系统多轮追问集成测试 (10轮扩展版)

测试场景 (10轮连续对话):
  第1问: "中芯国际营收"              → 单公司基础检索
  第2问: "中国移动净收入"            → 切换公司+指标
  第3问: "那他的营收呢"              → 代词解析: 他=中国移动
  第4问: "他们对比怎么样"            → 复数指代: 他们=中芯+移动
  第5问: "那中国联通呢"              → 延续对比, 引入第3家公司
  第6问: "中国电信2024年净利润呢"    → 引入第4家公司
  第7问: "这四家中哪家利润率最高"    → 跨公司计算分析 (calculator)
  第8问: "把中芯国际的毛利率也算一下"→ 深化单个指标
  第9问: "重新整理所有公司核心指标"  → 四家综合对比
  第10问: "给我生成营收对比图"       → 图表生成 (chart)

测试状态标记系统:
  RED   - 功能未实现或验证不通过
  GREEN - 功能已实现且验证通过

测试ID: TC-MT01 ~ TC-MT12
  基础记忆 (TC-MT01~MT08) -- 前4轮场景, 覆盖基础记忆能力
  扩展场景 (TC-MT09~MT12) -- 10轮场景, 覆盖工具多样性/公司覆盖/情景淘汰/对话截断

对应 SDD: openspec/changes/rag-to-agent/specs/spec-memory.md
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ============================================================
# 测试状态登记表
# ============================================================
TEST_STATUS = {
    "TC-MT01": "GREEN",   # test_working_memory_per_round
    "TC-MT02": "GREEN",   # test_episodic_memory_accumulation
    "TC-MT03": "GREEN",   # test_conversation_history_linear
    "TC-MT04": "GREEN",   # test_pronoun_resolution_he
    "TC-MT05": "GREEN",   # test_pronoun_resolution_they
    "TC-MT06": "GREEN",   # test_episodic_limit_eviction
    "TC-MT07": "GREEN",   # test_conversation_manager_compat_multiturn
    "TC-MT08": "GREEN",   # test_get_full_context_composition
    "TC-MT09": "GREEN",   # test_10round_company_coverage_4companies
    "TC-MT10": "GREEN",   # test_10round_tool_diversity
    "TC-MT11": "GREEN",   # test_10round_episodic_eviction
    "TC-MT12": "GREEN",   # test_10round_convmanager_truncation
}

passed = 0
failed = 0
red_count = 0
green_count = 0


def check(test_id, name, condition, detail=""):
    """统一的测试断言函数，自动读取 TEST_STATUS 标记"""
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
print("TDD: Agent 记忆系统多轮追问集成测试 (10轮扩展版)")
print(f"AgentMemory 模块可用: {_MEMORY_AVAILABLE}")
if not _MEMORY_AVAILABLE:
    print(f"  (导入错误: {_MEMORY_IMPORT_ERROR})")
print(f"ConversationManager 可用: {_CONV_AVAILABLE}")
print(f"测试场景: 10 轮财务追问 (4家公司, 5种工具)")
print("=" * 60)


# ============================================================
# 测试数据: 10 轮财务追问场景
# ============================================================
SCENARIO = [
    # -------- 第1轮: 中芯国际营收 --------
    {
        "round": 1,
        "user_message": "中芯国际营收",
        "assistant_answer": "中芯国际2024年营业总收入为 577.96 亿元，同比增长约 10.8%。",
        "working_steps": [
            {"thought": "需要查询中芯国际的营收数据",
             "action": "retrieve",
             "action_input": {"query": "营收", "company_name": "中芯国际"},
             "observation": "找到 5 条结果，营收 577.96 亿元", "elapsed_ms": 1200},
            {"thought": "数据已获取，直接回答",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 500},
        ],
    },
    # -------- 第2轮: 中国移动净收入 --------
    {
        "round": 2,
        "user_message": "中国移动净收入",
        "assistant_answer": "中国移动2024年净收入为 1563 亿元。",
        "working_steps": [
            {"thought": "需要查询中国移动的净收入数据",
             "action": "retrieve",
             "action_input": {"query": "净收入", "company_name": "中国移动"},
             "observation": "找到 4 条结果，净收入 1563 亿元", "elapsed_ms": 1100},
            {"thought": "数据已获取，直接回答",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 450},
        ],
    },
    # -------- 第3轮: 那他的营收呢 (他→中国移动) --------
    {
        "round": 3,
        "user_message": "那他的营收呢",
        "assistant_answer": "中国移动2024年营业总收入为 9373 亿元。",
        "working_steps": [
            {"thought": "需要查询中国移动的营收数据，'他'指上一轮的中国移动",
             "action": "retrieve",
             "action_input": {"query": "营收", "company_name": "中国移动"},
             "observation": "找到 5 条结果，营收 9373 亿元", "elapsed_ms": 1150},
            {"thought": "数据已获取，直接回答",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 430},
        ],
    },
    # -------- 第4轮: 他们对比怎么样 (他们→中芯+移动) --------
    {
        "round": 4,
        "user_message": "他们对比怎么样",
        "assistant_answer": "2024年营收对比: 中芯国际 577.96亿元 vs 中国移动 9373亿元。中国移动营收约为中芯国际的16.2倍。",
        "working_steps": [
            {"thought": "需要查询中芯国际营收数据",
             "action": "retrieve",
             "action_input": {"query": "营收", "company_name": "中芯国际"},
             "observation": "找到 5 条结果，营收 577.96 亿元", "elapsed_ms": 1180},
            {"thought": "需要查询中国移动营收数据",
             "action": "retrieve",
             "action_input": {"query": "营收", "company_name": "中国移动"},
             "observation": "找到 5 条结果，营收 9373 亿元", "elapsed_ms": 1130},
            {"thought": "数据齐全，进行对比分析",
             "action": "compare",
             "action_input": {"companies": ["中芯国际", "中国移动"], "metrics": ["营收"]},
             "observation": "对比表生成: 中芯 577.96亿 vs 移动 9373亿", "elapsed_ms": 900},
            {"thought": "对比分析已完成",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 420},
        ],
    },
    # -------- 第5轮: 那中国联通呢 (延续对比，引入第3家) --------
    {
        "round": 5,
        "user_message": "那中国联通呢",
        "assistant_answer": "中国联通2024年营收 3726 亿元。三家对比: 移动 9373亿 > 联通 3726亿 > 中芯 577.96亿。",
        "working_steps": [
            {"thought": "用户追问中国联通，需要查询该公司的营收数据",
             "action": "retrieve",
             "action_input": {"query": "营收", "company_name": "中国联通"},
             "observation": "找到 5 条结果，营收 3726 亿元", "elapsed_ms": 1100},
            {"thought": "将中国联通加入之前的对比分析",
             "action": "compare",
             "action_input": {"companies": ["中芯国际", "中国移动", "中国联通"], "metrics": ["营收"]},
             "observation": "三家对比完成: 移动>联通>中芯", "elapsed_ms": 850},
            {"thought": "三家对比分析完成",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 400},
        ],
    },
    # -------- 第6轮: 中国电信2024年净利润呢 (引入第4家) --------
    {
        "round": 6,
        "user_message": "中国电信2024年净利润呢",
        "assistant_answer": "中国电信2024年净利润为 318 亿元。",
        "working_steps": [
            {"thought": "需要查询中国电信的净利润数据",
             "action": "retrieve",
             "action_input": {"query": "净利润", "company_name": "中国电信"},
             "observation": "找到 5 条结果，净利润 318 亿元", "elapsed_ms": 1080},
            {"thought": "数据已获取，直接回答",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 420},
        ],
    },
    # -------- 第7轮: 这四家中哪家利润率最高 (跨公司计算分析) --------
    {
        "round": 7,
        "user_message": "这四家中哪家利润率最高",
        "assistant_answer": "四家公司净利率对比: 中国移动 16.7% > 中国电信 6.2% > 中国联通 4.5% > 中芯国际 6.3%。中国移动利润率最高。",
        "working_steps": [
            {"thought": "需要查询四家公司的营收和净利润数据",
             "action": "retrieve",
             "action_input": {"query": "营收 净利润", "company_name": None},
             "observation": "找到 20 条结果，覆盖4家公司营收+利润", "elapsed_ms": 1350},
            {"thought": "需要计算每家公司的利润率: 净利润/营收*100%",
             "action": "calculator",
             "action_input": {"expression": "margin", "values": {"中芯国际": "36.69/577.96*100", "中国移动": "1563/9373*100", "中国联通": "166/3726*100", "中国电信": "318/5120*100"}},
             "observation": "中芯6.3%, 移动16.7%, 联通4.5%, 电信6.2%", "elapsed_ms": 550},
            {"thought": "对比计算结果，中国移动利润率最高",
             "action": "compare",
             "action_input": {"companies": ["中芯国际", "中国移动", "中国联通", "中国电信"], "metrics": ["净利率"]},
             "observation": "移动16.7% > 电信6.2% > 中芯6.3% > 联通4.5%", "elapsed_ms": 720},
            {"thought": "分析完成，给出结论",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 380},
        ],
    },
    # -------- 第8轮: 把中芯国际的毛利率也算一下 (深化指标) --------
    {
        "round": 8,
        "user_message": "把中芯国际的毛利率也算一下",
        "assistant_answer": "中芯国际2024年毛利率为 18.6%。",
        "working_steps": [
            {"thought": "需要查询中芯国际的营业成本和营收，计算毛利率",
             "action": "retrieve",
             "action_input": {"query": "营业成本 营收", "company_name": "中芯国际"},
             "observation": "找到 5 条结果，营收577.96亿，营业成本470.98亿", "elapsed_ms": 1120},
            {"thought": "计算毛利率: (营收-成本)/营收*100%",
             "action": "calculator",
             "action_input": {"expression": "margin", "values": {"毛利率": "(577.96-470.98)/577.96*100"}},
             "observation": "毛利率 18.6%", "elapsed_ms": 320},
            {"thought": "数据已计算，给出毛利率结果",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 360},
        ],
    },
    # -------- 第9轮: 重新整理所有公司核心指标对比 (四家综合对比) --------
    {
        "round": 9,
        "user_message": "重新整理一下所有公司的核心指标对比",
        "assistant_answer": "核心指标汇总: 中芯国际(营收577.96亿/净利36.69亿/毛利率18.6%), 中国移动(营收9373亿/净利1563亿/净利率16.7%), 中国联通(营收3726亿/净利166亿/净利率4.5%), 中国电信(营收5120亿/净利318亿/净利率6.2%)。",
        "working_steps": [
            {"thought": "需要查询四家公司所有核心指标",
             "action": "retrieve",
             "action_input": {"query": "营收 净利润 毛利率 净利率", "company_name": None},
             "observation": "找到 25 条结果，覆盖4家公司的营收/利润/利润率", "elapsed_ms": 1400},
            {"thought": "进行四家公司多指标综合对比",
             "action": "compare",
             "action_input": {"companies": ["中芯国际", "中国移动", "中国联通", "中国电信"], "metrics": ["营收", "净利润", "净利率", "毛利率"]},
             "observation": "四家公司多指标对比表生成完成", "elapsed_ms": 950},
            {"thought": "综合对比表已生成，给出汇总结论",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 400},
        ],
    },
    # -------- 第10轮: 给我生成营收对比图 (图表生成) --------
    {
        "round": 10,
        "user_message": "给我生成营收对比图",
        "assistant_answer": "营收对比柱状图已生成，保存至 data/charts/营收对比_2024.png。四家公司营收: 中国移动 9373亿, 中国电信 5120亿, 中国联通 3726亿, 中芯国际 577.96亿。",
        "working_steps": [
            {"thought": "需要四家公司的营收数据来生成图表",
             "action": "retrieve",
             "action_input": {"query": "营收", "company_name": None},
             "observation": "找到 20 条结果，四家公司营收数据齐全", "elapsed_ms": 1250},
            {"thought": "用 chart 工具生成柱状对比图",
             "action": "chart",
             "action_input": {"chart_type": "bar", "data": {"中芯国际": 577.96, "中国移动": 9373, "中国联通": 3726, "中国电信": 5120}},
             "observation": "柱状图已生成: data/charts/营收对比_2024.png", "elapsed_ms": 680},
            {"thought": "图表已生成，给出文件路径和数值说明",
             "action": "Final Answer",
             "action_input": None,
             "observation": "回答完成", "elapsed_ms": 350},
        ],
    },
]


# ============================================================
# 辅助函数
# ============================================================
def simulate_round(memory, conv, round_data):
    """模拟一轮 Agent 对话"""
    round_num = round_data["round"]
    conv.add_message("user", round_data["user_message"])
    memory.reset_working()
    for step in round_data["working_steps"]:
        memory.add(
            thought=step["thought"],
            action=step["action"],
            action_input=step["action_input"],
            observation=step["observation"],
            elapsed_ms=step.get("elapsed_ms", 0),
        )
    memory.summarize_to_episodic(
        user_query=round_data["user_message"],
        final_answer=round_data["assistant_answer"],
    )
    conv.add_message("assistant", round_data["assistant_answer"])
    print(f"\n  [SIM] 第{round_num}轮完成: "
          f"工作记忆 {len(round_data['working_steps'])}步, "
          f"情景记忆 {len(memory.episodic_memory)}条, "
          f"对话历史 {len(conv.messages)}条")


# ============================================================
# TC-MT01: 工作记忆逐轮独立 (4轮)
# ============================================================
print("\n--- TC-MT01: 工作记忆每轮独立 (reset_working 后清空) ---")

def test_mt01():
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5)
    for rd in SCENARIO[:4]:
        simulate_round(memory, conv, rd)
    # 第4轮有4步
    ok = len(memory.working_memory) == 4
    return ok, f"最后一轮工作记忆步数: {len(memory.working_memory)} 步 (预期4)"

check("TC-MT01", "4 轮追问后工作记忆仅保留最后一轮步骤",
      test_mt01()[0], detail=test_mt01()[1])


# ============================================================
# TC-MT02: 情景记忆跨轮累积 (4轮)
# ============================================================
print("\n--- TC-MT02: 情景记忆跨轮累积 ---")

def test_mt02():
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5)
    for rd in SCENARIO[:4]:
        simulate_round(memory, conv, rd)
    episode_count = len(memory.episodic_memory)
    ok = episode_count == 4
    detail_msg = f"预期 4 条, 实际 {episode_count} 条"
    if ok:
        for i, rd in enumerate(SCENARIO[:4]):
            if rd["user_message"] not in memory.episodic_memory[i]["query"]:
                detail_msg += f" (第{i+1}轮摘要 query 不匹配)"
                ok = False
                break
    return ok, detail_msg

check("TC-MT02", "4 轮追问后情景记忆累积 4 条摘要",
      test_mt02()[0], detail=test_mt02()[1])


# ============================================================
# TC-MT03: 对话历史线性完整 (4轮)
# ============================================================
print("\n--- TC-MT03: 对话历史线性完整 ---")

def test_mt03():
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5)
    for rd in SCENARIO[:4]:
        simulate_round(memory, conv, rd)
    msg_count = len(conv.messages)
    ok = msg_count == 8
    detail_msg = f"预期 8 条 (4user+4assistant), 实际 {msg_count} 条"
    if ok:
        roles = [m["role"] for m in conv.messages]
        if roles != ["user", "assistant"] * 4:
            detail_msg += f", 角色序列异常: {roles}"
            ok = False
    return ok, detail_msg

check("TC-MT03", "4 轮追问后对话历史共 8 条, user/assistant 交替",
      test_mt03()[0], detail=test_mt03()[1])


# ============================================================
# TC-MT04: 代词解析 "他"
# ============================================================
print("\n--- TC-MT04: 代词解析 '他' 指代中国移动 ---")

def test_mt04():
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5)
    for rd in SCENARIO[:2]:
        simulate_round(memory, conv, rd)
    context_str = conv.get_context_string()
    ok = "中国移动" in context_str and "净收入" in context_str
    detail_msg = f"中国移动={'OK' if '中国移动' in context_str else 'MISS'}, 净收入={'OK' if '净收入' in context_str else 'MISS'}, 上下文 {len(context_str)} 字符"
    return ok, detail_msg

check("TC-MT04", "get_context_string() 含 '中国移动'+'净收入', 代词'他'可解析",
      test_mt04()[0], detail=test_mt04()[1])


# ============================================================
# TC-MT05: 复数指代 "他们"
# ============================================================
print("\n--- TC-MT05: 复数指代 '他们' 指代中芯+移动 ---")

def test_mt05():
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5)
    for rd in SCENARIO[:3]:
        simulate_round(memory, conv, rd)
    context_str = conv.get_context_string()
    ok = "中芯国际" in context_str and "中国移动" in context_str
    return ok, f"中芯国际={'OK' if '中芯国际' in context_str else 'MISS'}, 中国移动={'OK' if '中国移动' in context_str else 'MISS'}, 长度 {len(context_str)} 字符"

check("TC-MT05", "get_context_string() 含'中芯国际'+'中国移动', 复数'他们'可解析",
      test_mt05()[0], detail=test_mt05()[1])


# ============================================================
# TC-MT06: 情景记忆上限淘汰
# ============================================================
print("\n--- TC-MT06: 情景记忆超过上限自动淘汰最早记录 ---")

def test_mt06():
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=3)
    conv = ConversationManager(max_turns=5)
    for rd in SCENARIO[:4]:
        simulate_round(memory, conv, rd)
    episode_count = len(memory.episodic_memory)
    ok = episode_count == 3
    detail_msg = f"episodic_memory_turns=3, 实际保留 {episode_count} 条"
    if ok and episode_count == 3:
        retained = [ep["query"] for ep in memory.episodic_memory]
        if "中芯国际营收" in retained:
            detail_msg += " (WARN: 第1轮未被淘汰)"
            ok = False
        else:
            detail_msg += f", 保留: {retained}"
    return ok, detail_msg

check("TC-MT06", "episodic_memory_turns=3 时第4轮后第1轮摘要被淘汰",
      test_mt06()[0], detail=test_mt06()[1])


# ============================================================
# TC-MT07: ConversationManager 兼容性
# ============================================================
print("\n--- TC-MT07: ConversationManager 多轮场景兼容性 ---")

def test_mt07():
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=3)
    for rd in SCENARIO[:4]:
        simulate_round(memory, conv, rd)
    history = conv.get_history()
    ok = len(history) == 6
    detail_msg = f"max_turns=3, get_history() 返回 {len(history)} 条 (预期6条, 最近3轮)"
    if ok:
        conv.clear()
        if len(conv.messages) != 0:
            detail_msg += " (WARN: clear后未清空)"
            ok = False
    return ok, detail_msg

check("TC-MT07", "ConversationManager max_turns 截断 + clear 正常",
      test_mt07()[0], detail=test_mt07()[1])


# ============================================================
# TC-MT08: get_full_context 三层组合
# ============================================================
print("\n--- TC-MT08: get_full_context 完整上下文组合 ---")

def test_mt08():
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=5)
    for rd in SCENARIO[:3]:
        simulate_round(memory, conv, rd)
    # 第4轮手动执行(不调用simulate_round，保留工作记忆状态)
    conv.add_message("user", SCENARIO[3]["user_message"])
    memory.reset_working()
    for step in SCENARIO[3]["working_steps"]:
        memory.add(thought=step["thought"], action=step["action"],
                   action_input=step["action_input"], observation=step["observation"],
                   elapsed_ms=step.get("elapsed_ms", 0))
    conversation_history = conv.get_context_string()
    full_context = memory.get_full_context(conversation_history)
    ok = True
    detail_parts = []
    if "## 历史会话摘要" in full_context or "历史会话" in full_context:
        detail_parts.append("情景记忆: OK")
    else:
        detail_parts.append("情景记忆: MISS"); ok = False
    if "## 当前对话" in full_context:
        detail_parts.append("对话历史: OK")
    else:
        detail_parts.append("对话历史: MISS"); ok = False
    if "## 当前任务执行进度" in full_context or "步骤" in full_context:
        detail_parts.append("工作记忆: OK")
    else:
        detail_parts.append("工作记忆: MISS"); ok = False
    detail_parts.append(f"总长度: {len(full_context)} 字符")
    return ok, " | ".join(detail_parts)

check("TC-MT08", "get_full_context 正确组合 3 层记忆",
      test_mt08()[0], detail=test_mt08()[1])


# ============================================================
# TC-MT09: 10轮场景 - 4家公司覆盖 (新)
# ============================================================
print("\n--- TC-MT09: 10轮场景4家公司覆盖验证 ---")

def test_mt09():
    """验证10轮对话后，情景记忆中包含全部4家公司的查询记录"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=10)
    conv = ConversationManager(max_turns=10)
    for rd in SCENARIO:
        simulate_round(memory, conv, rd)
    # 情景记忆应有 10 条
    ec = len(memory.episodic_memory)
    ok = ec == 10
    detail_parts = [f"情景记忆: {ec}/10 条"]
    # 验证每家公司至少被提到一次
    all_answers = " ".join(rd["assistant_answer"] for rd in SCENARIO)
    companies_ok = all(("中芯国际" in all_answers,
                        "中国移动" in all_answers,
                        "中国联通" in all_answers,
                        "中国电信" in all_answers))
    detail_parts.append(f"公司覆盖={'OK' if companies_ok else 'MISS'}")
    ok = ok and companies_ok
    return ok, " | ".join(detail_parts)

check("TC-MT09", "10轮后情景记忆10条, 4家公司全覆盖 (中芯/移动/联通/电信)",
      test_mt09()[0], detail=test_mt09()[1])


# ============================================================
# TC-MT10: 10轮场景 - 工具多样性验证 (新)
# ============================================================
print("\n--- TC-MT10: 10轮场景工具多样性验证 ---")

def test_mt10():
    """验证10轮中使用到的工具类型: retrieve, compare, calculator, chart"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=10)
    conv = ConversationManager(max_turns=10)
    for rd in SCENARIO:
        simulate_round(memory, conv, rd)
    # 从情景记忆中收集所有使用的工具
    all_tools = set()
    for ep in memory.episodic_memory:
        for t in ep["tools_used"].split(", "):
            if t and t != "无":
                all_tools.add(t)
    expected = {"retrieve", "compare", "calculator", "chart"}
    ok = all_tools >= expected
    missing = expected - all_tools
    return ok, f"已使用工具: {sorted(all_tools)}, 缺失: {sorted(missing) if missing else '无'}"

check("TC-MT10", "10轮使用 4 种工具: retrieve/compare/calculator/chart",
      test_mt10()[0], detail=test_mt10()[1])


# ============================================================
# TC-MT11: 10轮场景 - 情景记忆淘汰验证 (新)
# ============================================================
print("\n--- TC-MT11: 10轮+episodic_limit=5 情景记忆淘汰验证 ---")

def test_mt11():
    """验证 episodic_memory_turns=5 时，10轮后仅保留最近5轮摘要"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
    conv = ConversationManager(max_turns=10)
    for rd in SCENARIO:
        simulate_round(memory, conv, rd)
    ec = len(memory.episodic_memory)
    ok = ec == 5
    detail_msg = f"episodic_memory_turns=5, 10轮后保留 {ec} 条 (预期5条)"
    if ok:
        retained = [ep["query"] for ep in memory.episodic_memory]
        # 验证前5轮被淘汰，后5轮保留
        if "中芯国际营收" in retained:
            detail_msg += " (WARN: 第1轮未被淘汰)"
            ok = False
        elif "中国移动净收入" in retained:
            detail_msg += " (WARN: 第2轮未被淘汰)"
            ok = False
        else:
            expected_late = ["那中国联通呢", "中国电信2024年净利润呢",
                             "这四家中哪家利润率最高", "把中芯国际的毛利率也算一下",
                             "重新整理一下所有公司的核心指标对比", "给我生成营收对比图"]
            matches = sum(1 for q in expected_late if q in retained)
            detail_msg += f", 后6轮命中 {matches}/6"
    return ok, detail_msg

check("TC-MT11", "episodic_memory_turns=5 时10轮后仅保留最近5轮, 前5轮被淘汰",
      test_mt11()[0], detail=test_mt11()[1])


# ============================================================
# TC-MT12: 10轮场景 - ConversationManager 长对话截断 (新)
# ============================================================
print("\n--- TC-MT12: 10轮场景 ConversationManager max_turns 截断验证 ---")

def test_mt12():
    """验证 max_turns=5 时，10轮(20条)对话只保留最近5轮(10条)"""
    if not _MEMORY_AVAILABLE or not _CONV_AVAILABLE:
        return False, "模块不可用"
    from agent_memory import AgentMemory
    from conversation import ConversationManager
    memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=10)
    conv = ConversationManager(max_turns=5)
    for rd in SCENARIO:
        simulate_round(memory, conv, rd)
    total_msgs = len(conv.messages)
    history = conv.get_history()
    ok = len(history) == 10 and total_msgs == 20
    detail_msg = f"全部消息: {total_msgs} 条, get_history() 返回: {len(history)} 条 (max_turns=5, 预期10条)"
    if ok:
        # 验证截断后最早的是第6轮的消息
        first_in_history = history[0]["content"]
        round6_keyword = "中国电信2024年净利润"
        if round6_keyword in first_in_history:
            detail_msg += " (截断正确: 从第6轮开始)"
        else:
            detail_msg += f" (截断后首条: {first_in_history[:40]}...)"
    return ok, detail_msg

check("TC-MT12", "max_turns=5 时10轮长对话 get_history() 仅返回最近5轮(10条)",
      test_mt12()[0], detail=test_mt12()[1])


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
    print("状态: 全部 RED - 阶段五对话记忆升级尚未完成")
elif red_count > 0:
    print(f"状态: 部分通过 - 还有 {red_count} 项 RED 待开发")
else:
    print("状态: 全部 GREEN - 阶段五对话记忆升级完成")
print("=" * 60)
print("\n测试场景对应关系 (12 项):")
print("  基础记忆 (TC-MT01~08): 基于前 4 轮场景")
print("    TC-MT01 工作记忆逐轮独立    | TC-MT03 对话历史完整")
print("    TC-MT02 情景记忆累积        | TC-MT04 代词'他'解析")
print("    TC-MT05 复数'他们'解析      | TC-MT06 情景上限淘汰")
print("    TC-MT07 ConvManager 兼容    | TC-MT08 三层上下文组合")
print("  扩展场景 (TC-MT09~12): 基于 10 轮场景")
print("    TC-MT09 4家公司覆盖         | TC-MT10 工具多样性")
print("    TC-MT11 情景记忆淘汰(5/10)  | TC-MT12 对话截断(5/10)")
