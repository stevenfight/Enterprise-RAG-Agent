# -*- coding: utf-8 -*-
"""
数值验证工具 (Agent 工具)

对 Agent 生成的数据陈述进行来源验证，检测幻觉。
通过对比 claim 中的数值与 source_text 中的原始数据，
判断陈述是否与来源一致。

验证流程:
  1. 从 claim 中提取数值
  2. 从 source_text 中提取数值
  3. 逐一比对，计算置信度
  4. 返回 valid (True/False/None) + match_details

Agent 用法示例:
    Thought: 我刚才说"中芯国际营收1250亿元"，需要验证
    Action: verify
    Action Input: {"claim": "中芯国际2024年营收为1250亿元",
                   "source_text": "2024年度公司实现营业收入578.21亿元"}

对应 SDD: openspec/changes/rag-to-agent/specs/spec-tools.md
对应 TDD: tests/test_agent_tools.py (TC-T10 ~ TC-T12)
"""

import logging
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from . import BaseTool, ToolResult

logger = logging.getLogger("verify_tool")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)

# 数值匹配容差 (相对误差)
TOLERANCE = 0.05

# 匹配时单位换算系数
UNIT_MULTIPLIERS = {
    "亿": 1e8,
    "万": 1e4,
    "千": 1e3,
}

# 置信度阈值
HIGH_CONFIDENCE = 0.9
MEDIUM_CONFIDENCE = 0.6


class VerifyTool(BaseTool):
    """数值验证工具

    将 Agent 生成的数据陈述与原始来源文本进行比对，
    检测是否存在幻觉（数值不匹配）。

    验证规则:
      - 提取 claim 和 source_text 中的数字
      - 考虑单位换算（亿/万）
      - 相对误差 ≤ 5% 视为匹配
      - 多重验证来源时加权置信度
    """

    name = "verify"
    description = (
        "验证数据陈述是否与原始来源一致。输入声明(claim)和来源文本(source_text)，"
        "自动提取数字比对，判断幻觉风险。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "claim": {
                "type": "string",
                "description": "待验证的数据陈述，如 '中芯国际2024年营收为1250亿元'"
            },
            "source_text": {
                "type": "string",
                "description": "原始来源文本，如 '2024年度公司实现营业收入1250.38亿元'"
            },
            "claim_label": {
                "type": "string",
                "description": "声明的指标标签（可选），如 '营收', '净利润'"
            },
        },
        "required": ["claim", "source_text"],
    }

    def __init__(self):
        logger.info("[VerifyTool] 初始化完成")

    # ============================================================
    # 核心 run 方法
    # ============================================================

    def run(self, **kwargs) -> ToolResult:
        """执行数值验证

        Args:
            claim (str): 待验证的数据陈述
            source_text (str): 原始来源文本
            claim_label (str): 指标标签（可选）

        Returns:
            ToolResult: data 包含 valid, confidence, match_details
        """
        error = self._validate_params(["claim", "source_text"], **kwargs)
        if error:
            logger.warning("[VerifyTool] 参数校验失败: %s", error)
            return ToolResult(success=False, error=error)

        claim = kwargs["claim"]
        source_text = kwargs["source_text"]
        claim_label = kwargs.get("claim_label", "")

        logger.info("[VerifyTool] ====== 验证开始 ======")
        logger.info("[VerifyTool] claim: '%s'", claim[:100] + "..." if len(claim) > 100 else claim)
        logger.info("[VerifyTool] source_text 长度: %d 字符", len(source_text))
        logger.info("[VerifyTool] claim_label: %s", claim_label or "(无)")

        # ---- 来源不足检查 ----
        if not source_text or len(source_text.strip()) < 10:
            logger.warning("[VerifyTool] 来源文本不足 (len=%d)，无法验证", len(source_text) if source_text else 0)
            return ToolResult(
                success=True,
                data={
                    "valid": None,
                    "confidence": 0.0,
                    "message": "来源文本不足，无法进行有效验证。建议扩大检索范围获取更多原始数据。",
                    "match_details": [],
                }
            )

        # ---- 提取数值 ----
        claim_numbers = self._extract_numbers(claim)
        source_numbers = self._extract_numbers(source_text)

        logger.info("[VerifyTool] claim 提取到 %d 个数值: %s",
                     len(claim_numbers),
                     [(n["value"], n["unit"]) for n in claim_numbers])
        logger.info("[VerifyTool] source 提取到 %d 个数值: %s",
                     len(source_numbers),
                     [(n["value"], n["unit"]) for n in source_numbers])

        # ---- 无来源数值 ----
        if not source_numbers:
            logger.warning("[VerifyTool] source_text 中未提取到有效数值")
            return ToolResult(
                success=True,
                data={
                    "valid": None,
                    "confidence": 0.0,
                    "message": "来源文本中无有效数值，无法验证。请确认来源文本是否为财务数据段落。",
                    "match_details": [],
                }
            )

        # ---- 无声明数值 ----
        if not claim_numbers:
            logger.info("[VerifyTool] claim 中未提取到数值，可能为定性陈述")
            return ToolResult(
                success=True,
                data={
                    "valid": True,
                    "confidence": 0.5,
                    "message": "声明中未检测到具体数值，可能是定性陈述，无法量化验证。",
                    "match_details": [],
                }
            )

        # ---- 逐条比对 ----
        match_details = []
        matched_count = 0
        mismatched_count = 0

        for cn in claim_numbers:
            claim_val = cn["value"]
            claim_unit = cn["unit"]
            claim_str = cn["raw"]

            logger.info("[VerifyTool] 比对声明值: raw='%s', value=%.4f, unit='%s'",
                         claim_str, claim_val, claim_unit)

            best_match = None
            best_distance = float("inf")

            for sn in source_numbers:
                source_val = sn["value"]
                source_unit = sn["unit"]
                source_str = sn["raw"]

                # 统一单位后比较
                claim_scaled = self._scale_to_unit(claim_val, claim_unit, source_unit)
                distance = abs(claim_scaled - source_val)

                if source_val != 0:
                    relative_error = distance / abs(source_val)
                else:
                    relative_error = float("inf")

                logger.info("[VerifyTool]   比源: value=%.4f, unit='%s', 统一后claim=%.4f, "
                             "distance=%.4f, rel_err=%.4f",
                             source_val, source_unit, claim_scaled, distance, relative_error)

                if relative_error < best_distance:
                    best_distance = relative_error
                    best_match = {
                        "source_raw": source_str,
                        "source_value": source_val,
                        "source_unit": source_unit,
                        "relative_error": round(relative_error, 4),
                    }

            if best_match is not None and best_match["relative_error"] <= TOLERANCE:
                detail = "匹配: claim='%s' vs source='%s' (误差=%.2f%%)" % (
                    claim_str,
                    best_match["source_raw"],
                    best_match["relative_error"] * 100,
                )
                matched_count += 1
                logger.info("[VerifyTool]   [OK] 匹配: %s", detail)
            else:
                if best_match is not None:
                    detail = "不匹配: claim='%s' (%.4f%s), 最接近 source='%s' (%.4f%s), 误差=%.2f%%" % (
                        claim_str, claim_val, claim_unit,
                        best_match["source_raw"], best_match["source_value"],
                        best_match["source_unit"],
                        best_match["relative_error"] * 100,
                    )
                else:
                    detail = "不匹配: claim='%s', 来源中无任何数值可比对" % claim_str
                mismatched_count += 1
                logger.warning("[VerifyTool]   [FAIL] 不匹配: %s", detail[:120])

            match_details.append({
                "claim_value": claim_str,
                "matched": best_match["relative_error"] <= TOLERANCE if best_match else False,
                "source_match": best_match["source_raw"] if best_match else None,
                "relative_error": best_match["relative_error"] if best_match else None,
                "detail": detail,
            })

        # ---- 计算置信度 ----
        total = len(claim_numbers)
        confidence = self._compute_confidence(matched_count, total)

        if matched_count == total and total > 0:
            valid = True
            message = "验证通过: 声明中 %d/%d 个数值与来源一致" % (matched_count, total)
        elif matched_count > 0:
            valid = True
            message = "部分验证通过: %d/%d 个数值匹配, %d 个不匹配" % (
                matched_count, total, mismatched_count)
        elif mismatched_count > 0:
            valid = False
            message = "验证失败: 声明中 %d 个数值均与来源不一致，可能存在幻觉" % mismatched_count
        else:
            valid = None
            message = "无法验证"

        logger.info("[VerifyTool] ====== 验证完成 ======")
        logger.info("[VerifyTool] 结果: valid=%s, confidence=%.2f, matched=%d/%d, mismatched=%d",
                     valid, confidence, matched_count, total, mismatched_count)

        return ToolResult(
            success=True,
            data={
                "valid": valid,
                "confidence": round(confidence, 2),
                "message": message,
                "match_details": match_details,
                "claim_label": claim_label,
                "total_claims": total,
                "matched_count": matched_count,
                "mismatched_count": mismatched_count,
            }
        )

    # ============================================================
    # 数值提取
    # ============================================================

    def _extract_numbers(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取所有数值及其单位

        支持的格式:
          - 纯数字: 1250, 578.21
          - 带单位: 1250亿元, 578.21万元, 1,384亿元
          - 带宽单位: 1250亿, 578万

        Args:
            text: 原始文本

        Returns:
            数值列表，每项包含 value(float), unit(str), raw(str)
        """
        results = []

        # 匹配模式: 数字 + 可选单位(亿/万/千)
        pattern = r"([\d,，]+\.?[\d]*)\s*([亿万千]?)"
        matches = re.finditer(pattern, text)

        for m in matches:
            raw = m.group(0).strip()
            num_str = m.group(1).replace(",", "").replace("，", "")
            unit = m.group(2) if m.group(2) else "个"

            # 跳过孤立的小数点或明显非数值
            if num_str in (".", ",", "，", ""):
                continue
            try:
                value = float(num_str)
            except ValueError:
                logger.debug("[VerifyTool] 跳过无法解析的数字: '%s'", num_str)
                continue

            # 跳过四年份 (1900-2099) 且单位为空/个
            if unit in ("个", "") and 1900 <= value <= 2099 and value == int(value):
                continue

            # 跳过过于小或过于大的异常值（可能是页码或股票代码）
            if value < 0.001 or value > 1e15:
                continue

            results.append({
                "value": value,
                "unit": unit,
                "raw": raw,
            })

        logger.info("[VerifyTool] 数值提取: 从 %d 字符中提取到 %d 个有效数值",
                     len(text), len(results))
        return results

    def _scale_to_unit(self, value: float, from_unit: str, to_unit: str) -> float:
        """统一数值到相同单位

        Args:
            value: 原始数值
            from_unit: 原单位
            to_unit: 目标单位

        Returns:
            换算后的数值
        """
        if from_unit == to_unit:
            return value

        from_mult = UNIT_MULTIPLIERS.get(from_unit, 1.0)
        to_mult = UNIT_MULTIPLIERS.get(to_unit, 1.0)

        scaled = value * from_mult / to_mult
        logger.debug("[VerifyTool] 单位换算: %.4f %s → %.4f %s (乘数: %s/%s)",
                      value, from_unit, scaled, to_unit, from_mult, to_mult)
        return scaled

    def _compute_confidence(self, matched: int, total: int) -> float:
        """计算验证置信度

        基于匹配比例和总数量的递减加权:
          - 全部匹配且 ≥ 2 个数值 → 1.0
          - 部分匹配 → 比例 * 递减权重

        Args:
            matched: 匹配的数值数量
            total: 总数值数量

        Returns:
            置信度 (0.0 ~ 1.0)
        """
        if total == 0:
            return 0.0
        if matched == total and total >= 2:
            return 1.0
        if matched == total and total == 1:
            return HIGH_CONFIDENCE
        if matched > 0:
            ratio = matched / total
            return round(ratio * (1.0 - (total - matched) * 0.1), 2)
        return 0.0
