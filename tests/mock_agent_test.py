# -*- coding: utf-8 -*-
"""
Mock 测试脚本: 验证 ReAct Agent 核心循环（不依赖真实 LLM API）

功能：
  1. 用 MockLLM 替代真实 DashScope API 调用
  2. 用 MockRetrieveTool 模拟检索工具
  3. 完整演示 Thought → Action → Observation → Final Answer 循环
  4. 全部日志打印到控制台，方便理解流程

运行方式:
  cd 项目根目录
  python tests/mock_agent_test.py

输出:
  - 控制台日志（完整推理链）
  - 最终答案（模拟输出）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import logging
import time

# ============================================================
# 配置日志格式
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)-12s] [%(levelname)-5s] %(message)s",
    datefmt="%H:%M:%S",
)

# ============================================================
# Mock 工具: 模拟财务数据检索
# ============================================================
from tools import BaseTool, ToolResult, ToolRegistry

MOCK_FINANCIAL_DATA = {
    "中芯国际": {
        "2024": {
            "营收": "营业收入 1250.38 亿元",
            "净利润": "归属于母公司股东的净利润 85.26 亿元",
            "研发费用": "研发投入 152.40 亿元",
        },
        "2023": {
            "营收": "营业收入 1155.34 亿元",
            "净利润": "归属于母公司股东的净利润 72.18 亿元",
        },
    },
    "中国移动": {
        "2024": {
            "营收": "营业收入 10093 亿元",
            "净利润": "归属于母公司股东的净利润 1384 亿元",
        },
        "2023": {
            "营收": "营业收入 9373 亿元",
            "净利润": "归属于母公司股东的净利润 1318 亿元",
        },
    },
    "中国联通": {
        "2024": {
            "营收": "营业收入 3877 亿元",
            "净利润": "归属于母公司股东的净利润 206 亿元",
        },
    },
    "中国电信": {
        "2024": {
            "营收": "营业收入 5299 亿元",
            "净利润": "归属于母公司股东的净利润 318 亿元",
        },
    },
}


class MockRetrieveTool(BaseTool):
    """模拟检索工具: 从本地字典中查找财务数据"""

    name = "retrieve"
    description = "从企业年报数据库中检索财务数据"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索关键词"},
            "company_name": {"type": "string", "description": "公司名称（可选）"},
            "top_n": {"type": "integer", "description": "返回数量，默认 3"},
        },
        "required": ["query"],
    }

    def run(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        company_name = kwargs.get("company_name", None)
        top_n = kwargs.get("top_n", 3)

        # 从 Mock 数据中查找
        results = []
        for comp, years in MOCK_FINANCIAL_DATA.items():
            if company_name and comp != company_name:
                continue
            for year, metrics in years.items():
                for metric_name, metric_value in metrics.items():
                    # 简单关键词匹配
                    if any(kw in query for kw in [metric_name, comp, year]):
                        results.append({
                            "company_name": comp,
                            "year": year,
                            "metric": metric_name,
                            "value": metric_value,
                            "source": f"{comp}{year}年年度报告 第{10 + len(results)}页",
                        })

        # 取 top_n
        results = results[:max(top_n, 1)]

        if not results:
            return ToolResult(
                success=True,
                data={"query": query, "results": [], "message": "未找到相关数据"}
            )

        return ToolResult(
            success=True,
            data={"query": query, "results": results, "count": len(results)}
        )


# ============================================================
# Mock LLM: 返回预设的 ReAct 格式响应
# ============================================================
class MockReActAgent:
    """
    Mock Agent: 不调用真实 LLM，用预设响应模拟 ReAct 推理过程。
    用于验证 Agent 核心框架（ToolRegistry、AgentMemory、ReAct 循环）的集成逻辑。
    """

    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.tool_registry.register(MockRetrieveTool())

        from agent_memory import AgentMemory
        self.memory = AgentMemory()

        self.max_steps = 5
        self.reasoning_chain = []

    def run_simulation(self, query: str, company_name: str = None) -> dict:
        """
        模拟完整的 ReAct 推理过程。

        使用预设的 LLM 响应序列:
          第 1 步: 检索数据
          第 2 步: 确认数据充分，输出 Final Answer
        """
        print("\n" + "=" * 60)
        print("  Mock Agent ReAct 循环测试")
        print("  查询: {}{}".format(
            query,
            f" (公司: {company_name})" if company_name else ""
        ))
        print("=" * 60)

        self.memory.reset_working()

        # ============================================================
        # 第 1 步: 模拟 LLM 生成 Thought + Action
        # ============================================================
        step = 1
        print(f"\n--- 步骤 {step}/{self.max_steps}: LLM 响应 ---")
        llm_response_step1 = (
            "Thought: 用户询问中芯国际2024年的营收数据，我需要从年报数据库中检索相关信息\n"
            "Action: retrieve\n"
            "Action Input: {\"query\": \"中芯国际 2024 营收\", \"company_name\": \"中芯国际\", \"top_n\": 3}"
        )
        print(f"  [LLM 输出] {llm_response_step1}")

        # 解析
        thought1, action1, action_input1 = "用户询问中芯国际2024年营收数据", "retrieve", {
            "query": "中芯国际 2024 营收",
            "company_name": company_name or "中芯国际",
            "top_n": 3,
        }

        # 执行工具
        print(f"\n  [工具执行] {action1}({action_input1})")
        result1 = self.tool_registry.execute(action1, **action_input1)
        observation1 = result1.to_observation()
        print(f"  [观察结果] {observation1[:200]}...")

        # 写入记忆
        self.memory.add(
            thought=thought1,
            action=action1,
            action_input=action_input1,
            observation=observation1,
            elapsed_ms=150,
        )
        self.reasoning_chain.append({
            "step_number": step,
            "thought": thought1,
            "action": action1,
            "action_input": action_input1,
            "observation": observation1,
        })

        # ============================================================
        # 第 2 步: 模拟 LLM 认为数据充分，输出 Final Answer
        # ============================================================
        step = 2
        print(f"\n--- 步骤 {step}/{self.max_steps}: LLM 响应 ---")
        llm_response_step2 = (
            "Thought: 已从年报中获取中芯国际2024年营收为1250.38亿元，信息充分，可以给出最终答案\n"
            "Final Answer: 根据中芯国际2024年年度报告，公司实现营业收入1250.38亿元。"
        )
        print(f"  [LLM 输出] {llm_response_step2}")

        # 解析: 检测到 Final Answer
        thought2 = "已获取中芯国际2024年营收数据"
        final_answer = "根据中芯国际2024年年度报告，公司实现营业收入1250.38亿元。"

        self.memory.add(
            thought=thought2,
            action="Final Answer",
            action_input=final_answer,
            observation="推理完成",
            elapsed_ms=80,
        )

        # 写入情景记忆
        self.memory.summarize_to_episodic(query, final_answer)

        # ============================================================
        # 输出最终结果
        # ============================================================
        print("\n" + "=" * 60)
        print("  推理完成")
        print("=" * 60)
        print(f"\n  最终答案:\n  {final_answer}")

        print(f"\n  推理链 (共 {len(self.reasoning_chain)} 步):")
        for rc in self.reasoning_chain:
            print(f"    步骤 {rc['step_number']}:")
            print(f"      Thought: {rc['thought']}")
            print(f"      Action : {rc['action']}")
            print(f"      Obs    : {rc['observation'][:80]}...")

        print(f"\n  工作记忆: {len(self.memory.working_memory)} 条记录")
        print(f"  情景记忆: {len(self.memory.episodic_memory)} 条摘要")

        return {
            "answer": final_answer,
            "steps": len(self.reasoning_chain),
            "reasoning_chain": self.reasoning_chain,
        }


# ============================================================
# 多步推理场景: 模拟"中国移动和中国联通营收对比"
# ============================================================
def run_complex_simulation():
    """复杂查询: 需要多步检索的模拟"""
    print("\n\n" + "#" * 60)
    print("#  复杂查询测试: 多公司对比")
    print("#" * 60)

    registry = ToolRegistry()
    registry.register(MockRetrieveTool())

    from agent_memory import AgentMemory
    memory = AgentMemory()

    reasoning_chain = []

    # 第 1 步: 检索中国移动营收
    step = 1
    print(f"\n步骤 {step}: 检索中国移动2024年营收")
    result1 = registry.execute(
        "retrieve", query="中国移动 2024 营收", company_name="中国移动", top_n=1
    )
    obs1 = result1.to_observation()
    print(f"  Observation: {obs1[:120]}...")
    memory.add(
        thought="需要先查中国移动2024年营收",
        action="retrieve",
        action_input={"query": "中国移动 2024 营收", "company_name": "中国移动"},
        observation=obs1,
        elapsed_ms=140,
    )
    reasoning_chain.append({
        "step_number": step, "action": "retrieve(中国移动)", "observation": obs1,
    })

    # 第 2 步: 检索中国联通营收
    step = 2
    print(f"\n步骤 {step}: 检索中国联通2024年营收")
    result2 = registry.execute(
        "retrieve", query="中国联通 2024 营收", company_name="中国联通", top_n=1
    )
    obs2 = result2.to_observation()
    print(f"  Observation: {obs2[:120]}...")
    memory.add(
        thought="还需要中国联通2024年营收数据",
        action="retrieve",
        action_input={"query": "中国联通 2024 营收", "company_name": "中国联通"},
        observation=obs2,
        elapsed_ms=130,
    )
    reasoning_chain.append({
        "step_number": step, "action": "retrieve(中国联通)", "observation": obs2,
    })

    # 第 3 步: 对比结果，输出 Final Answer
    step = 3
    print(f"\n步骤 {step}: 对比生成结论")
    final_answer = (
        "对比结果：\n"
        "  中国移动 2024年营收: 10093 亿元\n"
        "  中国联通 2024年营收: 3877 亿元\n"
        "  移动营收约为联通的 2.6 倍"
    )
    memory.add(
        thought="已获取两家公司营收数据，可以对比",
        action="Final Answer",
        action_input=final_answer,
        observation="推理完成",
        elapsed_ms=50,
    )

    memory.summarize_to_episodic("中国移动和中国联通营收对比", final_answer)

    print(f"\n  最终答案:\n  {final_answer}")
    print(f"\n  推理链: 共 {len(reasoning_chain)} 步")
    print(f"  情景记忆轮数: {len(memory.episodic_memory)}")

    print(f"\n  情景记忆上下文:\n{memory.get_episodic_context()}")


# ============================================================
# 测试入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Mock Agent ReAct 循环集成测试")
    print("  目的: 验证 ToolRegistry + AgentMemory + ReAct 循环 的集成逻辑")
    print("  注意: 不调用真实 LLM API，使用预设响应模拟")
    print("=" * 60)

    # 测试 1: 简单查询
    print("\n\n>>> 测试 1: 简单单步查询 <<<")
    agent = MockReActAgent()
    agent.run_simulation("中芯国际2024年营收是多少", company_name="中芯国际")

    # 测试 2: 工具未注册
    print("\n\n>>> 测试 2: 工具未注册时的错误处理 <<<")
    from tools import ToolRegistry, BaseTool
    registry = ToolRegistry()
    result = registry.execute("not_exist_tool", query="测试")
    print(f"  执行结果: success={result.success}, error={result.error}")

    # 测试 3: 空工具注册表
    print("\n\n>>> 测试 3: 空工具注册表 <<<")
    empty_registry = ToolRegistry()
    print(f"  工具列表: {empty_registry.list_all()}")
    print(f"  工具描述: {empty_registry.get_tool_descriptions()}")

    # 测试 4: 记忆系统
    print("\n\n>>> 测试 4: 记忆系统读写 <<<")
    from agent_memory import AgentMemory
    mem = AgentMemory(working_memory_limit=3, enable_long_term=True)
    mem.add("测试思考1", "retrieve", {"q": "test"}, "结果1", 100)
    mem.add("测试思考2", "calculate", {"expr": "1+1"}, "结果2", 50)
    mem.add("测试思考3", "retrieve", {"q": "test2"}, "结果3", 80)
    mem.add("测试思考4", "retrieve", {"q": "test3"}, "结果4", 90)
    print(f"  工作记忆条目数 (上限3): {len(mem.working_memory)}")
    print(f"  工作记忆上下文:\n{mem.get_working_context()}")

    mem.summarize_to_episodic("测试查询", "测试答案123")
    print(f"  情景记忆条目数: {len(mem.episodic_memory)}")
    print(f"  情景记忆上下文:\n{mem.get_episodic_context()}")

    company_info = mem.get_long_term("company_info", "中芯国际")
    print(f"  长期记忆查询(中芯国际): {company_info}")

    long_none = mem.get_long_term("company_info", "特斯拉")
    print(f"  长期记忆查询(未知公司): {long_none}")

    # 测试 5: 复杂多步查询
    print("\n\n>>> 测试 5: 复杂多步查询 (多公司对比) <<<")
    run_complex_simulation()

    # 回归测试验证
    print("\n\n>>> 测试 6: 管道回归验证 <<<")
    try:
        from conversation import ConversationManager
        conv = ConversationManager()
        conv.add_message("user", "测试")
        conv.add_message("assistant", "回复")
        history = conv.get_history(1)
        print(f"  ConversationManager 正常: {len(history)} 条历史 (预期 2)")
    except Exception as e:
        print(f"  ConversationManager 异常: {e}")

    print("\n" + "=" * 60)
    print("  全部 Mock 测试完成")
    print("=" * 60)
