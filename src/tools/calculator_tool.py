# -*- coding: utf-8 -*-
"""
财务计算器工具 (Agent 工具)

提供企业年报分析中常用的财务指标计算能力：
  - 同比增长率 (YoY)
  - 复合年增长率 (CAGR)
  - 利润率 (利润率/毛利率/净利率)
  - 增减百分比

Agent 用法示例:
    Thought: 需要计算中芯国际营收同比增长率
    Action: calculator
    Action Input: {"operation": "yoy_growth", "current": 89.7, "previous": 63.2}

对应 SDD: openspec/changes/rag-to-agent/specs/spec-tools.md
对应 TDD: tests/test_agent_tools.py (TC-T04 ~ TC-T05)
"""

import logging
import sys
from typing import Any, Dict, List, Optional

from . import BaseTool, ToolResult

logger = logging.getLogger("calculator_tool")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


# ============================================================
# 计算函数
# ============================================================

def _safe_float(value: Any) -> float:
    """安全转换为 float，失败返回 None 标记"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _fmt(value: float, decimals: int = 2) -> str:
    """格式化数字为可读字符串，保留指定位数"""
    if value is None:
        return "N/A"
    if abs(value) >= 1e8:
        return "%.1f亿" % (value / 1e8)
    if abs(value) >= 1e4:
        return "%.1f万" % (value / 1e4)
    if decimals == 0:
        return "%d" % int(round(value))
    return ("%%.%df" % decimals) % value


def calc_yoy_growth(current: Any, previous: Any) -> Dict[str, Any]:
    """同比增长率 (Year-over-Year Growth)
    
    公式: (current - previous) / |previous| * 100
    
    Returns:
        dict 包含 current, previous, growth_rate, absolute_change, direction
    """
    cur = _safe_float(current)
    prev = _safe_float(previous)

    logger.info("[Calculator] yoy_growth 输入: current=%s → %.4f, previous=%s → %.4f",
                 str(current)[:20], cur if cur is not None else "INVALID",
                 str(previous)[:20], prev if prev is not None else "INVALID")

    if cur is None or prev is None:
        logger.warning("[Calculator] yoy_growth 校验失败: current=%s, previous=%s",
                       "None" if cur is None else "OK", "None" if prev is None else "OK")
        return {"error": "参数必须为有效数字"}
    if prev == 0:
        logger.warning("[Calculator] yoy_growth 校验失败: previous=0 (分母为零)")
        return {"error": "上年数据为零，无法计算增长率（分母为零）"}

    change = cur - prev
    logger.info("[Calculator] yoy_growth 中间计算: %.4f - %.4f = %.4f", cur, prev, change)

    rate = round((change / abs(prev)) * 100, 2)
    logger.info("[Calculator] yoy_growth 中间计算: %.4f / |%.4f| * 100 = %.2f%%", change, prev, rate)

    direction = "增长" if change > 0 else ("下降" if change < 0 else "持平")
    logger.info("[Calculator] yoy_growth 结果: change=%.4f, rate=%.2f%%, direction=%s", change, rate, direction)

    return {
        "current_value": cur,
        "previous_value": prev,
        "absolute_change": round(change, 2),
        "growth_rate_pct": rate,
        "direction": direction,
        "formula": "(%.2f - %.2f) / |%.2f| * 100 = %.2f%%" % (cur, prev, prev, rate),
    }


def calc_cagr(start_value: Any, end_value: Any, years: Any) -> Dict[str, Any]:
    """复合年增长率 (Compound Annual Growth Rate)
    
    公式: (end / start)^(1/years) - 1
    
    Returns:
        dict 包含 start_value, end_value, years, cagr_pct
    """
    start = _safe_float(start_value)
    end = _safe_float(end_value)
    yrs = _safe_float(years)

    logger.info("[Calculator] cagr 输入: start=%s → %.4f, end=%s → %.4f, years=%s → %.4f",
                 str(start_value)[:20], start if start is not None else "INVALID",
                 str(end_value)[:20], end if end is not None else "INVALID",
                 str(years)[:20], yrs if yrs is not None else "INVALID")

    if start is None or end is None or yrs is None:
        return {"error": "参数必须为有效数字"}
    if start <= 0:
        logger.warning("[Calculator] cagr 校验失败: start=%.4f (必须大于零)", start)
        return {"error": "起始值必须大于零（CAGR 要求正基数）"}
    if yrs <= 0:
        logger.warning("[Calculator] cagr 校验失败: years=%.4f (必须大于零)", yrs)
        return {"error": "年数必须大于零"}

    ratio = end / start
    logger.info("[Calculator] cagr 中间计算: %.4f / %.4f = %.6f", end, start, ratio)

    cagr_raw = ratio ** (1.0 / yrs) - 1
    logger.info("[Calculator] cagr 中间计算: %.6f^(1/%.1f) - 1 = %.6f", ratio, yrs, cagr_raw)

    cagr = round(cagr_raw * 100, 2)
    direction = "增长" if cagr > 0 else ("下降" if cagr < 0 else "持平")
    logger.info("[Calculator] cagr 结果: cagr=%.2f%%, direction=%s", cagr, direction)

    return {
        "start_value": start,
        "end_value": end,
        "years": int(yrs) if yrs == int(yrs) else yrs,
        "cagr_pct": cagr,
        "direction": direction,
        "formula": "(%.2f / %.2f)^(1/%.1f) - 1 = %.2f%%" % (end, start, yrs, cagr),
    }


def calc_margin(numerator: Any, denominator: Any, margin_type: str = "通用") -> Dict[str, Any]:
    """利润率计算
    
    公式: numerator / denominator * 100
    
    Args:
        numerator: 分子（如净利润、毛利润）
        denominator: 分母（如营业收入）
        margin_type: 利润率类型标识
    
    Returns:
        dict 包含 numerator, denominator, margin_pct, margin_type
    """
    num = _safe_float(numerator)
    den = _safe_float(denominator)

    logger.info("[Calculator] margin 输入: numerator=%s → %.4f, denominator=%s → %.4f, type=%s",
                 str(numerator)[:20], num if num is not None else "INVALID",
                 str(denominator)[:20], den if den is not None else "INVALID",
                 margin_type)

    if num is None or den is None:
        return {"error": "参数必须为有效数字"}
    if den == 0:
        logger.warning("[Calculator] margin 校验失败: denominator=0")
        return {"error": "分母为零，无法计算利润率"}

    margin = round((num / abs(den)) * 100, 2)
    logger.info("[Calculator] margin 中间计算: %.4f / %.4f * 100 = %.2f%% (%s)",
                 num, den, margin, margin_type)

    return {
        "numerator": num,
        "denominator": den,
        "margin_pct": margin,
        "margin_type": margin_type,
        "formula": "%.2f / %.2f * 100 = %.2f%% (%s利润率)" % (num, den, margin, margin_type),
    }


def calc_pct_change(new_value: Any, old_value: Any, label: str = "") -> Dict[str, Any]:
    """增减百分比（通用）
    
    公式: (new - old) / |old| * 100
    
    Args:
        new_value: 新值
        old_value: 旧值
        label: 指标标签（如 "营收", "净利润"）
    """
    new = _safe_float(new_value)
    old = _safe_float(old_value)

    logger.info("[Calculator] pct_change 输入: new=%s → %.4f, old=%s → %.4f, label=%s",
                 str(new_value)[:20], new if new is not None else "INVALID",
                 str(old_value)[:20], old if old is not None else "INVALID",
                 label or "(无)")

    if new is None or old is None:
        return {"error": "参数必须为有效数字"}
    if old == 0:
        logger.warning("[Calculator] pct_change 校验失败: old=0")
        return {"error": "基数（旧值）为零，无法计算百分比变化"}

    change = new - old
    logger.info("[Calculator] pct_change 中间计算: %.4f - %.4f = %.4f", new, old, change)

    rate = round((change / abs(old)) * 100, 2)
    logger.info("[Calculator] pct_change 中间计算: %.4f / |%.4f| * 100 = %.2f%%", change, old, rate)

    direction = "增加" if change > 0 else ("减少" if change < 0 else "不变")
    logger.info("[Calculator] pct_change 结果: change=%.4f, rate=%.2f%%, direction=%s, label=%s",
                 change, rate, direction, label or "(无)")

    result = {
        "label": label,
        "old_value": old,
        "new_value": new,
        "absolute_change": round(change, 2),
        "change_pct": rate,
        "direction": direction,
        "formula": "(%s: %.2f - %.2f) / |%.2f| * 100 = %.2f%%" % (label, new, old, old, rate),
    }
    if not label:
        result.pop("label")
    return result


# ============================================================
# 操作映射表
# ============================================================

OPERATIONS = {
    "yoy_growth": {
        "func": calc_yoy_growth,
        "params": ["current", "previous"],
        "description": "同比增长率: (当年值 - 上年值) / |上年值| * 100%",
        "example": {
            "operation": "yoy_growth",
            "current": 89.7,
            "previous": 63.2,
        },
    },
    "cagr": {
        "func": calc_cagr,
        "params": ["start_value", "end_value", "years"],
        "description": "复合年增长率: (终值/初值)^(1/年数) - 1",
        "example": {
            "operation": "cagr",
            "start_value": 53.4,
            "end_value": 89.7,
            "years": 3,
        },
    },
    "margin": {
        "func": calc_margin,
        "params": ["numerator", "denominator", "margin_type"],
        "description": "利润率: 分子/分母*100%（如净利润/营收=净利率）",
        "example": {
            "operation": "margin",
            "numerator": 7.3,
            "denominator": 89.7,
            "margin_type": "净利率",
        },
    },
    "pct_change": {
        "func": calc_pct_change,
        "params": ["new_value", "old_value", "label"],
        "description": "增减百分比: (新值-旧值)/|旧值|*100%",
        "example": {
            "operation": "pct_change",
            "new_value": 89.7,
            "old_value": 63.2,
            "label": "营收",
        },
    },
}


# ============================================================
# CalculatorTool
# ============================================================

class CalculatorTool(BaseTool):
    """财务计算器工具

    提供 4 种财务指标计算:
      - yoy_growth: 同比增长率
      - cagr: 复合年增长率
      - margin: 利润率（毛利率/净利率/营业利润率）
      - pct_change: 增减百分比

    所有计算均在本地完成，不调用外部 API，零延迟。
    """

    name = "calculator"
    description = (
        "财务指标计算器。支持同比增长率(yoy_growth)、复合年增长率(cagr)、"
        "利润率(margin)、增减百分比(pct_change) 四种运算。"
        "所有运算均在本地精确计算，不调用外部服务。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["yoy_growth", "cagr", "margin", "pct_change"],
                "description": "计算类型: yoy_growth(同比增长率), cagr(复合年增长率), margin(利润率), pct_change(增减百分比)",
            },
            "current": {
                "type": "number",
                "description": "当年/最新值（用于 yoy_growth）",
            },
            "previous": {
                "type": "number",
                "description": "上年/历史值（用于 yoy_growth）",
            },
            "start_value": {
                "type": "number",
                "description": "起始值（用于 cagr）",
            },
            "end_value": {
                "type": "number",
                "description": "终止值（用于 cagr）",
            },
            "years": {
                "type": "number",
                "description": "年数（用于 cagr）",
            },
            "numerator": {
                "type": "number",
                "description": "分子（用于 margin，如净利润）",
            },
            "denominator": {
                "type": "number",
                "description": "分母（用于 margin，如营业收入）",
            },
            "margin_type": {
                "type": "string",
                "description": "利润率类型标签（用于 margin，如 '净利率', '毛利率'）",
            },
            "new_value": {
                "type": "number",
                "description": "新值（用于 pct_change）",
            },
            "old_value": {
                "type": "number",
                "description": "旧值（用于 pct_change）",
            },
            "label": {
                "type": "string",
                "description": "指标标签（用于 pct_change，如 '营收', '净利润'）",
            },
        },
        "required": ["operation"],
    }

    def __init__(self):
        logger.info("[CalculatorTool] 初始化完成")

    def run(self, **kwargs) -> ToolResult:
        """执行财务计算

        Args:
            operation (str): 计算类型，必填
            其他参数取决于具体 operation 类型

        Returns:
            ToolResult: success=True 时 data 包含计算结果文本
        """
        # 参数校验
        error = self._validate_params(["operation"], **kwargs)
        if error:
            logger.warning("[CalculatorTool] 参数校验失败: %s", error)
            return ToolResult(success=False, error=error)

        operation = kwargs["operation"]

        # 校验操作类型
        if operation not in OPERATIONS:
            available = sorted(OPERATIONS.keys())
            logger.warning("[CalculatorTool] 不支持的操作类型: %s", operation)
            return ToolResult(
                success=False,
                error="不支持的计算类型 '%s'，可用: %s" % (operation, ", ".join(available)),
            )

        op_def = OPERATIONS[operation]
        op_func = op_def["func"]
        required_params = op_def["params"]

        # 校验该操作所需的参数
        missing = [p for p in required_params if p not in kwargs or kwargs[p] is None]
        if missing:
            logger.warning("[CalculatorTool] 操作 '%s' 缺少参数: %s", operation, ", ".join(missing))
            return ToolResult(
                success=False,
                error="操作 '%s' 缺少参数: %s。示例: %s" % (
                    operation,
                    ", ".join(missing),
                    op_def["example"],
                ),
            )

        # 提取参数并执行计算
        try:
            params = {p: kwargs[p] for p in required_params}
            # 为 margin 传递 margin_type（可选参数）
            if operation == "margin" and "margin_type" in kwargs:
                params["margin_type"] = kwargs["margin_type"]
            if operation == "pct_change" and "label" in kwargs:
                params["label"] = kwargs["label"]

            result = op_func(**params)
        except Exception as e:
            logger.error("[CalculatorTool] 计算异常: %s", str(e))
            return ToolResult(success=False, error="计算异常: %s" % str(e))

        # 检查计算函数返回的错误
        if isinstance(result, dict) and "error" in result:
            logger.warning("[CalculatorTool] 计算失败: %s", result["error"])
            return ToolResult(success=False, error=result["error"])

        # 格式化输出
        logger.info("[CalculatorTool] 操作 '%s' 计算成功: %s", operation, result.get("formula", ""))
        output = self._format_output(operation, result)
        return ToolResult(success=True, data={"calculation": output, "details": result})

    def _format_output(self, operation: str, result: Dict[str, Any]) -> str:
        """将计算结果格式化为 Agent 可读的文本描述

        Args:
            operation: 操作类型
            result: 计算函数返回的结果字典

        Returns:
            格式化后的描述文本
        """
        if operation == "yoy_growth":
            return (
                "同比增长率计算:\n"
                "  当年值: %s\n"
                "  上年值: %s\n"
                "  同比变动: %s (%+.2f%%)\n"
                "  变动额: %+s"
            ) % (
                _fmt(result["current_value"]),
                _fmt(result["previous_value"]),
                result["direction"],
                result["growth_rate_pct"],
                _fmt(result["absolute_change"]),
            )

        if operation == "cagr":
            return (
                "复合年增长率 (CAGR) 计算:\n"
                "  起始值: %s\n"
                "  终止值: %s\n"
                "  年数: %s\n"
                "  年复合增长率: %+.2f%% (%s)"
            ) % (
                _fmt(result["start_value"]),
                _fmt(result["end_value"]),
                str(result["years"]),
                result["cagr_pct"],
                result["direction"],
            )

        if operation == "margin":
            return (
                "%s:\n"
                "  分子: %s\n"
                "  分母: %s\n"
                "  利润率: %.2f%%"
            ) % (
                result.get("margin_type", "利润率"),
                _fmt(result["numerator"]),
                _fmt(result["denominator"]),
                result["margin_pct"],
            )

        if operation == "pct_change":
            label = result.get("label", "指标")
            return (
                "%s 变化计算:\n"
                "  旧值: %s\n"
                "  新值: %s\n"
                "  变动: %s (%+.2f%%)"
            ) % (
                label,
                _fmt(result["old_value"]),
                _fmt(result["new_value"]),
                result["direction"],
                result["change_pct"],
            )

        return str(result)
