# -*- coding: utf-8 -*-
"""
多公司对比工具 (Agent 工具)

支持多公司、多指标横向财务数据对比分析。
内部调用 HybridRetriever 逐公司检索，整合为结构化 Markdown 表格。

调用链路:
  Agent.Action("compare") → CompareTool.run(companies, metric, year)
    → HybridRetriever.search(query, company_name, top_n) x N
    → 结构化对比表 + 差异分析

对应 SDD: openspec/changes/rag-to-agent/specs/spec-tools.md
对应 TDD: tests/test_agent_tools.py (TC-T06 ~ TC-T07)
"""

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import BaseTool, ToolResult

logger = logging.getLogger("compare_tool")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


class CompareTool(BaseTool):
    """多公司财务数据对比工具

    对多家公司的相同财务指标进行横向对比，支持:
      - 营收、净利润、毛利率等常见指标
      - 指定年份
      - 逐公司检索 + 结构化 Markdown 表格输出
      - 三层公司覆盖保底机制

    Agent 用法示例:
        Thought: 需要对比中芯国际、中国移动、中国联通2024年营收
        Action: compare
        Action Input: {"companies": ["中芯国际","中国移动","中国联通"], "metric": "营收", "year": "2024"}
    """

    name = "compare"
    description = (
        "对比多家公司的同一财务指标。指定公司列表、指标名称和年份，"
        "返回结构化 Markdown 格式对比表，包含数值、增长率和差异分析。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "companies": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要对比的公司列表"
            },
            "metric": {
                "type": "string",
                "description": "对比的财务指标，如: 营收, 净利润, 毛利率, 净利率, 总资产, 研发费用"
            },
            "year": {
                "type": "string",
                "description": "对比年份，如 '2024'。不填默认检索最新年报数据"
            },
            "top_n": {
                "type": "integer",
                "description": "每家公司检索条数，默认 3，最多 5"
            },
        },
        "required": ["companies", "metric"],
    }

    KNOWN_COMPANIES = ["中芯国际", "中国移动", "中国联通", "中国电信"]

    # 指标关键词映射（用于从文本中提取数值）
    METRIC_KEYWORDS = {
        "营收": ["营业总收入", "营业收入", "营收", "总收入"],
        "净利润": ["归属于.*净利润", "净利润", "归母净利润"],
        "毛利率": ["毛利率"],
        "净利率": ["净利率"],
        "总资产": ["总资产", "资产总计", "资产总额"],
        "研发费用": ["研发费用", "研发投入"],
        "净资产": ["净资产", "归属于母公司.*净资产", "股东权益"],
        "经营现金流": ["经营活动.*现金流", "经营现金流"],
    }

    def __init__(self, api_key=None):
        self._api_key = api_key
        self._retriever = None
        logger.info("[CompareTool] 初始化完成")

    # ============================================================
    # 内部方法
    # ============================================================

    def _get_retriever(self):
        if self._retriever is None:
            logger.info("[CompareTool] 首次调用，延迟加载 HybridRetriever...")
            from retrieval import HybridRetriever
            project_root = Path(__file__).resolve().parent.parent.parent
            vector_db_dir = project_root / "data" / "stock_data" / "databases" / "vector_dbs"
            if not vector_db_dir.exists():
                raise FileNotFoundError(
                    "向量数据库目录不存在: %s\n请先运行 python src/ingestion.py 构建向量数据库。" % vector_db_dir
                )
            self._retriever = HybridRetriever(vector_db_dir, api_key=self._api_key)
            logger.info("[CompareTool] HybridRetriever 已加载")
        return self._retriever

    def _validate_companies(self, companies):
        unknown = [c for c in companies if c not in self.KNOWN_COMPANIES]
        if unknown:
            logger.warning("[CompareTool] 未知公司: %s", ", ".join(unknown))
            valid = [c for c in companies if c in self.KNOWN_COMPANIES]
            if not valid:
                return "所有指定的公司均不在已知列表中: %s，可用: %s" % (
                    ", ".join(companies), ", ".join(self.KNOWN_COMPANIES)
                )
        return None

    def _search_company(self, company, metric, year, top_n):
        query = "%s %s %s" % (company, year, metric)
        logger.info("[CompareTool] 检索 %s: query='%s' (原查询), top_n=%d", company, query[:100], top_n)

        try:
            retriever = self._get_retriever()
            results = retriever.search(query=query, company_name=company, top_n=top_n)
            logger.info("[CompareTool] %s 检索返回: %d 条结果", company, len(results))
            if results:
                for i, r in enumerate(results[:3]):
                    logger.info("[CompareTool]   %s #%d: source=%s | pages=%s",
                                 company, i + 1,
                                 r.get("source_file", "?")[:50],
                                 r.get("pages", "?"))
            return results
        except Exception as e:
            logger.error("[CompareTool] %s 检索异常: %s", company, str(e))
            return []

    def _extract_key_value(self, results, metric):
        """从检索结果中提取关键指标值

        优先匹配完整句式（如 "营业收入为 1250 亿元"），回退到正则匹配。
        """
        keywords = self.METRIC_KEYWORDS.get(metric, [metric])

        logger.info("[CompareTool] 数值提取开始: metric='%s', 关键词=%s, 候选段数=%d",
                     metric, keywords, len(results))

        for idx, r in enumerate(results):
            text = r.get("parent_text", "")
            snippet_preview = text[:80].replace("\n", " ")
            logger.info("[CompareTool]   候选段 #%d: '%s...'", idx + 1, snippet_preview)

            # 优先匹配完整句式
            for kw in keywords:
                patterns = [
                    r"%s[约达为]+\s*[\d,，.]+[\s]*(?:亿[元]?|万[元]?|元[，, ])" % kw,
                    r"%s[是]?\s*[\d,，.]+[\s]*(?:亿[元]?|万[元]?|元[，, ])" % kw,
                    r"[\d,，.]+\s*(?:亿[元]?)\s*[，,].*%s" % kw,
                ]
                for pattern_idx, p in enumerate(patterns):
                    match = re.search(p, text)
                    if match:
                        raw_match = match.group(0).strip()
                        logger.info("[CompareTool]   数值提取成功: kw='%s', pattern=#%d, match='%s'",
                                     kw, pattern_idx + 1, raw_match[:60])
                        return raw_match

            # 回退：关键词附近找数字
            for kw in keywords:
                idx_kw = text.find(kw)
                if idx_kw >= 0:
                    snippet = text[max(0, idx_kw - 50): idx_kw + len(kw) + 100]
                    num_match = re.search(r"[\d,，.]+\s*(?:亿[元]?|万[元]?)", snippet)
                    if num_match:
                        raw_match = "%s: %s" % (kw, num_match.group(0))
                        logger.info("[CompareTool]   数值提取(回退): kw='%s', match='%s'", kw, raw_match[:60])
                        return raw_match

        logger.info("[CompareTool]   数值提取失败: 未在 %d 个候选段中找到与 '%s' 匹配的数值",
                     len(results), metric)
        return None

    # ============================================================
    # 格式化方法
    # ============================================================

    def _build_markdown_table(self, companies, metric, year, company_data):
        lines = [
            "## %s年 %s 多公司横向对比" % (year, metric),
            "",
            "| 公司 | %s | 数据来源 | 页码 |" % metric,
            "|------|------|---------|------|",
        ]
        for cn in companies:
            data = company_data.get(cn, {})
            value = data.get("value", "数据缺失")
            source = data.get("source", "-")
            pages = data.get("pages", "-")
            lines.append("| %s | %s | %s | %s |" % (cn, value, source, pages))
        lines.append("")
        return "\n".join(lines)

    def _build_difference_analysis(self, company_data):
        lines = ["### 差异说明", ""]

        numeric_companies = {}
        for cn, data in company_data.items():
            raw = data.get("raw_value")
            if raw is not None:
                numeric_companies[cn] = raw

        logger.info("[CompareTool] 差异分析: 可比较公司=%d (%s)",
                     len(numeric_companies),
                     ", ".join("%s=%.2f" % (k, v) for k, v in numeric_companies.items()) if numeric_companies else "无")

        if len(numeric_companies) >= 2:
            sorted_companies = sorted(numeric_companies.items(), key=lambda x: x[1], reverse=True)
            best_cn, best_val = sorted_companies[0]
            worst_cn, worst_val = sorted_companies[-1]
            lines.append("- 最高: **%s** (%.2f)" % (best_cn, best_val))
            lines.append("- 最低: **%s** (%.2f)" % (worst_cn, worst_val))

            if len(sorted_companies) >= 2 and best_val != 0:
                diff_pct = (best_val - worst_val) / abs(best_val) * 100
                lines.append("- 极差: %.2f (%.1f%%)" % (best_val - worst_val, diff_pct))
                logger.info("[CompareTool] 差异分析结果: best=%s(%.2f), worst=%s(%.2f), diff=%.2f(%.1f%%)",
                             best_cn, best_val, worst_cn, worst_val, best_val - worst_val, diff_pct)

        missing = [cn for cn, data in company_data.items()
                   if data.get("value") in ("数据缺失", "数据缺失（经保底检索仍无法获取）", "数据存在但未提取到具体数值")]
        if missing:
            lines.append("- 数据缺失: %s" % ", ".join(missing))

        return "\n".join(lines)

    # ============================================================
    # 核心 run 方法
    # ============================================================

    def run(self, **kwargs):
        error = self._validate_params(["companies", "metric"], **kwargs)
        if error:
            logger.warning("[CompareTool] 参数校验失败: %s", error)
            return ToolResult(success=False, error=error)

        companies = kwargs["companies"]
        metric = kwargs["metric"]
        year = kwargs.get("year", "2024")
        top_n = min(kwargs.get("top_n", 3), 5)

        logger.info("[CompareTool] ====== 对比分析开始 ======")
        logger.info("[CompareTool] 参数: companies=%s, metric='%s', year='%s', top_n=%d",
                     companies, metric, year, top_n)

        if not isinstance(companies, list) or len(companies) == 0:
            return ToolResult(success=False, error="companies 必须为非空列表")

        if len(companies) == 1:
            logger.info("[CompareTool] 只有 1 家公司，拒绝（请用 retrieve 工具）")
            return ToolResult(
                success=False,
                error="至少需要 2 家公司才能进行对比分析。如需查询单公司数据，请使用 retrieve 工具。"
            )

        validate_err = self._validate_companies(companies)
        if validate_err:
            return ToolResult(success=False, error=validate_err)

        valid_companies = [c for c in companies if c in self.KNOWN_COMPANIES]

        # ---- 逐公司检索 ----
        company_data = {}
        all_results = {}

        for cn in valid_companies:
            results = self._search_company(cn, metric, year, top_n)
            all_results[cn] = results

            if not results:
                logger.warning("[CompareTool] %s 无检索结果", cn)
                company_data[cn] = {"value": "数据缺失", "source": "-", "pages": "-", "raw_value": None}
                continue

            value_text = self._extract_key_value(results, metric)
            logger.info("[CompareTool] %s 提取到的数值文本: '%s'", cn, value_text[:80] if value_text else "None")

            top_result = results[0]
            source = top_result.get("source_file", "-")
            if len(source) > 40:
                source = source[:37] + "..."

            pages_raw = top_result.get("pages", [])
            if pages_raw and len(pages_raw) >= 2:
                pages = "第%d-%d页" % (pages_raw[0], pages_raw[-1])
            elif pages_raw:
                pages = "第%d页" % pages_raw[0]
            else:
                pages = "-"

            raw_value = None
            if value_text:
                num_match = re.search(r"([\d,，.]+)\s*(?:亿[元]?|万[元]?)", value_text)
                if num_match:
                    try:
                        raw_str = num_match.group(1).replace(",", "").replace("，", "")
                        raw_value = float(raw_str)
                        if "万" in value_text:
                            raw_value = raw_value / 10000
                            logger.info("[CompareTool] %s 转换为亿: %.4f (原单位=万)", cn, raw_value)
                        else:
                            logger.info("[CompareTool] %s 提取到原始数值: %.4f (单位=亿)", cn, raw_value)
                    except ValueError:
                        logger.warning("[CompareTool] %s 数值转换失败: '%s'", cn, num_match.group(1))

            company_data[cn] = {
                "value": value_text or "数据存在但未提取到具体数值",
                "source": source,
                "pages": pages,
                "raw_value": raw_value,
            }

        # ---- 三层保底 ----
        missing = [cn for cn in valid_companies
                   if company_data[cn]["value"] in ("数据缺失", "数据存在但未提取到具体数值")]
        if missing:
            logger.info("[CompareTool] 第一层保底触发: %d 家公司数据不足: %s", len(missing), ", ".join(missing))
            for cn in missing:
                logger.info("[CompareTool] 第二层保底: %s | query='%s %s年 %s' (不限公司)",
                             cn, cn, year, metric)
                try:
                    retriever = self._get_retriever()
                    fb_query = "%s %s年 %s" % (cn, year, metric)
                    fallback_results = retriever.search(query=fb_query, company_name=None, top_n=5)
                    fallback_for_cn = [r for r in fallback_results if r.get("company_name") == cn]
                    logger.info("[CompareTool] 第二层保底: %s | 不限公司检索=%d条 | 过滤后=%d条",
                                 cn, len(fallback_results), len(fallback_for_cn))
                    if fallback_for_cn:
                        value_text = self._extract_key_value(fallback_for_cn[:top_n], metric)
                        if value_text:
                            company_data[cn]["value"] = value_text
                            company_data[cn]["source"] = fallback_for_cn[0].get("source_file", "-")[:40]
                            company_data[cn]["pages"] = "保底检索"
                            logger.info("[CompareTool] 第二层保底成功: %s | value='%s'", cn, value_text[:60])
                except Exception as e:
                    logger.warning("[CompareTool] 第二层保底失败: %s | %s", cn, str(e))

        still_missing = [cn for cn in valid_companies
                         if company_data[cn]["value"] in ("数据缺失", "数据存在但未提取到具体数值")]
        if still_missing:
            logger.info("[CompareTool] 第三层保底触发: %d 家仍缺失: %s", len(still_missing), ", ".join(still_missing))
            for cn in still_missing:
                company_data[cn]["value"] = "数据缺失（经保底检索仍无法获取）"

        # ---- 生成对比表 ----
        table = self._build_markdown_table(valid_companies, metric, year, company_data)
        difference = self._build_difference_analysis(company_data)
        full_output = table + "\n" + difference

        data_count = sum(1 for d in company_data.values()
                         if d["value"] not in ("数据缺失", "数据缺失（经保底检索仍无法获取）",
                                                "数据存在但未提取到具体数值"))

        logger.info("[CompareTool] ====== 对比分析完成 ======")
        logger.info("[CompareTool] 覆盖率: %d/%d | 输出: %d 字符",
                     data_count, len(valid_companies), len(full_output))

        return ToolResult(
            success=True,
            data={
                "table": full_output,
                "metric": metric,
                "year": year,
                "companies_compared": len(valid_companies),
                "companies_with_data": data_count,
                "details": {cn: data["value"] for cn, data in company_data.items()},
            }
        )
