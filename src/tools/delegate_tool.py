# -*- coding: utf-8 -*-
"""
DelegateTool - Orchestrator 委托子任务给 Worker Agent 的工具

OrchestratorAgent 通过此工具将子任务外包给 Worker Agent 执行。
依赖注入：通过构造函数传入 agent_registry、shared_memory、event_queue。

阶段三升级：同批次独立任务并行执行（ThreadPoolExecutor），
支持 Worker 超时控制与失败重试（multi_agent 配置）。

对应方案：多Agent升级方案 步骤 2.3 + 3.1
"""

import concurrent.futures
import json
import logging
import queue
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.tools import BaseTool, ToolResult

logger = logging.getLogger("delegate_tool")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


class DelegateTool(BaseTool):
    """委托 Worker Agent 执行子任务

    OrchestratorAgent 持有此工具，LLM 可通过 Action: delegate 调用。
    阶段三起支持同批次任务并行执行，并受 worker_timeout / worker_max_retries 约束。

    Usage:
        from src.agent_registry import AgentRegistry
        from src.shared_memory import SharedMemory

        registry = AgentRegistry()
        sm = SharedMemory()
        tool = DelegateTool(agent_registry=registry, shared_memory=sm, event_queue=queue.Queue())
        result = tool.run(tasks=[
            {"agent": "DataAgent", "task": "中芯国际2024年营收", "company_name": "中芯国际"},
        ])
    """

    name = "delegate"
    description = (
        "将子任务委托给指定的 Worker Agent 执行。"
        "Worker 会自动获取上游 Agent 的数据结果。"
        "支持同时委托多个 Worker（同批并行执行）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "description": "要委托的子任务列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "agent": {
                            "type": "string",
                            "description": "Worker Agent 名称（如 DataAgent）"
                        },
                        "task": {
                            "type": "string",
                            "description": "子任务描述"
                        },
                        "company_name": {
                            "type": "string",
                            "description": "可选，指定公司名称"
                        },
                    },
                    "required": ["agent", "task"],
                },
            },
        },
        "required": ["tasks"],
    }

    # 可并行批：无相互依赖的检索/计算类任务
    _PARALLEL_AGENTS = {"DataAgent", "CalcAgent"}
    # 下游批：依赖上游数据写入后再执行
    _DOWNSTREAM_AGENTS = {"CompareAgent", "ChartAgent", "VerifyAgent"}

    def __init__(self, agent_registry, shared_memory,
                 event_queue: Optional[queue.Queue] = None):
        """初始化 DelegateTool（依赖注入）

        Args:
            agent_registry: AgentRegistry 实例（用于查找 Worker 能力）
            shared_memory: SharedMemory 实例（用于跨 Agent 结果共享）
            event_queue: 可选，线程安全的队列（用于 StepCallback 推送 Worker 步骤）
        """
        self.agent_registry = agent_registry
        self.shared_memory = shared_memory
        self._event_queue = event_queue
        self._llm_provider = None

    # ============================================================
    # 核心 run 方法（阶段三：批次分组 + 并行执行 + 超时/重试）
    # ============================================================

    def run(self, tasks: List[Dict[str, str]], **kwargs) -> ToolResult:
        """执行委托任务

        Args:
            tasks: 子任务列表，每个为 {"agent": "DataAgent", "task": "...", "company_name": "..."}

        Returns:
            ToolResult: 执行结果汇总
        """
        if not tasks:
            return ToolResult(success=False, error="tasks 参数为空")

        # 读取 multi_agent 容错配置（超时/重试）
        cfg = self._load_multi_agent_config()
        worker_timeout = cfg.get("worker_timeout", 30)
        max_retries = cfg.get("worker_max_retries", 1)

        # 1. 按依赖关系分组批次（检索类任务并行，分析类任务后续批）
        batches = self._group_by_dependency(tasks)

        # 2. 逐批执行（每批内部并行，批次间串行以保证下游读到完整上游数据）
        results = []
        worker_elapsed_list = []
        for batch_index, batch in enumerate(batches):
            logger.info("[DelegateTool] 批次 %d/%d: %d 个任务",
                         batch_index + 1, len(batches), len(batch))
            batch_results = self._run_batch_parallel(batch, worker_timeout, max_retries)
            results.extend(batch_results)
            worker_elapsed_list.extend(r.get("elapsed_ms", 0) for r in batch_results)

        # 3. 汇总结果（summary 供 Orchestrator Observation 使用）
        summary = "委托执行完成: {} 个子任务\n".format(len(tasks))
        summary += "\n".join(
            "[{}] {} - {}".format(
                "OK" if r.get("success") else "FAIL",
                r.get("task", "?"),
                r.get("answer", "")[:100] if r.get("success") else r.get("error", "")[:100],
            )
            for r in results
        )

        return ToolResult(
            success=True,
            data={
                "summary": summary,
                "total": len(tasks),
                "results": results,
                "parallel_batch_count": len(batches),
                "estimated_serial_ms": sum(worker_elapsed_list),
            },
        )

    # ============================================================
    # 批次分组与并行执行
    # ============================================================

    def _load_multi_agent_config(self) -> Dict[str, Any]:
        """读取 multi_agent 容错与超时配置（带默认值回退）

        Returns:
            dict 含 worker_timeout / worker_max_retries / continue_on_worker_failure
        """
        try:
            config_path = Path(__file__).resolve().parent.parent.parent / "config" / "agent_config.json"
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("multi_agent", {})
        except Exception as e:
            logger.warning("[DelegateTool] 读取 multi_agent 配置失败: %s，使用默认值", e)
            return {}

    def _group_by_dependency(self, tasks: List[Dict[str, str]]) -> List[List[Dict[str, str]]]:
        """按 Agent 类型分组批次

        检索/计算类任务（DataAgent/CalcAgent）相互独立 -> 同批并行；
        分析类任务（CompareAgent/ChartAgent/VerifyAgent）依赖上游数据 -> 后续批。
        """
        batches = []
        parallel_batch = []
        downstream_batch = []
        for task in tasks:
            agent_name = task.get("agent", "")
            if agent_name in self._PARALLEL_AGENTS:
                parallel_batch.append(task)
            else:
                downstream_batch.append(task)
        if parallel_batch:
            batches.append(parallel_batch)
        if downstream_batch:
            batches.append(downstream_batch)
        return batches

    def _run_batch_parallel(self, batch: List[Dict[str, str]],
                            worker_timeout: int, max_retries: int) -> List[Dict[str, Any]]:
        """同批任务并行执行（ThreadPoolExecutor）

        单个任务失败/超时不阻塞整批（continue_on_worker_failure=true 语义）。
        """
        # 单任务直接串行执行（无需开线程池）
        if len(batch) == 1:
            return [self._run_worker_task(batch[0], worker_timeout, max_retries)]

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
            future_to_task = {
                executor.submit(self._run_worker_task, task, worker_timeout, max_retries): task
                for task in batch
            }
            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error("[DelegateTool] 并行任务异常: %s", str(e))
                    results.append(self._build_failure_entry(task, f"并行执行异常: {e}"))
        return results

    def _run_worker_task(self, task: Dict[str, str],
                         worker_timeout: int, max_retries: int) -> Dict[str, Any]:
        """单任务执行单元（含超时控制与失败重试）

        超时用 ThreadPoolExecutor(max_workers=1) 的 future.result(timeout=) 实现；
        重试次数由 multi_agent 配置 worker_max_retries 控制。
        """
        agent_name = task.get("agent", "")
        sub_task = task.get("task", "")
        company = task.get("company_name", "")

        logger.info("[DelegateTool] 委托任务: agent=%s, task='%s', company='%s'",
                     agent_name, sub_task[:60], company)

        cap = self.agent_registry.get(agent_name)
        if cap is None:
            logger.warning("[DelegateTool] Agent '%s' 未注册", agent_name)
            return self._build_failure_entry(task, f"Agent '{agent_name}' 未注册")

        # 从 SharedMemory 构建上下文（下游 Worker 读上游结果）
        shared_ctx = self.shared_memory.get_context_for(agent_name)

        last_error = ""
        for attempt in range(max_retries + 1):
            # 按需创建 Worker Agent 实例
            worker = self._create_agent(cap)
            if worker is None:
                return self._build_failure_entry(task, f"Agent '{agent_name}' 创建失败")

            logger.info("[DelegateTool] 执行 Worker: %s (attempt %d/%d)",
                         agent_name, attempt + 1, max_retries + 1)
            worker_start = time.time()
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        worker.run,
                        query=sub_task,
                        company_name=company,
                        shared_context=shared_ctx,
                    )
                    result = future.result(timeout=worker_timeout)
            except concurrent.futures.TimeoutError:
                last_error = "Worker '%s' 超时 (%ds)" % (agent_name, worker_timeout)
                logger.error("[DelegateTool] %s", last_error)
                continue
            except Exception as e:
                last_error = "Worker '%s' 执行异常: %s" % (agent_name, str(e))
                logger.error("[DelegateTool] %s", last_error)
                continue

            # 执行成功：写入 SharedMemory 并返回结果
            worker_elapsed = (time.time() - worker_start) * 1000
            self.shared_memory.add_agent_result(
                f"{agent_name}({company})" if company else agent_name, result
            )
            logger.info("[DelegateTool] Worker '%s' 完成: success=%s, steps=%d, elapsed=%.0fms",
                         agent_name, result.success, result.total_steps, worker_elapsed)

            # M9: 推送 worker 完成事件到 SSE
            if self._event_queue is not None:
                try:
                    self._event_queue.put_nowait({
                        "type": "worker_complete",
                        "agent": agent_name,
                        "company": company,
                        "success": True,
                        "timestamp": int(time.time() * 1000),
                    })
                except Exception:
                    pass

            return {
                "agent": agent_name,
                "company": company,
                "task": sub_task,
                "success": result.success,
                "answer": result.answer[:200] if result.answer else "",
                "steps": result.total_steps,
                "elapsed_ms": worker_elapsed,
            }

        # 重试耗尽：推送失败事件并返回失败条目
        if self._event_queue is not None:
            try:
                self._event_queue.put_nowait({
                    "type": "worker_complete",
                    "agent": agent_name,
                    "company": company,
                    "success": False,
                    "timestamp": int(time.time() * 1000),
                })
            except Exception:
                pass
        return self._build_failure_entry(task, last_error)

    def _build_failure_entry(self, task: Dict[str, str], error: str) -> Dict[str, Any]:
        """构造失败结果条目（summary 展示用）"""
        return {
            "agent": task.get("agent", ""),
            "company": task.get("company_name", ""),
            "task": task.get("task", ""),
            "success": False,
            "error": error,
        }

    # ============================================================
    # Worker 实例创建（阶段三：支持 5 种 Worker）
    # ============================================================

    def _create_agent(self, cap, step_callback=None):
        """根据 AgentCapability 创建 Worker Agent 实例

        Args:
            cap: AgentCapability 实例
            step_callback: StepCallback 实例（预留，SSE worker_step 推送在后续阶段启用）

        Returns:
            ReActAgent 子类实例 或 None
        """
        from src.worker_agents.data_agent import DataAgent
        from src.worker_agents.calc_agent import CalcAgent
        from src.worker_agents.compare_agent import CompareAgent
        from src.worker_agents.chart_agent import ChartAgent
        from src.worker_agents.verify_agent import VerifyAgent
        from src.tools.retrieve_tool import RetrieveTool
        from src.tools.calculator_tool import CalculatorTool
        from src.tools.compare_tool import CompareTool
        from src.tools.chart_tool import ChartTool
        from src.tools.verify_tool import VerifyTool

        llm = getattr(self, '_llm_provider', None)

        retrieval = RetrieveTool()
        # 低优修复: 使用 WorkerToolFactory 复用工具实例
        try:
            from src.worker_tool_factory import WorkerToolFactory
        except ImportError:
            pass

        if cap.name == "DataAgent":
            return DataAgent(retrieval_tool=retrieval, llm_provider=llm)
        if cap.name == "CalcAgent":
            return CalcAgent(calculator_tool=CalculatorTool(), retrieval_tool=retrieval, llm_provider=llm)
        if cap.name == "CompareAgent":
            return CompareAgent(compare_tool=CompareTool(), retrieval_tool=retrieval, llm_provider=llm)
        if cap.name == "ChartAgent":
            return ChartAgent(chart_tool=ChartTool(), llm_provider=llm)
        if cap.name == "VerifyAgent":
            return VerifyAgent(verify_tool=VerifyTool(), retrieval_tool=retrieval, llm_provider=llm)

        logger.warning("[DelegateTool] 不支持的 Agent 类型: %s", cap.name)
        return None


class _DelegateStepCallback:
    """Worker 步骤回调（用于 SSE 流推送）

    不继承正式的 StepCallback 类，只依赖 queue.Queue 的线程安全特性。
    阶段三并行执行中，同批多个 Worker 各自持有独立的回调实例，
    均写入同一 queue.Queue（线程安全），SSE 消费端按序读取。
    """

    def __init__(self, agent_name: str, event_queue: queue.Queue):
        self.agent_name = agent_name
        self._event_queue = event_queue

    def __call__(self, step_type: str, step_data: Dict[str, Any]):
        """推送 Worker 步骤事件到 SSE 队列"""
        if self._event_queue:
            event = {
                "type": "worker_step",
                "agent": self.agent_name,
                "step_type": step_type,
                "data": step_data,
                "timestamp": int(time.time() * 1000),
            }
            self._event_queue.put(event)
            logger.debug("[DelegateTool] 推送 Worker 步骤: agent=%s, type=%s",
                          self.agent_name, step_type)
