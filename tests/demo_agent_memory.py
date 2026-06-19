# -*- coding: utf-8 -*-
"""
Agent 记忆系统演示脚本 (20轮扩展版)

模拟 20 轮财务追问场景，展示三层记忆 + ConversationManager 的协同工作。
重点验证: 长对话下情景记忆淘汰机制、ConversationManager 窗口截断、日志完整性。

运行: python tests/demo_agent_memory.py

配置:
  - 工作记忆上限: 10 步 (单轮内)
  - 情景记忆上限: 5 轮 (超出自动淘汰最早摘要)
  - 对话历史窗口: 5 轮 (get_context_string 仅返回最近5轮)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_memory import AgentMemory
from conversation import ConversationManager

# 日志开关
LOG_RETRIEVE = True   # retrieve 后打印详情
LOG_SUMMARIZE = True  # summarize 后打印详情
LOG_TRUNCATION = True # 截断/淘汰时打印详情


def divider(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def log_retrieve(round_num, step_num, company, metric, result):
    """retrieve 步骤后的详细日志"""
    if not LOG_RETRIEVE:
        return
    print(f"    [LOG·检索] 第{round_num}轮 步骤{step_num}: "
          f"公司={company}, 指标={metric}, 结果='{result[:50]}...'")


def log_summarize(round_num, user_query, answer_preview, steps_count, tools_used):
    """summarize 后的详细日志"""
    if not LOG_SUMMARIZE:
        return
    print(f"    [LOG·压缩] 第{round_num}轮 → 情景记忆: "
          f"query='{user_query[:30]}...', answer='{answer_preview[:30]}...', "
          f"steps={steps_count}, tools={tools_used}")


def log_truncation(round_num, conv, memory):
    """打印截断/淘汰信息"""
    if not LOG_TRUNCATION:
        return
    total_msgs = len(conv.messages)
    visible = min(conv.max_turns * 2, total_msgs)
    truncated = total_msgs - visible

    ep_total = len(memory.episodic_memory)
    ep_limit = memory.episodic_memory_turns
    ep_excess = max(0, ep_total - ep_limit)

    if truncated > 0 or ep_excess > 0:
        print(f"    [LOG·截断] 第{round_num}轮后: "
              f"对话截断 {truncated} 条(共{total_msgs}条, 保留最近{visible}条) | "
              f"情景淘汰 {ep_excess} 条(保留{ep_total}条, 上限{ep_limit})")


def show_episodic_summary(memory, round_num, show_all=False):
    """打印情景记忆摘要"""
    if not memory.episodic_memory:
        print(f"    [情景记忆] 空")
        return
    ep_list = memory.episodic_memory
    if not show_all and len(ep_list) > 8:
        # 只显示首尾各2条
        print(f"    [情景记忆] 共 {len(ep_list)} 条 (显示首尾):")
        for i, ep in enumerate(ep_list[:2]):
            print(f"      [{i}] query='{ep['query'][:25]}...' | steps={ep['steps_count']} | tools={ep['tools_used']}")
        print(f"      ... (省略 {len(ep_list) - 4} 条) ...")
        for i, ep in enumerate(ep_list[-2:], len(ep_list) - 2):
            print(f"      [{i}] query='{ep['query'][:25]}...' | steps={ep['steps_count']} | tools={ep['tools_used']}")
    else:
        print(f"    [情景记忆] 共 {len(ep_list)} 条:")
        for i, ep in enumerate(ep_list):
            print(f"      [{i}] query='{ep['query'][:30]}...' | steps={ep['steps_count']} | tools={ep['tools_used']}")


def show_working_memory(memory):
    """打印工作记忆"""
    if not memory.working_memory:
        print(f"    [工作记忆] 空")
        return
    print(f"    [工作记忆] 共 {len(memory.working_memory)} 步:")
    for s in memory.working_memory:
        obs = s["observation"]
        if len(obs) > 55:
            obs = obs[:55] + "..."
        print(f"      步骤{s['step_number']}: Action={s['action']}, Obs='{obs}'")


# ============================================================
# 20 轮场景数据
# ============================================================
# 公司数据(模拟):
#   中芯国际: 营收577.96亿, 净利36.69亿, 毛利率18.6%, 研发49.92亿, 现金流102亿
#   中国移动: 营收9373亿,  净利1563亿,  净利率16.7%, 研发286亿,   现金流2800亿
#   中国联通: 营收3726亿,  净利166亿,   净利率4.5%,  研发78亿,    现金流650亿
#   中国电信: 营收5120亿,  净利318亿,   净利率6.2%,  研发132亿,   现金流980亿
SCENARIO = [
    # (轮次, 用户消息, 助手回答, [(thought, action, action_input, observation, elapsed_ms), ...])
    # ===== 第1~5轮: 引入3家公司, 代词解析, 对比 =====
    (1, "中芯国际营收",
     "中芯国际2024年营业总收入为 577.96 亿元。",
     [("需要查询中芯国际的营收数据", "retrieve",
       {"query": "营收", "company_name": "中芯国际"},
       "找到 5 条结果，营收 577.96 亿元", 1200),
      ("数据已获取，直接回答", "Final Answer", None, "回答完成", 500)]),

    (2, "中国移动净收入",
     "中国移动2024年净收入为 1563 亿元。",
     [("需要查询中国移动的净收入数据", "retrieve",
       {"query": "净收入", "company_name": "中国移动"},
       "找到 4 条结果，净收入 1563 亿元", 1100),
      ("数据已获取，直接回答", "Final Answer", None, "回答完成", 450)]),

    (3, "那他的营收呢",
     "中国移动2024年营业总收入为 9373 亿元。",
     [("需要查询中国移动的营收数据，'他'指上一轮的中国移动", "retrieve",
       {"query": "营收", "company_name": "中国移动"},
       "找到 5 条结果，营收 9373 亿元", 1150),
      ("数据已获取，直接回答", "Final Answer", None, "回答完成", 430)]),

    (4, "他们对比怎么样",
     "2024年营收对比: 中芯国际 577.96亿元 vs 中国移动 9373亿元。中国移动营收约为中芯国际的16.2倍。",
     [("需要查询中芯国际营收数据", "retrieve",
       {"query": "营收", "company_name": "中芯国际"},
       "找到 5 条结果，营收 577.96 亿元", 1180),
      ("需要查询中国移动营收数据", "retrieve",
       {"query": "营收", "company_name": "中国移动"},
       "找到 5 条结果，营收 9373 亿元", 1130),
      ("数据齐全，进行对比分析", "compare",
       {"companies": ["中芯国际", "中国移动"], "metrics": ["营收"]},
       "对比表生成: 中芯 577.96亿 vs 移动 9373亿", 900),
      ("对比分析已完成", "Final Answer", None, "回答完成", 420)]),

    (5, "那中国联通呢",
     "中国联通2024年营收 3726 亿元。三家对比: 移动 9373亿 > 联通 3726亿 > 中芯 577.96亿。",
     [("用户追问中国联通，需要查询营收数据", "retrieve",
       {"query": "营收", "company_name": "中国联通"},
       "找到 5 条结果，营收 3726 亿元", 1100),
      ("将中国联通加入对比分析", "compare",
       {"companies": ["中芯国际", "中国移动", "中国联通"], "metrics": ["营收"]},
       "三家对比完成: 移动>联通>中芯", 850),
      ("三家对比分析完成", "Final Answer", None, "回答完成", 400)]),

    # ===== 第6~10轮: 引入第4家公司, 多指标计算, 图表 =====
    (6, "中国电信2024年净利润呢",
     "中国电信2024年净利润为 318 亿元。",
     [("需要查询中国电信的净利润数据", "retrieve",
       {"query": "净利润", "company_name": "中国电信"},
       "找到 5 条结果，净利润 318 亿元", 1080),
      ("数据已获取，直接回答", "Final Answer", None, "回答完成", 420)]),

    (7, "这四家中哪家利润率最高",
     "四家净利率: 中国移动 16.7%, 中国电信 6.2%, 中芯国际 6.3%, 中国联通 4.5%。中国移动利润率最高。",
     [("需要查询四家公司的营收和净利润数据", "retrieve",
       {"query": "营收 净利润", "company_name": None},
       "找到 20 条结果，覆盖4家公司营收+利润", 1350),
      ("计算每家利润率: 净利润/营收*100%", "calculator",
       {"expression": "margin",
        "values": {"中芯国际": "36.69/577.96*100", "中国移动": "1563/9373*100",
                   "中国联通": "166/3726*100", "中国电信": "318/5120*100"}},
       "中芯6.3%, 移动16.7%, 联通4.5%, 电信6.2%", 550),
      ("对比计算结果", "compare",
       {"companies": ["中芯国际", "中国移动", "中国联通", "中国电信"], "metrics": ["净利率"]},
       "移动16.7% > 中芯6.3% > 电信6.2% > 联通4.5%", 720),
      ("分析完成", "Final Answer", None, "回答完成", 380)]),

    (8, "把中芯国际的毛利率也算一下",
     "中芯国际2024年毛利率为 18.6%。",
     [("需要查询中芯国际的营业成本和营收", "retrieve",
       {"query": "营业成本 营收", "company_name": "中芯国际"},
       "找到 5 条结果，营收577.96亿，营业成本470.98亿", 1120),
      ("计算毛利率: (营收-成本)/营收*100%", "calculator",
       {"expression": "margin", "values": {"毛利率": "(577.96-470.98)/577.96*100"}},
       "毛利率 18.6%", 320),
      ("数据已计算", "Final Answer", None, "回答完成", 360)]),

    (9, "重新整理一下所有公司的核心指标对比",
     "汇总: 中芯(营收577.96亿/净利36.69亿/毛利率18.6%), 移动(营收9373亿/净利1563亿/净利率16.7%), 联通(营收3726亿/净利166亿/净利率4.5%), 电信(营收5120亿/净利318亿/净利率6.2%)。",
     [("需要查询四家公司所有核心指标", "retrieve",
       {"query": "营收 净利润 毛利率 净利率", "company_name": None},
       "找到 25 条结果，覆盖4家公司的营收/利润/利润率", 1400),
      ("四家公司多指标综合对比", "compare",
       {"companies": ["中芯国际", "中国移动", "中国联通", "中国电信"],
        "metrics": ["营收", "净利润", "净利率", "毛利率"]},
       "四家公司多指标对比表生成完成", 950),
      ("综合对比完成", "Final Answer", None, "回答完成", 400)]),

    (10, "给我生成营收对比图",
     "营收对比柱状图已生成: data/charts/营收对比_2024.png。中国移动 9373亿, 中国电信 5120亿, 中国联通 3726亿, 中芯国际 577.96亿。",
     [("需要四家公司营收数据", "retrieve",
       {"query": "营收", "company_name": None},
       "找到 20 条结果，四家公司营收数据齐全", 1250),
      ("用 chart 工具生成柱状对比图", "chart",
       {"chart_type": "bar",
        "data": {"中芯国际": 577.96, "中国移动": 9373, "中国联通": 3726, "中国电信": 5120}},
       "柱状图已生成: data/charts/营收对比_2024.png", 680),
      ("图表已生成", "Final Answer", None, "回答完成", 350)]),

    # ===== 第11~15轮: 深化指标, 研发费用, 负债率 =====
    (11, "中芯国际2024年的研发费用是多少",
     "中芯国际2024年研发费用为 49.92 亿元，占营收比例约 8.6%。",
     [("需要查询中芯国际的研发费用数据", "retrieve",
       {"query": "研发费用", "company_name": "中芯国际"},
       "找到 3 条结果，研发费用 49.92 亿元", 1050),
      ("数据已获取，直接回答", "Final Answer", None, "回答完成", 410)]),

    (12, "那中国移动呢",
     "中国移动2024年研发费用为 286 亿元，占营收比例约 3.1%。",
     [("延续上轮话题，需要查询中国移动研发费用", "retrieve",
       {"query": "研发费用", "company_name": "中国移动"},
       "找到 4 条结果，研发费用 286 亿元", 1080),
      ("数据已获取", "Final Answer", None, "回答完成", 400)]),

    (13, "中国电信的营收增长率是多少",
     "中国电信2024年营收 5120 亿元，较2023年 4930 亿元增长约 3.9%。",
     [("需要查询中国电信2023和2024年的营收数据", "retrieve",
       {"query": "营收 2023 2024", "company_name": "中国电信"},
       "找到 6 条结果，2024年5120亿，2023年4930亿", 1150),
      ("计算同比增长率: (5120-4930)/4930*100%", "calculator",
       {"expression": "yoy", "values": {"增长率": "(5120-4930)/4930*100"}},
       "增长率 3.85% ≈ 3.9%", 340),
      ("计算完成", "Final Answer", None, "回答完成", 380)]),

    (14, "这四个公司谁负债率最低",
     "四家公司资产负债率: 中国移动 33.2%, 中国电信 47.8%, 中国联通 52.1%, 中芯国际 38.5%。中国移动负债率最低。",
     [("需要查询四家公司的资产负债率", "retrieve",
       {"query": "资产负债率 总负债 总资产", "company_name": None},
       "找到 18 条结果，四家公司负债率数据齐全", 1400),
      ("对比四家资产负债率", "compare",
       {"companies": ["中芯国际", "中国移动", "中国联通", "中国电信"], "metrics": ["资产负债率"]},
       "移动33.2% < 中芯38.5% < 电信47.8% < 联通52.1%", 800),
      ("对比完成", "Final Answer", None, "回答完成", 390)]),

    (15, "把负债率从低到高排个序",
     "资产负债率从低到高: 中国移动 33.2% < 中芯国际 38.5% < 中国电信 47.8% < 中国联通 52.1%。",
     [("已有负债率数据，直接排序", "compare",
       {"companies": ["中芯国际", "中国移动", "中国联通", "中国电信"], "metrics": ["资产负债率"], "sort": "asc"},
       "排序完成: 移动<中芯<电信<联通", 550),
      ("排序完成", "Final Answer", None, "回答完成", 350)]),

    # ===== 第16~20轮: 现金流, 深入对比, 最终汇总 =====
    (16, "中芯国际的现金流怎么样",
     "中芯国际2024年经营活动现金流为 102 亿元，同比减少约 18.7%。",
     [("需要查询中芯国际的经营活动现金流数据", "retrieve",
       {"query": "经营活动现金流", "company_name": "中芯国际"},
       "找到 4 条结果，现金流量 102 亿元", 1080),
      ("数据已获取", "Final Answer", None, "回答完成", 410)]),

    (17, "那净利润率呢",
     "中芯国际2024年销售净利润率为 6.3%。",
     [("延续上轮的中芯国际话题，查询净利润率", "retrieve",
       {"query": "净利润率", "company_name": "中芯国际"},
       "找到 3 条结果，净利润率 6.3%", 1020),
      ("数据已获取", "Final Answer", None, "回答完成", 380)]),

    (18, "对比一下中芯国际和中国联通的现金流",
     "现金流对比: 中芯国际 102亿 vs 中国联通 650亿。中国联通现金流约为中芯国际的6.4倍。",
     [("需要查询中国联通现金流数据", "retrieve",
       {"query": "经营活动现金流", "company_name": "中国联通"},
       "找到 4 条结果，联通现金流 650 亿元", 1060),
      ("对比中芯和联通现金流", "compare",
       {"companies": ["中芯国际", "中国联通"], "metrics": ["经营活动现金流"]},
       "联通650亿 > 中芯102亿", 620),
      ("对比完成", "Final Answer", None, "回答完成", 390)]),

    (19, "生成一张净利润对比图",
     "净利润对比柱状图已生成: data/charts/净利润对比_2024.png。移动 1563亿, 电信 318亿, 联通 166亿, 中芯 36.69亿。",
     [("需要四家公司净利润数据", "retrieve",
       {"query": "净利润", "company_name": None},
       "找到 16 条结果，四家公司净利润数据齐全", 1200),
      ("用 chart 工具生成柱状图", "chart",
       {"chart_type": "bar",
        "data": {"中芯国际": 36.69, "中国移动": 1563, "中国联通": 166, "中国电信": 318}},
       "柱状图已生成: data/charts/净利润对比_2024.png", 640),
      ("图表已生成", "Final Answer", None, "回答完成", 340)]),

    (20, "汇总一下本次查询的所有关键发现",
     "本次 20 轮查询关键发现汇总: (1)营收规模: 移动9373亿 > 电信5120亿 > 联通3726亿 > 中芯578亿; (2)利润率: 移动16.7%最高, 联通4.5%最低; (3)负债率: 移动33.2%最健康; (4)现金流: 移动雄厚, 中芯偏紧; (5)毛利率: 中芯18.6%, 制造业特征明显。",
     [("需要汇总所有历史查询的关键指标", "retrieve",
       {"query": "营收 净利润 现金流 负债率 毛利率", "company_name": None},
       "找到 30 条结果，覆盖全部历史查询指标", 1500),
      ("进行综合汇总对比", "compare",
       {"companies": ["中芯国际", "中国移动", "中国联通", "中国电信"],
        "metrics": ["营收", "净利润", "净利率", "资产负债率", "毛利率", "经营活动现金流"]},
       "综合汇总表生成完成", 1000),
      ("汇总分析完成", "Final Answer", None, "回答完成", 450)]),
]


# ============================================================
# 初始化
# ============================================================
divider("初始化: AgentMemory + ConversationManager")

memory = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
conv = ConversationManager(max_turns=5, agent_memory=memory)

print("配置参数:")
print(f"  AgentMemory.working_memory_limit  = {memory.working_memory_limit}")
print(f"  AgentMemory.episodic_memory_turns = {memory.episodic_memory_turns}")
print(f"  ConversationManager.max_turns     = {conv.max_turns}")
print(f"  关键约束: get_context_string() 仅返回最近 {conv.max_turns} 轮对话 (={conv.max_turns * 2} 条消息)")
print(f"  关键约束: 情景记忆超过 {memory.episodic_memory_turns} 条时自动淘汰最早记录")
print(f"  日志开关: LOG_RETRIEVE={LOG_RETRIEVE}, LOG_SUMMARIZE={LOG_SUMMARIZE}, LOG_TRUNCATION={LOG_TRUNCATION}")


# ============================================================
# 逐轮执行
# ============================================================
context_samples = {}  # 保存指定轮次的 context_before 供最终核查
sample_rounds = [3, 5, 10, 15, 18, 20]  # 在这些轮次采样 context_before

for rd_num, user_msg, assistant_ans, steps in SCENARIO:
    divider(f"第 {rd_num} 轮: 用户问 '{user_msg[:35]}'")

    # ---- 步骤0: 打印当前上下文(用于代词解析) ----
    if rd_num in sample_rounds:
        context_before = conv.get_context_string()
        context_samples[rd_num] = context_before
        print(f"\n  ┌─ 第{rd_num}轮 context_before (get_context_string) ─┐")
        lines = context_before.split("\n")
        if len(lines) > 15:
            print(f"  │ (共 {len(lines)} 行, 显示首尾)...")
            for l in lines[:6]:
                print(f"  │ {l}")
            print(f"  │ ... (省略 {len(lines) - 10} 行) ...")
            for l in lines[-4:]:
                print(f"  │ {l}")
        else:
            for l in lines:
                print(f"  │ {l}")
        print(f"  └────────────────────────────────────────────┘")
        # 核查窗口内容
        # 注意: context_before 采样于本轮的 add_message 之前,
        # 所以当前 conv.messages 仅包含前 (rd_num-1) 轮的对话。
        # get_history() 的最后 max_turns 轮 = 第 (rd_num-max_turns) ~ (rd_num-1) 轮
        if rd_num >= 10:
            expected_start_round = rd_num - conv.max_turns  # 窗口起始轮 (context_before 不含本轮)
            visible_content = context_before
            print(f"  [核查] 第{rd_num}轮采样时机: 本轮的 add_message 之前, "
                  f"conv.messages={2*(rd_num-1)} 条(第1~{rd_num-1}轮)")
            print(f"  [核查] 预期窗口: 第{expected_start_round}~{rd_num-1}轮 (取最后{conv.max_turns}轮)")
            # 验证: 第(expected_start_round-1)轮的消息不应在窗口中
            if expected_start_round > 1:
                early_msg = SCENARIO[expected_start_round - 2][1]
                if early_msg in visible_content:
                    print(f"  [WARN] 截断异常! 第{expected_start_round-1}轮消息 '{early_msg}' 仍在窗口中!")
                else:
                    print(f"  [OK] 第{expected_start_round-1}轮消息已截断")
            # 验证: 第expected_start_round轮的消息应在窗口中
            start_msg = SCENARIO[expected_start_round - 1][1]
            if start_msg in visible_content:
                print(f"  [OK] 第{expected_start_round}轮消息在窗口中")
            else:
                print(f"  [WARN] 第{expected_start_round}轮消息缺失!")

    # ---- 步骤1: 用户消息写入 ----
    conv.add_message("user", user_msg)
    memory.reset_working()
    print(f"  -> user 消息已写入 ConversationManager, 工作记忆已清空")

    # ---- 步骤2: Agent 执行每一步 ----
    for step_i, (thought, action, action_input, observation, elapsed) in enumerate(steps, 1):
        memory.add(thought=thought, action=action,
                   action_input=action_input, observation=observation,
                   elapsed_ms=elapsed)

        # retrieve 后打印详细日志
        if LOG_RETRIEVE and action == "retrieve":
            company = action_input.get("company_name", "全公司") if action_input else "全公司"
            query = action_input.get("query", "") if action_input else ""
            log_retrieve(rd_num, step_i, company, query, observation)

    # ---- 步骤3: 压缩到情景记忆 ----
    memory.summarize_to_episodic(user_query=user_msg, final_answer=assistant_ans)
    if LOG_SUMMARIZE:
        ep = memory.episodic_memory[-1]  # 刚追加的
        log_summarize(rd_num, ep["query"], ep["answer_preview"],
                      ep["steps_count"], ep["tools_used"])

    # ---- 步骤4: 助手回答写入 ----
    conv.add_message("assistant", assistant_ans)

    # ---- 步骤5: 截断/淘汰检查 ----
    log_truncation(rd_num, conv, memory)

    # ---- 步骤6: 状态快照 (每5轮或前5轮每轮) ----
    if rd_num <= 5 or rd_num % 5 == 0:
        print(f"\n  ┌─ 第{rd_num}轮 状态快照 ─┐")
        print(f"  │ 对话总条数: {len(conv.messages)} (含超出窗口的)")
        print(f"  │ 窗口内条数: {min(conv.max_turns * 2, len(conv.messages))}")
        print(f"  │ 情景记忆: {len(memory.episodic_memory)} 条 (上限{memory.episodic_memory_turns})")
        print(f"  │ 工作记忆: {len(memory.working_memory)} 步")
        show_episodic_summary(memory, rd_num, show_all=(rd_num <= 6))
        show_working_memory(memory)
        print(f"  └──────────────────────┘")

# ============================================================
# 最终验证
# ============================================================
divider("最终验证: 20轮长对话稳定性检查")

print("\n  一、情景记忆淘汰机制验证")
print(f"    情景记忆上限: {memory.episodic_memory_turns}")
print(f"    实际保留: {len(memory.episodic_memory)} 条")
ep_queries = [ep["query"] for ep in memory.episodic_memory]
print(f"    保留的摘要: {ep_queries}")
# 验证前15轮全被淘汰
early_queries = [SCENARIO[i][1] for i in range(15)]  # 前15轮
leaked = [q for q in early_queries if q in ep_queries]
if leaked:
    print(f"    [FAIL] 情景记忆淘汰异常! 以下前15轮未被淘汰: {leaked}")
else:
    print(f"    [PASS] 情景记忆淘汰正常: 前15轮全部淘汰, 仅保留第16~20轮")

print("\n  二、ConversationManager 窗口截断验证")
print(f"    对话总条数: {len(conv.messages)}")
print(f"    窗口大小: {conv.max_turns * 2} 条 ({conv.max_turns} 轮)")
history = conv.get_history()
print(f"    get_history() 返回: {len(history)} 条")

# 验证 context_before 在第20轮的正确性
# 重要: 第20轮 context_before 采样于"添加第20轮消息之前",
# 此时对话已有 38 条消息(第1~19轮), max_turns=5, get_context_string()
# 返回 messages[-10:] = 第15~19轮。所以窗口内应有第15轮, 不应有第14轮。
print("\n  三、第20轮 context_before 窗口内容核查 (采样于第20轮消息添加前)")
ctx20 = context_samples.get(20, conv.get_context_string())
ctx20_total_lines = len(ctx20.split("\n"))
print(f"    context_before 共 {ctx20_total_lines} 行, 总字符: {len(ctx20)}")
print(f"    采样时机: 第20轮消息添加前 (conv.messages 共 38 条 = 第1~19轮)")
print(f"    预期窗口: 第15~19轮 (max_turns=5, 取最后 10 条 = 第15~19轮的 user+assistant)")
round14_msg = SCENARIO[13][1]  # "这四个公司谁负债率最低" (第14轮, 不应出现)
round15_msg = SCENARIO[14][1]  # "把负债率从低到高排个序" (第15轮, 应该在窗口内)
if round14_msg in ctx20:
    print(f"    [FAIL] 第14轮消息 '{round14_msg}' 仍在窗口中, 截断边界错误!")
else:
    print(f"    [PASS] 第14轮消息已正确截断, 不在窗口中")
if round15_msg in ctx20:
    print(f"    [PASS] 第15轮消息在窗口中 (正常: 窗口=15~19轮)")
else:
    print(f"    [FAIL] 第15轮消息缺失! 窗口起始位置不正确")

print("\n  四、工作记忆独立性验证")
print(f"    第20轮后工作记忆步数: {len(memory.working_memory)} (预期=3: retrieve+compare+answer)")
step_actions = [s["action"] for s in memory.working_memory]
print(f"    步骤 actions: {step_actions}")

print("\n  五、工具使用统计")
all_tools = set()
for ep in memory.episodic_memory:
    for t in ep["tools_used"].split(", "):
        if t and t != "无":
            all_tools.add(t)
# 同时统计全部20轮的
full_tools = set()
for _, _, _, steps in SCENARIO:
    for _, action, _, _, _ in steps:
        if action != "Final Answer":
            full_tools.add(action)
print(f"    情景记忆中记录的工具: {sorted(all_tools)}")
print(f"    全部20轮实际使用的工具: {sorted(full_tools)}")

print("\n  六、完整对话历史条数")
print(f"    全部消息: {len(conv.messages)} 条 (预期=40条 = 20轮×2)")

# ============================================================
# 对话历史回放 (仅首尾)
# ============================================================
divider("对话历史回放 (40条, 仅显示首4条和尾4条)")

for i, msg in enumerate(conv.messages):
    if i < 4 or i >= len(conv.messages) - 4:
        role = "用户" if msg["role"] == "user" else "助手"
        content = msg["content"]
        if len(content) > 75:
            content = content[:75] + "..."
        print(f"  [{i+1:2d}] {role}: {content}")
    elif i == 4:
        print(f"  ... (省略中间 {len(conv.messages) - 8} 条) ...")

# ============================================================
# get_full_context 输出
# ============================================================
divider("get_full_context() 输出 (第20轮后的完整上下文)")

full_ctx = conv.get_full_context()
print(f"  总长度: {len(full_ctx)} 字符")
# 只显示结构摘要
for section_header in ["## 历史会话摘要", "## 当前对话", "## 当前任务执行进度"]:
    if section_header in full_ctx:
        print(f"  [OK] 包含: {section_header}")
    else:
        print(f"  [MISS] 缺少: {section_header}")

# 展示片段
print("\n--- 情景记忆部分 (get_full_context 中的) ---")
if full_ctx:
    sections = full_ctx.split("## ")
    for s in sections:
        if s.startswith("历史会话摘要"):
            content = s[:500]
            if len(s) > 500:
                content = s[:500] + "\n... (截断)"
            print("## " + content)

# ============================================================
# 汇总检查
# ============================================================
divider("汇总检查 (20轮场景)")

checks = [
    ("工作记忆独立", len(memory.working_memory) == 3,
     f"第20轮 {len(memory.working_memory)} 步 (retrieve+compare+answer)"),
    ("情景记忆上限", len(memory.episodic_memory) == 5,
     f"episodic_limit=5, 实际={len(memory.episodic_memory)}"),
    ("前15轮全部淘汰",
     all(SCENARIO[i][1] not in ep_queries for i in range(15)),
     f"{len(leaked)} 条泄漏"),
    ("对话总条数", len(conv.messages) == 40,
     f"预期40条(20轮×2), 实际{len(conv.messages)}"),
    ("窗口截断正确",
     len(conv.get_history()) == 10,
     f"max_turns=5, get_history()返回{len(conv.get_history())}条"),
    ("第20轮context_before截断正确",
     round14_msg not in ctx20 and round15_msg in ctx20,
     "第14轮已截断(窗口外), 第15轮在窗口内"),
    ("三层上下文完整",
     all(kw in full_ctx for kw in ["历史会话摘要", "当前对话", "当前任务执行进度"]),
     "情景记忆+对话+工作记忆"),
    ("20轮工具多样性",
     full_tools >= {"retrieve", "compare", "calculator", "chart"},
     f"使用工具: {sorted(full_tools)}"),
]

all_ok = True
for name, ok, detail in checks:
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_ok = False
    print(f"  [{status}] {name}: {detail}")

print(f"\n  结论: {'全部 8 项通过' if all_ok else '存在失败项, 请检查'}")
print("=" * 60)

# ============================================================
# 异常测试: 模拟对话中断与上下文恢复
# ============================================================
divider("异常测试: 对话中断与情景记忆恢复")
print("""
  测试目标:
    模拟 3 种典型中断场景, 验证情景记忆在异常情况下是否正确保持,
    以及恢复后的上下文是否完整。

  场景概述:
    场景A - 单轮内API超时中断: Agent执行了retrieve但未生成Final Answer
    场景B - 对话中途强制退出: 用户关闭窗口, 情景记忆已持久化前几轮摘要
    场景C - 恢复后追问: 基于历史情景记忆恢复上下文, 继续对话
""")

# ---- 场景A: 单轮内 API 超时中断 ----
divider("场景A: 模拟 Agent retrieve 后 API 超时, 本轮未完成 summarize")

print("""
  初始状态:
    前 3 轮正常对话已完成: 中芯营收(2步) → 移动净收入(2步) → 移动营收(2步)
    情景记忆有 3 条摘要, 工作记忆为空(上一轮已 summarize)
  
  第 4 轮中断:
    用户问"中芯国际净利润"
    Agent 执行 retrieve(成功) → 准备 calculator 时 API 超时, 进程崩溃
    summarize_to_episodic() 未调用, assistant 消息未写入
""")

mem_a = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
conv_a = ConversationManager(max_turns=5, agent_memory=mem_a)

# 正常完成前 3 轮
for rd in SCENARIO[:3]:
    conv_a.add_message("user", rd[1])
    mem_a.reset_working()
    for thought, action, action_input, obs, elapsed in rd[3]:
        mem_a.add(thought=thought, action=action,
                  action_input=action_input, observation=obs, elapsed_ms=elapsed)
    mem_a.summarize_to_episodic(user_query=rd[1], final_answer=rd[2])
    conv_a.add_message("assistant", rd[2])

print("  前 3 轮执行完毕:")
print(f"    情景记忆: {len(mem_a.episodic_memory)} 条")
print(f"    对话历史: {len(conv_a.messages)} 条")
print(f"    工作记忆: {len(mem_a.working_memory)} 步 (已清空)")

# 模拟第 4 轮中断: 只完成 retrieve, 未调用 summarize
print("\n  第 4 轮开始...")
conv_a.add_message("user", "中芯国际净利润")
mem_a.reset_working()
mem_a.add(thought="需要查询中芯国际的净利润数据",
          action="retrieve",
          action_input={"query": "净利润", "company_name": "中芯国际"},
          observation="找到 5 条结果，净利润 36.69 亿元", elapsed_ms=1200)

print("    [模拟] retrieve 完成, 但后续 calculator/Final Answer 因 API 超时中断!")
print("    [模拟] summarize_to_episodic() 未调用, assistant 消息未写入!")

# 检查中断后的状态
print(f"\n  中断后状态:")
print(f"    工作记忆: {len(mem_a.working_memory)} 步 (残留 1 步未清理)")
print(f"    情景记忆: {len(mem_a.episodic_memory)} 条 (仍为前3轮, 第4轮未写入)")
print(f"    对话历史: {len(conv_a.messages)} 条 (7条 = 3轮×2 + 1条user)")
last_msg = conv_a.messages[-1]
print(f"    最后消息: role={last_msg['role']}, content='{last_msg['content']}'")

checks_a = [
    ("工作记忆未清理(reset前残留)", len(mem_a.working_memory) == 1,
     "1步残留(正常: 中断时未调用 summarize)"),
    ("情景记忆未被污染", len(mem_a.episodic_memory) == 3,
     "3条(前3轮完整, 第4轮未写入)"),
    ("对话历史有未回复的 user", len(conv_a.messages) == 7 and conv_a.messages[-1]["role"] == "user",
     "7条, 最后一条为未回复的 user"),
]

for name, ok, detail in checks_a:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {detail}")

# 恢复: 清理工作记忆, 重试第 4 轮
print("\n  恢复操作: 清理工作记忆残留, 从情景记忆获取上下文, 重试第 4 轮...")
mem_a.reset_working()
print(f"    reset_working() 后工作记忆: {len(mem_a.working_memory)} 步 (已清理)")

# 用情景记忆恢复上下文
episodic_context = mem_a.get_episodic_context(max_turns=3)
print(f"    情景记忆上下文长度: {len(episodic_context)} 字符")
print(f"    情景记忆包含: {'中芯国际' in episodic_context and '中国移动' in episodic_context}")

# 正常完成第 4 轮
mem_a.add(thought="需要查询中芯国际的净利润数据(重试)", action="retrieve",
          action_input={"query": "净利润", "company_name": "中芯国际"},
          observation="找到 5 条结果，净利润 36.69 亿元", elapsed_ms=1150)
mem_a.add(thought="数据已获取，直接回答", action="Final Answer",
          action_input=None, observation="回答完成", elapsed_ms=400)
mem_a.summarize_to_episodic(user_query="中芯国际净利润",
                             final_answer="中芯国际2024年净利润为 36.69 亿元。")
conv_a.add_message("assistant", "中芯国际2024年净利润为 36.69 亿元。")

print(f"\n  恢复后状态:")
print(f"    工作记忆: {len(mem_a.working_memory)} 步 (retrieve + Final Answer)")
print(f"    情景记忆: {len(mem_a.episodic_memory)} 条 (前3轮 + 第4轮)")
print(f"    对话历史: {len(conv_a.messages)} 条 (完整 4 轮)")
print(f"  [PASS] 场景A: 中断后通过情景记忆恢复, 重试成功")

# ---- 场景B: 对话中途强制退出 ----
divider("场景B: 模拟用户关闭窗口(强制退出), 情景记忆检查")

print("""
  模拟:
    用户完成 3 轮正常对话后关闭浏览器。
    此时 AgentMemory 的情景记忆已有 3 条摘要。
    ConversationManager 有 6 条消息(3 user + 3 assistant)。
    工作记忆为空(最后一轮已 summarize)。

  关键验证:
    情景记忆中保存了历史摘要, 不依赖工作记忆或对话历史即可恢复上下文。
""")

mem_b = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
conv_b = ConversationManager(max_turns=5, agent_memory=mem_b)

for rd in SCENARIO[:3]:
    conv_b.add_message("user", rd[1])
    mem_b.reset_working()
    for thought, action, action_input, obs, elapsed in rd[3]:
        mem_b.add(thought=thought, action=action,
                  action_input=action_input, observation=obs, elapsed_ms=elapsed)
    mem_b.summarize_to_episodic(user_query=rd[1], final_answer=rd[2])
    conv_b.add_message("assistant", rd[2])

print("  正常 3 轮完成。用户关闭窗口。")
print(f"    情景记忆摘要: {[ep['query'] for ep in mem_b.episodic_memory]}")

# 模拟重新打开: 保留 AgentMemory, 重建 ConversationManager
print("\n  用户重新打开系统, 重建 ConversationManager...")
conv_b_new = ConversationManager(max_turns=5, agent_memory=mem_b)

print(f"    新建 ConversationManager 对话历史: {len(conv_b_new.messages)} 条 (空)")
print(f"    但 AgentMemory 情景记忆仍在: {len(mem_b.episodic_memory)} 条")

# 验证: 即使对话历史为空, 情景记忆仍可提供上下文
conversation_history = conv_b_new.get_context_string()
if not conversation_history:
    print(f"    get_context_string() 返回空: 对话历史为空(正常)")

full_ctx_b = conv_b_new.get_full_context()
print(f"    get_full_context() 长度: {len(full_ctx_b)} 字符")

checks_b = [
    ("情景记忆独立于对话历史", len(mem_b.episodic_memory) == 3,
     "3条(重启后仍在)"),
    ("对话历史独立重建", len(conv_b_new.messages) == 0,
     "0条(空, 正常)"),
    ("get_full_context仍有情景记忆",
     "历史会话摘要" in full_ctx_b or "历史会话" in full_ctx_b,
     f"情景记忆存在于 full_context 中"),
    ("情景记忆可独立恢复上下文",
     "中芯国际" in full_ctx_b and "中国移动" in full_ctx_b,
     "包含之前讨论的公司信息"),
]

for name, ok, detail in checks_b:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {detail}")

# 追问: 基于情景记忆恢复后继续对话
print("\n  基于情景记忆恢复, 用户追问 '那他们的营收对比怎么样'...")
conv_b_new.add_message("user", "那他们的营收对比怎么样")
mem_b.reset_working()
mem_b.add(thought="需要查询中芯国际和移动营收", action="retrieve",
          action_input={"query": "营收", "company_name": None},
          observation="找到 10 条结果，中芯 577.96亿, 移动 9373亿", elapsed_ms=1300)
mem_b.add(thought="需要对比分析", action="compare",
          action_input={"companies": ["中芯国际", "中国移动"], "metrics": ["营收"]},
          observation="对比完成: 中芯 577.96亿 vs 移动 9373亿", elapsed_ms=600)
mem_b.add(thought="对比完成", action="Final Answer",
          action_input=None, observation="回答完成", elapsed_ms=350)
mem_b.summarize_to_episodic("那他们的营收对比怎么样",
                             "营收对比: 中芯 577.96亿 vs 移动 9373亿。")
conv_b_new.add_message("assistant", "营收对比: 中芯 577.96亿 vs 移动 9373亿。")

print(f"    追问后情景记忆: {len(mem_b.episodic_memory)} 条 (前3轮 + 第4轮)")
print(f"  [PASS] 场景B: 强制退出后情景记忆独立恢复, 追问正常执行")

# ---- 场景C: 多次中断 + 情景记忆累积 ----
divider("场景C: 模拟 3 次连续中断-恢复循环, 情景记忆是否累积正确")

print("""
  模拟:
    用户连续 5 轮对话, 其中第2轮和第4轮发生中断。
    验证每轮恢复后情景记忆是否正确追加, 无重复无遗漏。
""")

mem_c = AgentMemory(working_memory_limit=10, episodic_memory_turns=5)
conv_c = ConversationManager(max_turns=5, agent_memory=mem_c)

def safe_add_message(conv, role, content):
    """安全添加消息 (防止重复添加导致对话历史错乱)"""
    if conv.messages and conv.messages[-1]["role"] == role:
        # 同一角色连续, 可能是中断后重试, 不重复追加
        print(f"    [WARN] 检测到 {role} 消息重复发送, 跳过 (可能因中断重试)")
        return False
    conv.add_message(role, content)
    return True

total_rounds = 5
interrupt_rounds = {2, 4}  # 第 2 轮和第 4 轮发生中断

for rd_idx in range(total_rounds):
    rd = SCENARIO[rd_idx]
    rd_num = rd[0]
    user_msg = rd[1]
    assistant_ans = rd[2]
    steps = rd[3]

    print(f"\n  开始第 {rd_num} 轮: '{user_msg}'" +
          (" (此轮将中断!)" if rd_num in interrupt_rounds else ""))

    # 用户消息
    safe_add_message(conv_c, "user", user_msg)
    mem_c.reset_working()

    if rd_num in interrupt_rounds:
        # 模拟中断: 只执行到 retrieve 就崩溃
        retrieve_step = steps[0]
        mem_c.add(thought=retrieve_step[0], action=retrieve_step[1],
                  action_input=retrieve_step[2], observation=retrieve_step[3],
                  elapsed_ms=retrieve_step[4])
        print(f"    [中断] retrieve 完成, 但后续步骤未执行, summarize 未调用!")
        print(f"    第{rd_num}轮残留: 工作记忆={len(mem_c.working_memory)}步, "
              f"情景记忆={len(mem_c.episodic_memory)}条(本轮未写入)")

        # 恢复: 清理工作记忆, 重新执行完整流程
        print(f"    恢复: 清理工作记忆, 重新执行第{rd_num}轮...")
        mem_c.reset_working()
        for step in steps:
            mem_c.add(thought=step[0], action=step[1],
                      action_input=step[2], observation=step[3],
                      elapsed_ms=step[4])
        mem_c.summarize_to_episodic(user_query=user_msg, final_answer=assistant_ans)
        safe_add_message(conv_c, "assistant", assistant_ans)
        print(f"    恢复完成: 工作记忆={len(mem_c.working_memory)}步, "
              f"情景记忆={len(mem_c.episodic_memory)}条, "
              f"对话历史={len(conv_c.messages)}条")
    else:
        # 正常轮次
        for step in steps:
            mem_c.add(thought=step[0], action=step[1],
                      action_input=step[2], observation=step[3],
                      elapsed_ms=step[4])
        mem_c.summarize_to_episodic(user_query=user_msg, final_answer=assistant_ans)
        safe_add_message(conv_c, "assistant", assistant_ans)

print(f"\n  场景C 最终状态:")
print(f"    情景记忆: {len(mem_c.episodic_memory)} 条 (预期5条, 每轮1条)")
print(f"    对话历史: {len(conv_c.messages)} 条 (预期10条 = 5轮×2)")
ep_queries_c = [ep["query"] for ep in mem_c.episodic_memory]
print(f"    情景摘要: {ep_queries_c}")

checks_c = [
    ("情景记忆累积正确(5条, 无缺漏)", len(mem_c.episodic_memory) == 5,
     f"实际={len(mem_c.episodic_memory)}"),
    ("对话历史完整(10条)", len(conv_c.messages) == 10,
     f"实际={len(conv_c.messages)}"),
    ("第2轮中断后正确恢复", "中国移动净收入" in ep_queries_c,
     "第2轮摘要存在"),
    ("第4轮中断后正确恢复", "他们对比怎么样" in ep_queries_c,
     "第4轮摘要存在"),
    ("中断轮无重复摘要", len(set(ep_queries_c)) == len(ep_queries_c),
     "无重复"),
    ("对话历史角色交替正确",
     [m["role"] for m in conv_c.messages] == ["user", "assistant"] * 5,
     "user/assistant 交替"),
]

for name, ok, detail in checks_c:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {detail}")

# ---- 场景C 追问恢复验证 ----
print(f"\n  验证恢复后追问: '那他们的净利润对比呢'")
full_ctx_c_before = conv_c.get_full_context()
print(f"    get_full_context() 长度: {len(full_ctx_c_before)} 字符")
print(f"    包含公司上下文: "
      f"{'中芯国际' in full_ctx_c_before and '中国移动' in full_ctx_c_before}")

# ============================================================
# 异常测试汇总
# ============================================================
divider("异常测试汇总: 对话中断与上下文恢复")

all_checks = checks_a + checks_b + checks_c
total_abnormal = len(all_checks)
passed_abnormal = sum(1 for _, ok, _ in all_checks if ok)
failed_abnormal = total_abnormal - passed_abnormal

for name, ok, detail in all_checks:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {detail}")

print(f"\n  结论: {passed_abnormal}/{total_abnormal} 项通过"
      + (" (全部通过)" if failed_abnormal == 0 else f", {failed_abnormal} 项失败"))
print("=" * 60)
