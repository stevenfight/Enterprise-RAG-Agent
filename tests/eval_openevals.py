#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OpenEvals 评测脚本

使用 OpenEvals 的 LLM-as-Judge 方式对 Agent 生成结果进行语义级别的质量评估，
弥补关键词匹配的局限性 (如数字格式差异、语义等价但表述不同等)。

评估维度:
  1. Correctness (正确性) - 答案与参考答案的语义一致性
  2. RAG Groundedness (忠实度) - 答案是否忠实于检索到的来源文档
  3. Answer Relevance (相关性) - 答案是否直接回应用户问题

使用方法:
  cd 项目根目录
  python tests/eval_openevals.py

前置条件:
  1. 已安装 openevals: pip install openevals
  2. 已安装 langchain-community: pip install langchain-community
  3. 已设置 DASHSCOPE_API_KEY 环境变量

参考: CASE-openevals使用/1-correctness.py
"""

import json
import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional

# ---- langchain 1.1.x 兼容性修复 ----
# 在导入 langchain 相关模块前设置必要属性
import langchain
if not hasattr(langchain, "verbose"):
    langchain.verbose = False
if not hasattr(langchain, "debug"):
    langchain.debug = False
if not hasattr(langchain, "llm_cache"):
    langchain.llm_cache = None

# ---- 路径设置 ----
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---- OpenEvals 导入 ----
from openevals.prompts import (
    CORRECTNESS_PROMPT,
    RAG_GROUNDEDNESS_PROMPT,
    ANSWER_RELEVANCE_PROMPT,
)
from openevals.llm import create_llm_as_judge

# ---- LangChain ChatTongyi 导入 (作为评估 LLM) ----
from langchain_community.chat_models import ChatTongyi

# ---- 项目模块导入 ----
from src.agent_core import ReActAgent
from src.agent_memory import AgentMemory
from src.tools import ToolRegistry
from src.tools.retrieve_tool import RetrieveTool
from src.tools.calculator_tool import CalculatorTool
from src.tools.compare_tool import CompareTool
from src.tools.chart_tool import ChartTool
from src.tools.verify_tool import VerifyTool

# ---- 配置 ----
DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_datasets")
GENERATION_DATASET_PATH = os.path.join(DATASET_DIR, "generation_queries.json")

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    # 尝试从 env 文件读取
    env_path = os.path.join(PROJECT_ROOT, "env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DASHSCOPE_API_KEY="):
                    DASHSCOPE_API_KEY = line.split("=", 1)[1].strip()
                    os.environ["DASHSCOPE_API_KEY"] = DASHSCOPE_API_KEY
                    break

if not DASHSCOPE_API_KEY:
    print("[ERROR] 未设置 DASHSCOPE_API_KEY 环境变量")
    print("  请在 env 文件中设置: DASHSCOPE_API_KEY=your-key")
    sys.exit(1)


# ============================================================
# 第一部分: 创建评估 LLM 和评估器
# ============================================================

def create_evaluators():
    """创建 OpenEvals 评估器

    使用 ChatTongyi (qwen-turbo) 作为评估 LLM，
    创建三个评估器: 正确性、忠实度、相关性。

    Returns:
        dict: {"correctness": evaluator, "groundedness": evaluator, "relevance": evaluator}
    """
    print("=" * 60)
    print("[OpenEvals] 创建评估 LLM 和评估器...")
    print("=" * 60)

    # 评估 LLM (使用 qwen-turbo，速度快、成本低)
    eval_llm = ChatTongyi(
        model_name="qwen-turbo",
        dashscope_api_key=DASHSCOPE_API_KEY,
        temperature=0,
    )
    print("[OK] 评估 LLM 创建成功: qwen-turbo")

    # 1. 正确性评估器 - 比较答案与参考答案的语义一致性
    correctness_evaluator = create_llm_as_judge(
        prompt=CORRECTNESS_PROMPT,
        feedback_key="correctness",
        judge=eval_llm,
        continuous=True,
        use_reasoning=False,
    )
    print("[OK] 正确性评估器创建成功")

    # 2. RAG 忠实度评估器 - 检查答案是否忠实于检索到的来源文档
    groundedness_evaluator = create_llm_as_judge(
        prompt=RAG_GROUNDEDNESS_PROMPT,
        feedback_key="groundedness",
        judge=eval_llm,
        continuous=True,
        use_reasoning=False,
    )
    print("[OK] 忠实度评估器创建成功")

    # 3. 答案相关性评估器 - 检查答案是否直接回应用户问题
    relevance_evaluator = create_llm_as_judge(
        prompt=ANSWER_RELEVANCE_PROMPT,
        feedback_key="relevance",
        judge=eval_llm,
        continuous=True,
        use_reasoning=False,
    )
    print("[OK] 相关性评估器创建成功")

    print()
    return {
        "correctness": correctness_evaluator,
        "groundedness": groundedness_evaluator,
        "relevance": relevance_evaluator,
    }


# ============================================================
# 第二部分: 运行 Agent 获取答案
# ============================================================

def create_agent() -> ReActAgent:
    """创建 ReActAgent 实例"""
    registry = ToolRegistry()
    registry.register(RetrieveTool())
    registry.register(CalculatorTool())
    registry.register(CompareTool())
    registry.register(ChartTool())
    registry.register(VerifyTool())

    memory = AgentMemory()
    agent = ReActAgent(
        tool_registry=registry,
        memory=memory,
        max_steps=5,
        temperature=0.3,
        model="qwen-max",
    )
    return agent


_agent_instance: Optional[ReActAgent] = None


def get_agent() -> ReActAgent:
    """获取全局 Agent 实例 (单例)"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = create_agent()
    return _agent_instance


# ============================================================
# 第三部分: 运行 OpenEvals 评测
# ============================================================

def extract_score(result: Any) -> Optional[float]:
    """从 OpenEvals 评估结果中提取分数

    OpenEvals 结果可能是 dict、float 或 tuple 格式。

    Args:
        result: 评估器返回的结果

    Returns:
        分数 (0.0-1.0) 或 None
    """
    if isinstance(result, dict):
        return result.get("score")
    elif isinstance(result, (int, float)):
        return float(result)
    elif isinstance(result, tuple) and len(result) > 0:
        return float(result[0])
    elif hasattr(result, "score"):
        return result.score
    return None


def run_openevals_evaluation(
    test_cases: List[Dict[str, Any]],
    evaluators: Dict[str, Any],
) -> Dict[str, Any]:
    """运行 OpenEvals 评测

    对每条测试用例:
      1. 调用 ReActAgent 获取答案
      2. 用 3 个评估器分别评分
      3. 汇总结果

    Args:
        test_cases: 测试用例列表
        evaluators: 评估器字典

    Returns:
        评测结果汇总
    """
    print("\n" + "=" * 60)
    print("[OpenEvals] 开始评测...")
    print(f"  测试用例数: {len(test_cases)}")
    print(f"  评估维度: correctness, groundedness, relevance")
    print("=" * 60)

    agent = get_agent()
    results = []

    for i, test_case in enumerate(test_cases):
        query = test_case.get("query", "")
        company_name = test_case.get("company_name")
        reference_answer = test_case.get("reference_answer", "")

        print(f"\n[{i+1}/{len(test_cases)}] {test_case.get('id', '')} - {query}")

        # 1. 调用 Agent 获取答案
        try:
            start_time = time.time()
            result = agent.run(query, company_name=company_name)
            elapsed = time.time() - start_time
            answer = result.answer or ""
            sources = []
            # 从 reasoning_chain 中提取检索来源
            if hasattr(result, "reasoning_chain"):
                for step in result.reasoning_chain:
                    obs = step.get("observation", "")
                    if "results" in obs and "来源" in obs:
                        # 简单提取来源信息
                        sources.append(obs[:500])
            context = "\n".join(sources) if sources else answer
        except Exception as e:
            elapsed = 0
            answer = f"执行错误: {str(e)}"
            context = ""
            result = type("R", (), {"success": False, "total_steps": 0})()

        # 2. 评估: 正确性 (与参考答案对比)
        correctness_score = None
        try:
            correctness_result = evaluators["correctness"](
                inputs=query,
                outputs=answer,
                reference_outputs=reference_answer,
            )
            correctness_score = extract_score(correctness_result)
        except Exception as e:
            print(f"  [WARN] 正确性评估失败: {e}")
            correctness_score = 0.0

        # 3. 评估: 忠实度 (答案是否忠实于来源文档)
        # RAG_GROUNDEDNESS_PROMPT 需要 context 参数 (不是 reference_outputs)
        groundedness_score = None
        try:
            groundedness_result = evaluators["groundedness"](
                inputs=query,
                outputs=answer,
                context=context,
            )
            groundedness_score = extract_score(groundedness_result)
        except Exception as e:
            print(f"  [WARN] 忠实度评估失败: {e}")
            groundedness_score = 0.0

        # 4. 评估: 相关性 (答案是否回应了问题)
        relevance_score = None
        try:
            relevance_result = evaluators["relevance"](
                inputs=query,
                outputs=answer,
            )
            relevance_score = extract_score(relevance_result)
        except Exception as e:
            print(f"  [WARN] 相关性评估失败: {e}")
            relevance_score = 0.0

        # 汇总单条结果
        entry = {
            "id": test_case.get("id", ""),
            "query": query,
            "answer": answer[:200] + "..." if len(answer) > 200 else answer,
            "reference_answer": reference_answer[:100] + "..." if len(reference_answer) > 100 else reference_answer,
            "correctness": round(correctness_score, 3) if correctness_score is not None else None,
            "groundedness": round(groundedness_score, 3) if groundedness_score is not None else None,
            "relevance": round(relevance_score, 3) if relevance_score is not None else None,
            "success": result.success if hasattr(result, "success") else False,
            "steps": result.total_steps if hasattr(result, "total_steps") else 0,
            "elapsed": round(elapsed, 2),
        }
        results.append(entry)

        # 打印单条结果
        avg_score = sum(s for s in [correctness_score, groundedness_score, relevance_score] if s is not None) / 3
        status = "PASS" if avg_score >= 0.6 else "FAIL"
        print(f"  -> [{status}] correctness={correctness_score:.2f}, "
              f"groundedness={groundedness_score:.2f}, relevance={relevance_score:.2f}")
        print(f"     answer: {entry['answer'][:80]}...")

    # 汇总统计
    total = len(results)
    valid_correctness = [r["correctness"] for r in results if r["correctness"] is not None]
    valid_groundedness = [r["groundedness"] for r in results if r["groundedness"] is not None]
    valid_relevance = [r["relevance"] for r in results if r["relevance"] is not None]

    summary = {
        "total": total,
        "avg_correctness": round(sum(valid_correctness) / len(valid_correctness), 3) if valid_correctness else 0,
        "avg_groundedness": round(sum(valid_groundedness) / len(valid_groundedness), 3) if valid_groundedness else 0,
        "avg_relevance": round(sum(valid_relevance) / len(valid_relevance), 3) if valid_relevance else 0,
        "pass_count": sum(1 for r in results if r["correctness"] and r["correctness"] >= 0.6),
        "results": results,
    }
    summary["pass_rate"] = round(summary["pass_count"] / total, 2) if total else 0

    # 打印汇总
    print("\n" + "=" * 60)
    print("[OpenEvals 评测汇总]")
    print("=" * 60)
    print(f"  总用例数: {summary['total']}")
    print(f"  通过数: {summary['pass_count']} (通过率: {summary['pass_rate']:.0%})")
    print(f"  平均正确性 (Correctness): {summary['avg_correctness']:.2f}")
    print(f"  平均忠实度 (Groundedness): {summary['avg_groundedness']:.2f}")
    print(f"  平均相关性 (Relevance): {summary['avg_relevance']:.2f}")
    print()

    # 逐维度分析
    print("[维度分析]")
    for dim, key in [("正确性", "correctness"), ("忠实度", "groundedness"), ("相关性", "relevance")]:
        scores = [r[key] for r in results if r[key] is not None]
        if scores:
            low_cases = [r["id"] for r in results if r[key] is not None and r[key] < 0.5]
            print(f"  {dim}: avg={sum(scores)/len(scores):.2f}, "
                  f"min={min(scores):.2f}, max={max(scores):.2f}, "
                  f"低分用例={low_cases if low_cases else '无'}")
    print("=" * 60)

    # 保存报告
    report_path = os.path.join(
        DATASET_DIR,
        f"openevals_report_{time.strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n[INFO] OpenEvals 评测报告已保存: {report_path}")

    return summary


# ============================================================
# 第四部分: 主函数
# ============================================================

def main():
    """主函数: 加载数据集 -> 创建评估器 -> 运行评测"""

    print("=" * 60)
    print("企业级财务年报分析智能RAG Agent - OpenEvals 评测")
    print("=" * 60)
    print()

    # 加载数据集
    if not os.path.exists(GENERATION_DATASET_PATH):
        print(f"[ERROR] 评测数据集不存在: {GENERATION_DATASET_PATH}")
        sys.exit(1)

    with open(GENERATION_DATASET_PATH, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
    print(f"[INFO] 已加载数据集: generation_queries.json, 共 {len(test_cases)} 条用例")

    # 创建评估器
    evaluators = create_evaluators()

    # 运行评测
    summary = run_openevals_evaluation(test_cases, evaluators)

    # 最终结论
    print("\n" + "=" * 60)
    print("[结论]")
    print("=" * 60)
    if summary["avg_correctness"] >= 0.7:
        print("  正确性: 良好 (Agent 生成的答案与参考答案语义一致)")
    elif summary["avg_correctness"] >= 0.5:
        print("  正确性: 一般 (部分答案存在偏差，需优化检索精度)")
    else:
        print("  正确性: 较差 (答案与参考答案差距较大)")

    if summary["avg_groundedness"] >= 0.7:
        print("  忠实度: 良好 (答案忠实于检索到的来源文档)")
    elif summary["avg_groundedness"] >= 0.5:
        print("  忠实度: 一般 (部分答案可能包含未来源的内容)")
    else:
        print("  忠实度: 较差 (答案可能存在幻觉)")

    if summary["avg_relevance"] >= 0.7:
        print("  相关性: 良好 (答案直接回应用户问题)")
    elif summary["avg_relevance"] >= 0.5:
        print("  相关性: 一般 (部分答案偏离用户问题)")
    else:
        print("  相关性: 较差 (答案未能回应用户问题)")
    print("=" * 60)


if __name__ == "__main__":
    main()
