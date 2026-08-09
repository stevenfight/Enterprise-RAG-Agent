# -*- coding: utf-8 -*-
"""
Worker Agent 包

Orchestrator 通过 DelegateTool 将子任务分发给本包中的各个 Agent 执行。
全部 5 个 Worker Agent 已实现：

- DataAgent: 财务数据检索分析
- CalcAgent: 指标计算
- CompareAgent: 公司对比分析
- ChartAgent: 图表生成
- VerifyAgent: 结果验证
"""

from .data_agent import DataAgent
from .calc_agent import CalcAgent
from .compare_agent import CompareAgent
from .chart_agent import ChartAgent
from .verify_agent import VerifyAgent

__all__ = [
    "DataAgent",
    "CalcAgent",
    "CompareAgent",
    "ChartAgent",
    "VerifyAgent",
]
