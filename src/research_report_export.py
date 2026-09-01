# -*- coding: utf-8 -*-
"""E1.6 研究报告的声明级 Markdown/HTML 导出。"""

from __future__ import annotations

from html import escape

from src.research_delivery import Claim, ResearchReport


class ResearchReportExporter:
    """只导出已有不可变报告快照，不生成或补全缺失的证据。"""

    @classmethod
    def to_markdown(cls, report: ResearchReport) -> str:
        """生成保留稳定标识和全部声明依据的 Markdown。"""
        cls._validate(report)
        lines = [
            "# 研究报告",
            "",
            f"- 报告 ID：`{report.report_id}`",
            f"- 任务 ID：`{report.task_id}`",
            f"- 计划 ID：`{report.plan_id}`",
            f"- 报告版本：`{report.report_version}`",
            f"- 数据版本：`{report.data_version}`",
            f"- 审核状态：`{report.review_status.value}`",
            f"- 生成时间：`{report.created_at}`",
            "",
            "## 声明",
        ]
        for claim in report.claims:
            lines.extend(cls._markdown_claim(claim))
        return "\n".join(lines) + "\n"

    @classmethod
    def to_html(cls, report: ResearchReport) -> str:
        """生成语义化 HTML，并转义声明文本和所有可显示字段。"""
        cls._validate(report)
        metadata = "".join(
            f"<li><strong>{escape(label)}：</strong><code>{escape(value)}</code></li>"
            for label, value in (
                ("报告 ID", report.report_id), ("任务 ID", report.task_id),
                ("计划 ID", report.plan_id), ("报告版本", str(report.report_version)),
                ("数据版本", report.data_version), ("审核状态", report.review_status.value),
                ("生成时间", report.created_at),
            )
        )
        claims = "".join(cls._html_claim(claim) for claim in report.claims)
        return f"<!doctype html><html lang=\"zh-CN\"><body><article data-report-id=\"{escape(report.report_id, quote=True)}\"><h1>研究报告</h1><ul>{metadata}</ul><section><h2>声明</h2>{claims}</section></article></body></html>"

    @staticmethod
    def _validate(report: ResearchReport) -> None:
        if not isinstance(report, ResearchReport):
            raise ValueError("report 必须是 ResearchReport")

    @staticmethod
    def _markdown_claim(claim: Claim) -> list[str]:
        lines = ["", f"### 声明 `{claim.claim_id}`", "", claim.text, "", f"- 依据类型：`{claim.support_kind.value}`"]
        for label, values in (("事实", claim.fact_ids), ("计算", claim.calculation_ids), ("来源", claim.source_ids)):
            if values:
                lines.append(f"- {label}：" + "、".join(f"`{value}`" for value in values))
        if claim.analysis_label is not None:
            lines.append(f"- 分析标签：{claim.analysis_label}")
        return lines

    @staticmethod
    def _html_claim(claim: Claim) -> str:
        evidence = "".join(
            f"<li>{escape(label)}：<code>{escape(value)}</code></li>"
            for label, values in (("事实", claim.fact_ids), ("计算", claim.calculation_ids), ("来源", claim.source_ids))
            for value in values
        )
        if claim.analysis_label is not None:
            evidence += f"<li>分析标签：{escape(claim.analysis_label)}</li>"
        return f"<section data-claim-id=\"{escape(claim.claim_id, quote=True)}\"><h3>声明 <code>{escape(claim.claim_id)}</code></h3><p>{escape(claim.text)}</p><p>依据类型：<code>{escape(claim.support_kind.value)}</code></p><ul>{evidence}</ul></section>"
