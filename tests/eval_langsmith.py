#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LangSmith 测试与评估脚本

本脚本提供使用 LangSmith 进行 Agent 测试和评估的完整流程：
  1. 从本地 JSON 文件加载评测数据集
  2. 将数据集上传到 LangSmith 平台
  3. 使用 ReActAgent 运行每条测试用例
  4. 通过自定义评估器对结果进行评分
  5. 在 LangSmith Dashboard 查看可视化报告

使用方法:
  cd 项目根目录
  python tests/eval_langsmith.py

前置条件:
  1. 已安装 langsmith 包: pip install langsmith
  2. 已设置环境变量:
     - LANGSMITH_API_KEY (从 https://smith.langchain.com 获取)
     - LANGCHAIN_TRACING_V2=true
  3. 已设置 DashScope API Key

参考项目: CASE-投顾AI助手（效果评估）/2-langsmith_testing_evaluation.py
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---- 路径设置 ----
# 确保能导入 src 模块
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---- LangSmith 导入 ----
from langsmith import Client
from langsmith.evaluation import evaluate
from langsmith.schemas import Example, Run

# ---- 项目模块导入 ----
from src.monitoring import is_available, get_client, LANGSMITH_PROJECT
from src.agent_core import ReActAgent
from src.agent_memory import AgentMemory
from src.tools import ToolRegistry
from src.tools.retrieve_tool import RetrieveTool
from src.tools.calculator_tool import CalculatorTool
from src.tools.compare_tool import CompareTool
from src.tools.chart_tool import ChartTool
from src.tools.verify_tool import VerifyTool

# ---- 评测数据集路径 ----
DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_datasets")
GENERATION_DATASET_PATH = os.path.join(DATASET_DIR, "generation_queries.json")
RETRIEVAL_DATASET_PATH = os.path.join(DATASET_DIR, "retrieval_queries.json")

# ---- LangSmith 数据集名称 ----
LANGSMITH_DATASET_NAME = "financial-rag-agent-eval"


# ============================================================
# 第一部分: 数据集加载与上传
# ============================================================

def load_local_dataset(file_path: str) -> List[Dict[str, Any]]:
    """从本地 JSON 文件加载评测数据集

    Args:
        file_path: JSON 文件路径

    Returns:
        评测用例列表
    """
    if not os.path.exists(file_path):
        print(f"[ERROR] 评测数据集文件不存在: {file_path}")
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"[INFO] 已加载本地数据集: {os.path.basename(file_path)}, 共 {len(data)} 条用例")
    return data


def upload_dataset_to_langsmith(
    client: Client,
    test_cases: List[Dict[str, Any]],
    dataset_name: str = LANGSMITH_DATASET_NAME,
) -> Optional[str]:
    """将本地评测数据集上传到 LangSmith 平台

    如果数据集已存在且包含用例，则跳过上传。
    否则创建新数据集并添加所有测试用例。

    Args:
        client: LangSmith Client 实例
        test_cases: 测试用例列表
        dataset_name: LangSmith 数据集名称

    Returns:
        数据集名称 (成功时) 或 None (失败时)
    """
    if not client:
        print("[ERROR] LangSmith Client 未初始化")
        return None

    if not test_cases:
        print("[ERROR] 测试用例列表为空")
        return None

    try:
        # 检查数据集是否已存在
        dataset_exists = False
        existing_count = 0
        try:
            existing_examples = list(client.list_examples(dataset_name=dataset_name))
            existing_count = len(existing_examples)
            if existing_count > 0:
                dataset_exists = True
                print(f"[LangSmith] 数据集已存在: {dataset_name} (现有 {existing_count} 条用例)")
        except Exception:
            pass

        # 数据集不存在时创建
        if not dataset_exists:
            try:
                client.create_dataset(
                    dataset_name=dataset_name,
                    description="企业级财务年报分析智能RAG Agent 评测数据集",
                )
                print(f"[LangSmith] 数据集已创建: {dataset_name}")
            except Exception as create_error:
                error_msg = str(create_error)
                if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                    print(f"[LangSmith] 数据集已存在: {dataset_name}")
                else:
                    raise create_error

        # 添加测试用例
        if existing_count == 0:
            print(f"[LangSmith] 正在上传 {len(test_cases)} 条测试用例...")
            added_count = 0
            for test_case in test_cases:
                try:
                    inputs = {
                        "query": test_case.get("query", ""),
                        "company_name": test_case.get("company_name"),
                    }
                    outputs = {
                        "reference_answer": test_case.get("reference_answer", ""),
                        "should_contain": test_case.get("should_contain", []),
                        "category": test_case.get("category", ""),
                        "description": test_case.get("description", ""),
                    }
                    client.create_example(
                        inputs=inputs,
                        outputs=outputs,
                        dataset_name=dataset_name,
                    )
                    added_count += 1
                except Exception as e:
                    error_msg = str(e)
                    if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                        continue
                    else:
                        print(f"  [WARN] 添加用例失败: {error_msg}")

            print(f"[LangSmith] 上传完成: 新增 {added_count}/{len(test_cases)} 条用例")
        else:
            print(f"[LangSmith] 数据集已有 {existing_count} 条用例，跳过上传")

        # 验证数据集
        final_examples = list(client.list_examples(dataset_name=dataset_name))
        print(f"[LangSmith] 数据集准备完成: {dataset_name} (共 {len(final_examples)} 条用例)")
        return dataset_name

    except Exception as e:
        print(f"[ERROR] 数据集上传失败: {str(e)}")
        traceback.print_exc()
        return None


# ============================================================
# 第二部分: 自定义评估器
# ============================================================

def _safe_get_inputs(example) -> Dict[str, Any]:
    """安全获取 Example 的 inputs 字段"""
    try:
        if hasattr(example, "inputs") and example.inputs:
            return example.inputs if isinstance(example.inputs, dict) else {}
        if isinstance(example, dict) and "inputs" in example:
            return example["inputs"] if isinstance(example["inputs"], dict) else {}
    except Exception:
        pass
    return {}


def _safe_get_outputs(example) -> Dict[str, Any]:
    """安全获取 Example 的 outputs 字段"""
    try:
        if hasattr(example, "outputs") and example.outputs:
            return example.outputs if isinstance(example.outputs, dict) else {}
        if isinstance(example, dict) and "outputs" in example:
            return example["outputs"] if isinstance(example["outputs"], dict) else {}
    except Exception:
        pass
    return {}


def _safe_get_run_outputs(run) -> Dict[str, Any]:
    """安全获取 Run 的 outputs 字段"""
    try:
        if run.outputs:
            return run.outputs if isinstance(run.outputs, dict) else {}
    except Exception:
        pass
    return {}


def answer_completeness_eval(inputs: dict, outputs: dict, reference_outputs: dict) -> Dict[str, Any]:
    """答案完整性评估器 (函数式)

    检查 Agent 生成的答案是否包含期望的关键词。
    评分 = 命中关键词数 / 期望关键词总数
    """
    try:
        expected_keywords = reference_outputs.get("should_contain", [])

        if not expected_keywords:
            return {
                "key": "answer_completeness",
                "score": None,
                "comment": "未指定期望关键词",
            }

        answer = outputs.get("answer", "")

        if not answer:
            return {
                "key": "answer_completeness",
                "score": 0.0,
                "comment": "Agent 未返回答案",
            }

        # 检查关键词命中情况
        answer_lower = answer.lower()
        found_keywords = [kw for kw in expected_keywords if kw.lower() in answer_lower]
        completeness = len(found_keywords) / len(expected_keywords) if expected_keywords else 0

        return {
            "key": "answer_completeness",
            "score": completeness,
            "comment": f"命中 {len(found_keywords)}/{len(expected_keywords)} 个关键词: {found_keywords}",
        }
    except Exception as e:
        return {
            "key": "answer_completeness",
            "score": 0.0,
            "comment": f"评估错误: {str(e)}",
        }


def answer_success_eval(inputs: dict, outputs: dict, reference_outputs: dict) -> Dict[str, Any]:
    """答案成功率评估器 (函数式)

    检查 Agent 是否成功完成任务 (success=True)。
    """
    try:
        success = outputs.get("success", False)

        return {
            "key": "answer_success",
            "score": 1.0 if success else 0.0,
            "comment": "Agent 执行成功" if success else "Agent 执行失败",
        }
    except Exception as e:
        return {
            "key": "answer_success",
            "score": 0.0,
            "comment": f"评估错误: {str(e)}",
        }


def answer_length_eval(inputs: dict, outputs: dict, reference_outputs: dict) -> Dict[str, Any]:
    """答案长度评估器 (函数式)

    检查答案长度是否在合理范围内 (10-2000 字符)。
    过短可能信息不足，过长可能冗余。
    """
    try:
        answer = outputs.get("answer", "")

        if not answer:
            return {
                "key": "answer_length",
                "score": 0.0,
                "comment": "答案为空",
            }

        length = len(answer)
        if length < 10:
            score = 0.3
            comment = f"答案过短 ({length} 字符)"
        elif length > 2000:
            score = 0.5
            comment = f"答案过长 ({length} 字符)"
        else:
            score = 1.0
            comment = f"答案长度合理 ({length} 字符)"

        return {
            "key": "answer_length",
            "score": score,
            "comment": comment,
        }
    except Exception as e:
        return {
            "key": "answer_length",
            "score": 0.0,
            "comment": f"评估错误: {str(e)}",
        }


# ============================================================
# 第三部分: Agent 目标函数
# ============================================================

def create_agent() -> ReActAgent:
    """创建 ReActAgent 实例

    初始化工具注册表和记忆系统，返回一个可执行的 Agent。
    """
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


# 全局 Agent 实例 (避免每次评估都重新初始化)
_agent_instance: Optional[ReActAgent] = None


def get_agent() -> ReActAgent:
    """获取全局 Agent 实例 (单例模式)"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = create_agent()
    return _agent_instance


def target_function(example: Dict[str, Any]) -> Dict[str, Any]:
    """LangSmith 评估目标函数

    接收 LangSmith 传入的 example，调用 ReActAgent 执行查询，
    返回结构化结果供评估器使用。

    Args:
        example: 包含 inputs 的字典 (query, company_name)

    Returns:
        包含 answer, success, steps, elapsed 等字段的结果字典
    """
    try:
        inputs = example if isinstance(example, dict) else {}
        if "inputs" in inputs:
            inputs = inputs["inputs"]

        query = inputs.get("query", "")
        company_name = inputs.get("company_name")

        if not query or not query.strip():
            return {
                "answer": "查询为空，无法处理",
                "success": False,
                "steps": 0,
                "elapsed": 0,
                "error": "empty_query",
            }

        # 调用 Agent
        agent = get_agent()
        start_time = time.time()
        result = agent.run(query, company_name=company_name)
        elapsed = time.time() - start_time

        return {
            "answer": result.answer or "",
            "success": result.success,
            "steps": result.total_steps,
            "elapsed": round(elapsed, 2),
            "forced_stop": result.forced_stop,
        }
    except Exception as e:
        return {
            "answer": f"执行错误: {str(e)}",
            "success": False,
            "steps": 0,
            "elapsed": 0,
            "error": str(e),
        }


# ============================================================
# 第四部分: 本地评测 (不依赖 LangSmith 平台)
# ============================================================

def run_local_evaluation(test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """在本地运行评测 (不上传到 LangSmith)

    当 LangSmith 不可用时使用此模式。
    逐条运行测试用例并使用评估器评分，输出本地报告。

    Args:
        test_cases: 测试用例列表

    Returns:
        评测结果汇总
    """
    print("\n" + "=" * 60)
    print("[本地评测模式] LangSmith 未启用，运行本地评测")
    print("=" * 60)

    agent = get_agent()
    results = []

    for i, test_case in enumerate(test_cases):
        query = test_case.get("query", "")
        company_name = test_case.get("company_name")
        expected_keywords = test_case.get("should_contain", [])
        reference_answer = test_case.get("reference_answer", "")

        print(f"\n[{i+1}/{len(test_cases)}] {test_case.get('id', '')} - {query}")

        try:
            start_time = time.time()
            result = agent.run(query, company_name=company_name)
            elapsed = time.time() - start_time
            answer = result.answer or ""
        except Exception as e:
            elapsed = 0
            answer = f"执行错误: {str(e)}"
            result = type("R", (), {"success": False, "total_steps": 0})()

        # 评估: 关键词覆盖率
        answer_lower = answer.lower()
        found_keywords = [kw for kw in expected_keywords if kw.lower() in answer_lower]
        completeness = len(found_keywords) / len(expected_keywords) if expected_keywords else 0

        # 评估: 成功率
        success = result.success if hasattr(result, "success") else False

        # 评估: 答案长度
        answer_length = len(answer)

        result_entry = {
            "id": test_case.get("id", ""),
            "query": query,
            "answer": answer[:200] + "..." if len(answer) > 200 else answer,
            "reference_answer": reference_answer[:100] + "..." if len(reference_answer) > 100 else reference_answer,
            "completeness": round(completeness, 2),
            "found_keywords": found_keywords,
            "expected_keywords": expected_keywords,
            "success": success,
            "steps": result.total_steps if hasattr(result, "total_steps") else 0,
            "elapsed": round(elapsed, 2),
            "answer_length": answer_length,
        }
        results.append(result_entry)

        # 打印单条结果
        status = "PASS" if completeness >= 0.5 and success else "FAIL"
        print(f"  -> [{status}] completeness={completeness:.0%}, success={success}, "
              f"steps={result_entry['steps']}, elapsed={elapsed:.1f}s")
        print(f"     found: {found_keywords}")
        print(f"     answer: {result_entry['answer'][:80]}...")

    # 汇总统计
    total = len(results)
    avg_completeness = sum(r["completeness"] for r in results) / total if total else 0
    success_count = sum(1 for r in results if r["success"])
    pass_count = sum(1 for r in results if r["completeness"] >= 0.5 and r["success"])
    avg_elapsed = sum(r["elapsed"] for r in results) / total if total else 0

    summary = {
        "total": total,
        "passed": pass_count,
        "failed": total - pass_count,
        "success_count": success_count,
        "avg_completeness": round(avg_completeness, 2),
        "pass_rate": round(pass_count / total, 2) if total else 0,
        "avg_elapsed": round(avg_elapsed, 2),
        "results": results,
    }

    # 打印汇总
    print("\n" + "=" * 60)
    print("[本地评测汇总]")
    print("=" * 60)
    print(f"  总用例数: {summary['total']}")
    print(f"  通过数: {summary['passed']} (通过率: {summary['pass_rate']:.0%})")
    print(f"  成功数: {summary['success_count']}")
    print(f"  平均关键词覆盖率: {summary['avg_completeness']:.0%}")
    print(f"  平均耗时: {summary['avg_elapsed']:.1f}s")
    print("=" * 60)

    # 保存本地报告
    report_path = os.path.join(DATASET_DIR, f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n[INFO] 本地评测报告已保存: {report_path}")

    return summary


# ============================================================
# 第五部分: LangSmith 在线评测
# ============================================================

def run_langsmith_evaluation(
    client: Client,
    dataset_name: str,
    experiment_prefix: Optional[str] = None,
) -> Optional[Any]:
    """运行 LangSmith 在线评测

    使用 langsmith.evaluation.evaluate 函数运行评测，
    结果自动上传到 LangSmith 平台。

    Args:
        client: LangSmith Client 实例
        dataset_name: 数据集名称
        experiment_prefix: 实验名称前缀

    Returns:
        评估结果对象
    """
    if not experiment_prefix:
        experiment_prefix = f"financial-rag-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # 评估器列表 (函数式，兼容 langsmith 0.8.x evaluate API)
    evaluators = [
        answer_completeness_eval,
        answer_success_eval,
        answer_length_eval,
    ]

    print(f"\n[LangSmith] 开始在线评测...")
    print(f"  实验名称: {experiment_prefix}")
    print(f"  数据集: {dataset_name}")
    print(f"  评估器: answer_completeness, answer_success, answer_length")
    print(f"  并发数: 1 (串行执行，避免 API 限流)")
    print()

    try:
        results = evaluate(
            target_function,
            data=dataset_name,
            evaluators=evaluators,
            experiment_prefix=experiment_prefix,
            max_concurrency=1,
            client=client,
        )

        # 打印评测结果汇总
        print()
        print("=" * 60)
        print("[LangSmith] 评测结果汇总")
        print("=" * 60)

        # 尝试从 results 中提取分数
        try:
            if hasattr(results, "_results"):
                eval_results = results._results
            elif hasattr(results, "results"):
                eval_results = results.results
            else:
                eval_results = results

            # 逐条打印评估结果
            scores_summary = {}
            if isinstance(eval_results, list):
                for r in eval_results:
                    run_name = ""
                    try:
                        run_name = r.get("name", r.get("run", {}).get("name", ""))[:50]
                    except Exception:
                        pass

                    eval_res = r.get("evaluation_results", [])
                    for er in eval_res:
                        key = er.get("key", "unknown")
                        score = er.get("score")
                        comment = er.get("comment", "")
                        if key not in scores_summary:
                            scores_summary[key] = []
                        scores_summary[key].append(score)
                        print(f"  [{key}] score={score} | {comment[:60]}")
            elif isinstance(eval_results, dict):
                for key, val in eval_results.items():
                    print(f"  {key}: {val}")
        except Exception as e:
            print(f"  [WARN] 结果解析失败: {e}")

        # 打印汇总统计
        if scores_summary:
            print()
            print("-" * 60)
            print("[评估器得分汇总]")
            for key, scores in scores_summary.items():
                valid_scores = [s for s in scores if s is not None]
                if valid_scores:
                    avg = sum(valid_scores) / len(valid_scores)
                    print(f"  {key}: avg={avg:.2f}, scores={valid_scores}")
                else:
                    print(f"  {key}: 无有效分数")

        print()
        print("[LangSmith] 评测完成!")
        print(f"  实验名称: {experiment_prefix}")
        print(f"  数据集: {dataset_name}")
        print()
        print("查看详细结果:")
        print(f"  https://smith.langchain.com")
        print()
        print("在 LangSmith 界面中:")
        print("  1. 进入 'Experiments' 页面")
        print(f"  2. 查找实验: {experiment_prefix}")
        print("  3. 查看详细的评估结果、分数和统计信息")

        return results
    except Exception as e:
        print(f"[ERROR] 评测运行失败: {str(e)}")
        traceback.print_exc()
        return None


# ============================================================
# 第六部分: 主函数
# ============================================================

def main():
    """主函数: 加载数据集 -> 上传/检查 -> 运行评测

    支持命令行参数:
      --local   强制使用本地评测模式 (不上传 LangSmith)
    """

    force_local = "--local" in sys.argv

    print("=" * 60)
    print("企业级财务年报分析智能RAG Agent - LangSmith 评测")
    print("=" * 60)
    print()

    # 加载本地数据集
    test_cases = load_local_dataset(GENERATION_DATASET_PATH)
    if not test_cases:
        print("[ERROR] 无法加载评测数据集，退出")
        sys.exit(1)

    # 检查 LangSmith 是否可用
    langsmith_enabled = is_available() and not force_local
    client = get_client() if langsmith_enabled else None

    if langsmith_enabled and client:
        # ---- LangSmith 在线评测模式 ----
        print(f"[LangSmith] 已启用 | 项目: {LANGSMITH_PROJECT}")
        print()

        # 步骤 1: 上传数据集
        print("步骤 1: 上传评测数据集到 LangSmith...")
        print("-" * 60)
        dataset_name = upload_dataset_to_langsmith(client, test_cases)
        if not dataset_name:
            print("[ERROR] 数据集上传失败，退出")
            sys.exit(1)
        print()

        # 步骤 2: 运行评测
        print("步骤 2: 运行 LangSmith 评测...")
        print("-" * 60)
        results = run_langsmith_evaluation(client, dataset_name)

        if results:
            print()
            print("=" * 60)
            print("评测完成! 请访问 LangSmith 查看结果")
            print("=" * 60)
        else:
            print()
            print("[WARN] 评测完成但未返回结果，请检查 LangSmith 界面")
    else:
        # ---- 本地评测模式 ----
        print("[LangSmith] 未启用 (LANGSMITH_API_KEY 或 LANGCHAIN_TRACING_V2 未配置)")
        print("  启用方法: 在 env 文件中设置 LANGSMITH_API_KEY 和 LANGCHAIN_TRACING_V2=true")
        print()
        run_local_evaluation(test_cases)


if __name__ == "__main__":
    main()
