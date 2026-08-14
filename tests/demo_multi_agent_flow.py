# -*- coding: utf-8 -*-
"""
多 Agent 路由流程本地 Mock 演示

目标：在不触发真实 LLM / 网络 / FAISS 的前提下，直观展示一次多公司对比查询
从「路由」到「最终汇总」的完整数据流转。

本演示 Mock 掉两个边界：
  1. LLM（_call_llm）：返回预设的 delegate / Final Answer 响应
  2. Worker（_create_agent）：返回预设答案的 MockWorker

其余逻辑均为真实执行：
  QueryRouter 正则路由 -> OrchestratorAgent ReAct 循环 -> DelegateTool 依赖分组
  -> 并行/串行调度 -> SharedMemory 写回 -> 最终汇总

编码: UTF-8
"""

import json
import logging
import sys
import threading
from pathlib import Path

# 将项目根目录加入 sys.path，使直接运行本脚本时 `import src` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch

# 在导入 src.* 之前就关闭 INFO 级别日志，避免内部模块日志淹没演示输出。
# logging.disable 是全局 manager 级禁用，即使模块加载时调用 logger.setLevel(INFO)
# 也不会将其推翻，从而彻底屏蔽 import 阶段与运行阶段的所有 INFO 噪音。
logging.disable(logging.INFO)

from src.agent_core import AgentResult
from src.agent_registry import AgentRegistry, AgentCapability
from src.shared_memory import SharedMemory
from src.tools.delegate_tool import DelegateTool
from src.orchestrator_agent import OrchestratorAgent
from src.router import QueryRouter


_print_lock = threading.Lock()


def log(msg=""):
    """带锁打印，避免并行 Worker 输出串行错乱"""
    with _print_lock:
        print(msg)


def section(title):
    log()
    log("=" * 74)
    log(title)
    log("=" * 74)


def step(n, title):
    log()
    log(f"[步骤 {n}] {title}")
    log("-" * 74)


QUERY = "中国移动和中国联通2024年营收对比"

WORKER_NAMES = ["DataAgent", "CalcAgent", "CompareAgent", "ChartAgent", "VerifyAgent"]

# Mock LLM 拆解出的子任务（展示分组与 delegate 响应共用同一份数据）
TASKS = [
    {"agent": "DataAgent", "task": "检索中国移动2024年营业收入", "company_name": "中国移动"},
    {"agent": "DataAgent", "task": "检索中国联通2024年营业收入", "company_name": "中国联通"},
    {"agent": "CalcAgent", "task": "计算两家运营商营收合计与差额"},
    {"agent": "CompareAgent", "task": "对比中国移动与中国联通2024年营收"},
    {"agent": "ChartAgent", "task": "生成两家运营商营收对比柱状图"},
    {"agent": "VerifyAgent", "task": "核验营收数据与计算结果的正确性"},
]


def make_registry():
    """注册 5 个 Worker 能力"""
    registry = AgentRegistry()
    for name in WORKER_NAMES:
        registry.register(AgentCapability(
            name=name,
            description=f"{name} 能力描述",
            tools=["retrieve"],
        ))
    return registry


class MockWorker:
    """模拟 Worker Agent：真实 run 接口，返回预设答案"""

    def __init__(self, name):
        self.name = name

    def run(self, query="", company_name="", shared_context=""):
        answer = self._answer_for(company_name)
        ctx = shared_context if shared_context else "（无上游结果）"
        ctx_lines = "\n".join(f"        | {line}" for line in ctx.splitlines())

        block = (
            f"    [{self.name}] 收到委托任务\n"
            f"        query       = {query}\n"
            f"        company     = {company_name or '(未指定)'}\n"
            f"        上游上下文  =\n{ctx_lines}\n"
            f"        返回答案    = {answer}"
        )
        log(block)
        return AgentResult(
            answer=answer,
            success=True,
            reasoning_chain=[{
                "step": 1,
                "thought": f"{self.name} 完成子任务",
                "action": "Final Answer",
                "action_input": answer,
                "observation": "",
                "elapsed_ms": 5.0,
            }],
            total_steps=1,
            total_elapsed_ms=5.0,
            sources=[{"source": "2024年年报", "company_name": company_name or self.name}],
            total_tokens=120,
        )

    def _answer_for(self, company_name):
        if self.name == "DataAgent":
            if "移动" in (company_name or ""):
                return "中国移动2024年营业收入 10,407.59亿元"
            if "联通" in (company_name or ""):
                return "中国联通2024年营业收入 3,895.75亿元"
            return "检索完成"
        if self.name == "CalcAgent":
            return "两家运营商营收合计 14,303.34亿元，差额 6,511.84亿元"
        if self.name == "CompareAgent":
            return "中国移动营收约为中国联通的 2.67 倍，领先 6,511.84亿元"
        if self.name == "ChartAgent":
            return "已生成营收对比柱状图（data/charts/营收对比_中国移动_中国联通.png）"
        if self.name == "VerifyAgent":
            return "核验通过：数据来源一致，计算无误"
        return "完成"


def main():
    section("多 Agent 路由流程 Mock 演示")
    log(f"演示查询: {QUERY}")

    # 步骤 1：路由
    step(1, "第一层路由：QueryRouter 判断查询复杂度")
    router = QueryRouter(turbo_llm=MagicMock())
    route_result = router.route(QUERY)
    route_dict = route_result.to_dict()
    log(f"    路由模式: {route_dict['mode']}")
    log(f"    路由来源: {route_dict['trace']}（正则命中，未调用 LLM）")
    log(f"    决策说明: {route_dict['reasoning']}")
    cat = route_dict.get("category", {})
    log(f"    分类详情: 类型={cat.get('type')}, 公司={cat.get('companies')}, "
        f"指标={cat.get('metrics')}, 年份={cat.get('years')}")
    log(f"              需要图表={cat.get('need_chart')}, "
        f"需要计算={cat.get('need_calculate')}, 需要对比={cat.get('need_compare')}")

    # 步骤 2：Orchestrator 初始化
    step(2, "OrchestratorAgent 初始化（注册 Worker 能力）")
    registry = make_registry()
    sm = SharedMemory()
    delegate = DelegateTool(agent_registry=registry, shared_memory=sm)

    with patch("src.agent_core.get_api_key", return_value="demo-mock-key"):
        orch = OrchestratorAgent(
            delegate_tool=delegate,
            agent_registry=registry,
            shared_memory=sm,
        )

    log(f"    Orchestrator 持有的工具: {orch.tool_registry.list_all()}")
    log(f"    模型={orch.model}, 温度={orch.temperature}, 最大步数={orch.max_steps}")
    log("    注入到 System Prompt 的 Worker 描述:")
    for line in orch._agent_descriptions.splitlines():
        log(f"      {line}")

    # 步骤 3：任务拆解
    step(3, "任务拆解：Orchestrator 将查询拆解为子任务")
    log(f"    拆解出的子任务数: {len(TASKS)}")
    for i, t in enumerate(TASKS, 1):
        company = f"（公司: {t['company_name']}）" if t.get("company_name") else ""
        log(f"      {i}. {t['agent']}: {t['task']}{company}")

    # 步骤 4：依赖分组
    step(4, "依赖分组：DelegateTool 按 Agent 类型分批")
    batches = delegate._group_by_dependency(TASKS)
    for idx, batch in enumerate(batches, 1):
        names = [t["agent"] for t in batch]
        label = "并行批（无依赖）" if idx == 1 else "下游批（依赖上游）"
        log(f"      批次{idx} [{label}]: {names}")

    # 步骤 5：真实执行
    step(5, "真实执行：OrchestratorAgent.run()（Mock LLM + Mock Worker）")

    # Mock Worker 创建：_create_agent 返回预设答案的 MockWorker，不触发真实检索/LLM
    delegate._create_agent = MagicMock(side_effect=lambda cap: MockWorker(cap.name))

    delegate_response = (
        "Thought: 需要对比中国移动和中国联通的2024年营业收入，先并行检索两家数据，再计算、对比、画图、核验。\n"
        "Action: delegate\n"
        f"Action Input: {json.dumps({'tasks': TASKS}, ensure_ascii=False)}"
    )
    final_response = (
        "Thought: 已完成检索、计算、对比、画图和核验。\n"
        "Final Answer: 中国移动2024年营业收入 10,407.59亿元，中国联通 3,895.75亿元。"
        "中国移动领先，营收约为中国联通的 2.67 倍。对比柱状图已生成，数据核验通过。"
    )
    orch._call_llm = MagicMock(side_effect=[delegate_response, final_response])

    log("    _call_llm 第 1 次 -> 返回 delegate 动作（任务拆解）")
    log("    _call_llm 第 2 次 -> 返回 Final Answer（最终汇总）")
    log()
    log("    > OrchestratorAgent.run() 开始 ...")
    result = orch.run(QUERY)
    log("    > OrchestratorAgent.run() 结束")

    # 步骤 6：SharedMemory 最终状态
    step(6, "SharedMemory 最终状态（所有 Worker 结果已写回）")
    for name, r in sm.agent_outputs.items():
        log(f"      {name}: {r.answer}")
    log(f"    聚合 Token 用量: {sm.get_total_tokens()}")
    log(f"    执行流水记录数: {len(sm.get_execution_log())}")

    # 步骤 7：最终汇总
    step(7, "最终汇总结果（AgentResult）")
    log(f"    success: {result.success}")
    log(f"    answer: {result.answer}")
    log(f"    推理链步骤数: {len(result.reasoning_chain)}")
    for item in result.reasoning_chain:
        log(f"      step{item['step']}: action={item['action']}")

    section("演示结束")


if __name__ == "__main__":
    main()
