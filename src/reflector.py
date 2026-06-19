# -*- coding: utf-8 -*-
"""
答案反思与验证模块 (Agent 反射层)

对 Agent 生成的中间/最终答案进行质量评估和自动修正：
  - 数值幻觉检测: 逐个数点与来源交叉验证
  - 来源完整性检查: 检查每个陈述是否有来源支撑
  - 回答完整性检查: 检查是否完整回应了用户的所有问题
  - 自动修正: 检测到问题时用来源数据替换错误值

调用链路:
  Agent.ReAct → AnswerReflector.verify(answer, sources, query)
    → 幻觉检测 → 来源检查 → 完整性检查 → 修正建议

对应 SDD: openspec/changes/rag-to-agent/specs/spec-reflection.md
对应 TDD: tests/test_reflector.py (TC-R01 ~ TC-R08)
"""

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("reflector")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)

# 容差配置
TOLERANCE = 0.05  # 5% 相对误差内视为一致

# 单位换算系数
UNIT_MULTIPLIERS = {"亿": 1e8, "万": 1e4, "千": 1e3}

# 数值提取正则
NUMBER_PATTERN = re.compile(r"([\d,，]+\.?[\d]*)\s*([亿万千]?)")


@dataclass
class ReflectionResult:
    """反思验证结果

    Attributes:
        has_hallucination: 是否检测到幻觉
        hallucination_count: 幻觉数据点数量
        total_datapoints: 总数据点数量
        source_completeness: 来源完整性评分 (0.0~1.0)
        answer_completeness: 回答完整性评分 (0.0~1.0)
        overall_confidence: 综合置信度
        suggestions: 修正建议列表
        details: 每个数据点的逐条验证结果
        corrected_answer: 修正后的答案 (如果有修正)
    """
    has_hallucination: bool = False
    hallucination_count: int = 0
    total_datapoints: int = 0
    source_completeness: float = 1.0
    answer_completeness: float = 1.0
    overall_confidence: float = 1.0
    suggestions: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)
    corrected_answer: str = ""


class AnswerReflector:
    """答案反思器

    对 Agent 输出进行三道检查:
      1. 数值幻觉检测: 每个数字是否与来源一致
      2. 来源完整性: 多少陈述有来源标注
      3. 回答完整性: 是否完整回应用户问题
    """

    def __init__(
        self,
        enable_verification: bool = True,
        enable_hallucination_check: bool = True,
        auto_correct: bool = True,
        hallucination_threshold: float = 0.7,
    ):
        """
        Args:
            enable_verification: 是否启用总体验证
            enable_hallucination_check: 是否启用幻觉检测
            auto_correct: 是否自动修正检测到的问题
            hallucination_threshold: 幻觉检测阈值 (数值差异超过此比例视为幻觉)
        """
        self.enable_verification = enable_verification
        self.enable_hallucination_check = enable_hallucination_check
        self.auto_correct = auto_correct
        self.hallucination_threshold = hallucination_threshold

        logger.info("[Reflector] 初始化完成: verification=%s, hallucination=%s, "
                     "auto_correct=%s, threshold=%.2f",
                     enable_verification, enable_hallucination_check,
                     auto_correct, hallucination_threshold)

    # ============================================================
    # 主入口: verify()
    # ============================================================

    def verify(
        self,
        answer: str,
        sources: List[Dict[str, Any]],
        user_query: str = "",
    ) -> ReflectionResult:
        """对 Agent 答案进行全量质量验证

        Args:
            answer: Agent 生成的答案文本
            sources: 检索来源列表 (由 retrieve 工具返回)
            user_query: 用户原始问题 (用于完整性检查)

        Returns:
            ReflectionResult: 包含幻觉检测、完整性和修正建议的完整结果
        """
        if not self.enable_verification:
            logger.info("[Reflector] 验证已禁用，跳过所有检查")
            return ReflectionResult()

        logger.info("[Reflector] ========== 开始反思验证 ==========")
        logger.info("[Reflector] 答案长度: %d 字符, 来源数: %d, 查询: '%s'",
                     len(answer), len(sources), user_query[:60] if user_query else "(无)")

        # ---- 提取答案中的数据点 ----
        datapoints = self._extract_datapoints(answer)
        logger.info("[Reflector] 从答案中提取到 %d 个数据点", len(datapoints))
        for i, dp in enumerate(datapoints):
            logger.info("[Reflector]   数据点 #%d: value=%.4f, unit='%s', context='%s'",
                         i + 1, dp["value"], dp["unit"], dp["context"][:60])

        total_datapoints = len(datapoints)

        # ---- 1. 幻觉检测 ----
        hallucination_count = 0
        details = []

        if self.enable_hallucination_check and total_datapoints > 0:
            logger.info("[Reflector] ------ 幻觉检测开始 (%d个数据点) ------", total_datapoints)

            for dp in datapoints:
                dp_detail = self._verify_datapoint(dp, sources)
                details.append(dp_detail)

                if dp_detail["is_hallucination"]:
                    hallucination_count += 1
                    logger.warning("[Reflector]   [幻觉] value=%.4f%s, context='%s' → %s",
                                   dp["value"], dp["unit"], dp["context"][:40],
                                   dp_detail.get("correction", "无修正候选"))
                else:
                    logger.info("[Reflector]   [正常] value=%.4f%s, matched_with='%s'",
                                 dp["value"], dp["unit"],
                                 dp_detail.get("best_source", "无")[:40] if dp_detail.get("best_source") else "无")

            logger.info("[Reflector] 幻觉检测结果: %d/%d 个数据点存在幻觉",
                         hallucination_count, total_datapoints)
        else:
            logger.info("[Reflector] 幻觉检测跳过: enabled=%s, datapoints=%d",
                         self.enable_hallucination_check, total_datapoints)

        # ---- 2. 来源完整性检查 ----
        source_completeness = self._check_source_completeness(answer, sources)
        logger.info("[Reflector] 来源完整性评分: %.2f", source_completeness)

        # ---- 3. 回答完整性检查 ----
        answer_completeness = self._check_answer_completeness(answer, user_query) if user_query else 1.0
        logger.info("[Reflector] 回答完整性评分: %.2f", answer_completeness)

        # ---- 4. 综合置信度 ----
        has_hallucination = hallucination_count > 0
        hallucination_penalty = hallucination_count / max(total_datapoints, 1) if total_datapoints > 0 else 0

        overall = (
            (1.0 - hallucination_penalty) * 0.6 +  # 幻觉权重 60%
            source_completeness * 0.2 +             # 来源权重 20%
            answer_completeness * 0.2               # 完整性权重 20%
        )
        overall = round(max(0.0, min(1.0, overall)), 2)
        logger.info("[Reflector] 综合置信度: %.2f (幻觉=%.2f, 来源完整性=%.2f, 回答完整性=%.2f)",
                     overall, 1.0 - hallucination_penalty, source_completeness, answer_completeness)

        # ---- 5. 生成建议 ----
        suggestions = self._generate_suggestions(
            has_hallucination, hallucination_count, total_datapoints,
            source_completeness, answer_completeness, details
        )
        if suggestions:
            logger.info("[Reflector] 生成 %d 条修正建议", len(suggestions))

        # ---- 6. 自动修正 ----
        corrected_answer = ""
        if self.auto_correct and has_hallucination and total_datapoints > 0:
            logger.info("[Reflector] 触发自动修正: %d 个幻觉数据点", hallucination_count)
            corrected_answer = self._apply_auto_correct(answer, details)
            logger.info("[Reflector] 自动修正完成: 修正后答案长度 %d 字符", len(corrected_answer))
        elif has_hallucination:
            logger.info("[Reflector] 自动修正未启用 (auto_correct=%s)", self.auto_correct)

        logger.info("[Reflector] ========== 反思验证完成 ==========")

        return ReflectionResult(
            has_hallucination=has_hallucination,
            hallucination_count=hallucination_count,
            total_datapoints=total_datapoints,
            source_completeness=round(source_completeness, 2),
            answer_completeness=round(answer_completeness, 2),
            overall_confidence=overall,
            suggestions=suggestions,
            details=details,
            corrected_answer=corrected_answer,
        )

    # ============================================================
    # 数据点提取
    # ============================================================

    def _extract_datapoints(self, text: str) -> List[Dict[str, Any]]:
        """从答案文本中提取所有数值数据点

        Args:
            text: 答案文本

        Returns:
            数据点列表，每项包含 value, unit, context, raw
        """
        results = []
        for m in NUMBER_PATTERN.finditer(text):
            num_str = m.group(1).replace(",", "").replace("，", "")
            unit = m.group(2) if m.group(2) else "个"

            if num_str in (".", ",", "，", ""):
                continue
            try:
                value = float(num_str)
            except ValueError:
                continue

            # 跳过年份
            if unit in ("个", "") and 1900 <= value <= 2099 and value == int(value):
                continue
            # 跳过异常值
            if value < 0.001 or value > 1e15:
                continue

            # 提取上下文 (数字前后各 30 字)
            pos = m.start()
            ctx_start = max(0, pos - 30)
            ctx_end = min(len(text), pos + len(m.group(0)) + 30)
            context = text[ctx_start:ctx_end].replace("\n", " ").strip()

            results.append({
                "value": value,
                "unit": unit,
                "context": context,
                "raw": m.group(0).strip(),
            })

        logger.info("[Reflector] 数据点提取: 从 %d 字符中提取 %d 个有效数值",
                     len(text), len(results))
        return results

    # ============================================================
    # 1. 幻觉检测 (逐点验证)
    # ============================================================

    def _verify_datapoint(
        self,
        dp: Dict[str, Any],
        sources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """验证单个数据点是否与来源一致

        Args:
            dp: 数据点 {value, unit, context}
            sources: 检索来源列表

        Returns:
            验证详情 {is_hallucination, best_source, correction, ...}
        """
        claim_value = dp["value"]
        claim_unit = dp["unit"]

        best_source = None
        best_distance = float("inf")
        best_source_value = None

        for src in sources:
            src_text = src.get("text", src.get("parent_text", ""))
            if not src_text:
                continue

            src_numbers = self._extract_numbers_from_text(src_text)
            for sn in src_numbers:
                # 统一单位后比较
                claim_scaled = self._scale_to_unit(claim_value, claim_unit, sn["unit"])
                distance = abs(claim_scaled - sn["value"])

                relative_error = distance / abs(sn["value"]) if sn["value"] != 0 else float("inf")

                if relative_error < best_distance:
                    best_distance = relative_error
                    best_source = src_text
                    best_source_value = (sn["value"], sn["unit"], sn["raw"])

        # 判断是否为幻觉
        is_hallucination = True
        correction = None
        if best_source is not None and best_distance <= self.hallucination_threshold:
            is_hallucination = False
        elif best_source_value is not None:
            correction = "%.4f%s" % (best_source_value[0], best_source_value[1])

        return {
            "claim_raw": dp["raw"],
            "claim_value": claim_value,
            "claim_unit": claim_unit,
            "context": dp["context"],
            "is_hallucination": is_hallucination,
            "best_distance": round(best_distance, 4) if best_distance != float("inf") else None,
            "best_source": best_source[:100] + ("..." if best_source and len(best_source) > 100 else "") if best_source else None,
            "correction": correction,
        }

    def _extract_numbers_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从来源文本提取数值"""
        results = []
        for m in NUMBER_PATTERN.finditer(text):
            num_str = m.group(1).replace(",", "").replace("，", "")
            unit = m.group(2) if m.group(2) else "个"
            if num_str in (".", ",", "，", ""):
                continue
            try:
                value = float(num_str)
            except ValueError:
                continue
            if unit in ("个", "") and 1900 <= value <= 2099 and value == int(value):
                continue
            if value < 0.001 or value > 1e15:
                continue
            results.append({"value": value, "unit": unit, "raw": m.group(0).strip()})
        return results

    def _scale_to_unit(self, value: float, from_unit: str, to_unit: str) -> float:
        """单位换算"""
        if from_unit == to_unit:
            return value
        from_mult = UNIT_MULTIPLIERS.get(from_unit, 1.0)
        to_mult = UNIT_MULTIPLIERS.get(to_unit, 1.0)
        return value * from_mult / to_mult

    # ============================================================
    # 2. 来源完整性检查
    # ============================================================

    def _check_source_completeness(
        self,
        answer: str,
        sources: List[Dict[str, Any]],
    ) -> float:
        """检查答案中数据陈述的来源覆盖率

        通过统计答案中数值与来源文本的匹配比例来评估。
        如果答案中每个数值都能在至少一个来源中找到对应，
        则完整性为 1.0。

        Args:
            answer: Agent 的答案文本
            sources: 检索来源列表

        Returns:
            来源完整性评分 (0.0 ~ 1.0)
        """
        if not sources:
            logger.warning("[Reflector] 无来源文本，完整性和幻觉检查均无法执行")
            return 0.0

        datapoints = self._extract_datapoints(answer)
        if not datapoints:
            logger.info("[Reflector] 答案中无数据点，来源完整性=1.0")
            return 1.0

        # 统计能在来源中找到对应值的数据点
        matched = 0
        for dp in datapoints:
            matched_flag = False
            for src in sources:
                src_text = src.get("text", src.get("parent_text", ""))
                if not src_text:
                    continue
                src_numbers = self._extract_numbers_from_text(src_text)
                for sn in src_numbers:
                    scaled = self._scale_to_unit(dp["value"], dp["unit"], sn["unit"])
                    rel_err = abs(scaled - sn["value"]) / abs(sn["value"]) if sn["value"] != 0 else float("inf")
                    if rel_err <= TOLERANCE:
                        matched_flag = True
                        break
                if matched_flag:
                    break
            if matched_flag:
                matched += 1

        completeness = round(matched / len(datapoints), 2) if datapoints else 1.0
        logger.info("[Reflector] 来源完整性: %d/%d 个数据点有来源支撑 → %.2f",
                     matched, len(datapoints), completeness)
        return completeness

    # ============================================================
    # 3. 回答完整性检查
    # ============================================================

    def _check_answer_completeness(self, answer: str, user_query: str) -> float:
        """检查答案是否完整回答了用户的所有问题

        简单规则:
          - 对比查询: 答案中是否覆盖了所有提及的公司
          - 多项指标: 用户问 N 个指标，答案是否覆盖了 N 个
          - 默认: 根据答案长度和关键词匹配度评估

        Args:
            answer: Agent 的答案
            user_query: 用户原始问题

        Returns:
            回答完整性评分 (0.0 ~ 1.0)
        """
        score = 0.5  # 基础分

        # 规则1: 检测用户是否在问多家公司
        company_keywords = {"中芯国际", "中国移动", "中国联通", "中国电信"}
        companies_asked = {c for c in company_keywords if c in user_query}
        companies_in_answer = {c for c in company_keywords if c in answer}

        if companies_asked:
            coverage = len(companies_in_answer & companies_asked) / len(companies_asked)
            logger.info("[Reflector] 公司覆盖: asked=%d (%s), in_answer=%d (%s) → coverage=%.2f",
                         len(companies_asked), ", ".join(sorted(companies_asked)),
                         len(companies_in_answer), ", ".join(sorted(companies_in_answer)),
                         coverage)
            score = max(score, coverage * 0.7 + 0.3)  # 公司覆盖占 70%

        # 规则2: 检测是否含有多指标要求
        metric_keywords = {"营收", "净利润", "毛利率", "净利率", "研发费用", "总资产", "增长率"}
        metrics_asked = {m for m in metric_keywords if m in user_query}
        metrics_in_answer = {m for m in metric_keywords if m in answer}

        if metrics_asked:
            metric_coverage = len(metrics_in_answer & metrics_asked) / len(metrics_asked)
            logger.info("[Reflector] 指标覆盖: asked=%d (%s), in_answer=%d (%s) → coverage=%.2f",
                         len(metrics_asked), ", ".join(sorted(metrics_asked)),
                         len(metrics_in_answer), ", ".join(sorted(metrics_in_answer)),
                         metric_coverage)
            score = min(score, metric_coverage * 0.5 + 0.5)  # 指标覆盖拉低评分

        # 规则3: 答案过短可能是敷衍
        if len(answer) < 50:
            logger.info("[Reflector] 答案过短 (%d 字符), 可能是敷衍回答", len(answer))
            score = min(score, 0.3)
        elif len(answer) > 200:
            score = min(score + 0.1, 1.0)

        return round(score, 2)

    # ============================================================
    # 4. 生成建议
    # ============================================================

    def _generate_suggestions(
        self,
        has_hallucination: bool,
        hallucination_count: int,
        total_datapoints: int,
        source_completeness: float,
        answer_completeness: float,
        details: List[Dict[str, Any]],
    ) -> List[str]:
        """基于检测结果生成修正建议列表

        Returns:
            建议字符串列表
        """
        suggestions = []

        if has_hallucination:
            suggestions.append(
                "检测到 %d/%d 个数据点与来源不一致，建议重新检索并核实数据" % (
                    hallucination_count, total_datapoints
                )
            )
            # 添加具体修正
            for i, det in enumerate(details):
                if det["is_hallucination"] and det.get("correction"):
                    suggestions.append(
                        "  数据点 #%d: '%s' 应修正为 '%s'" % (
                            i + 1, det["claim_raw"], det["correction"]
                        )
                    )

        if source_completeness < 0.8:
            suggestions.append(
                "来源完整性不足 (%.0f%%), 建议增加检索条数或调整 query 扩大检索范围" % (
                    source_completeness * 100
                )
            )

        if answer_completeness < 0.6:
            suggestions.append(
                "回答不够完整 (%.0f%%), 可能遗漏了用户关注的公司或指标" % (
                    answer_completeness * 100
                )
            )

        return suggestions

    # ============================================================
    # 5. 自动修正
    # ============================================================

    def _apply_auto_correct(
        self,
        answer: str,
        details: List[Dict[str, Any]],
    ) -> str:
        """对答案中的幻觉数据进行自动替换

        Args:
            answer: 原始答案文本
            details: 逐点验证详情 (含 correction 字段)

        Returns:
            修正后的答案文本
        """
        corrected = answer
        for det in details:
            if det["is_hallucination"] and det.get("correction"):
                logger.info("[Reflector] 自动修正: '%s' → '%s'",
                             det["claim_raw"], det["correction"])
                corrected = corrected.replace(det["claim_raw"], det["correction"])

        return corrected

    # ============================================================
    # 便捷方法 (TDD 兼容)
    # ============================================================

    def check_hallucination(self, answer: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """纯幻觉检测 (兼容 TDD TC-R01/R02)

        Returns:
            dict: {"has_hallucination": bool, "confidence": float, "details": [...]}
        """
        result = self.verify(answer, sources)
        return {
            "has_hallucination": result.has_hallucination,
            "confidence": result.overall_confidence,
            "details": result.details,
        }

    def check_completeness(self, answer: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """纯完整性检查 (兼容 TDD TC-R04/R05/R06)

        Returns:
            dict: {"source_completeness": float, "answer_completeness": float}
        """
        source = self._check_source_completeness(answer, sources)
        return {"source_completeness": source}

    def suggest_correction(self, answer: str, sources: List[Dict[str, Any]]) -> List[str]:
        """生成修正建议 (兼容 TDD TC-R07)

        Returns:
            建议字符串列表
        """
        datapoints = self._extract_datapoints(answer)
        details = [self._verify_datapoint(dp, sources) for dp in datapoints]
        has_hallucination = any(d["is_hallucination"] for d in details)
        hallucination_count = sum(1 for d in details if d["is_hallucination"])

        return self._generate_suggestions(
            has_hallucination, hallucination_count, len(datapoints),
            1.0, 1.0, details,
        )
