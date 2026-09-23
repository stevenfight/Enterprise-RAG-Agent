"""M2.1 可解释 PageRouter：按页面信号区分 text/table/chart/scan/mixed。

路由为确定性规则，所有决策携带可审计的理由（reasons）；
纯文本页不请求视觉模型，表格页的视觉调用按复杂度门禁另行决策（M2.5）。
"""

from dataclasses import dataclass


@dataclass
class PageSignals:
    """单页可解释信号包：由调用方从 PDF 文本层、解析 Markdown 与视觉区域记录构建。"""

    page_number: int
    text_layer_chars: int = 0
    html_table_count: int = 0
    md_table_count: int = 0
    image_count: int = 0
    chart_region_count: int = 0
    table_region_count: int = 0


@dataclass
class PageRouteDecision:
    """单页路由决策：页面类型、是否请求视觉模型、可审计理由。"""

    page_number: int
    page_type: str
    use_vision: bool
    reasons: list


class PageRouter:
    """可解释页面路由器：确定性分类，纯文本页绝不请求视觉模型。"""

    def route(self, signals):
        """按信号顺序判定页面类型：scan 优先于 mixed，mixed 优先于单一类型。"""
        reasons = []
        text_layer_chars = int(signals.text_layer_chars)
        table_signal_count = (
            int(signals.html_table_count)
            + int(signals.md_table_count)
            + int(signals.table_region_count)
        )
        chart_signal_count = (
            int(signals.chart_region_count)
            + int(signals.image_count)
        )

        if text_layer_chars <= 0:
            reasons.append("无文本层")
            return PageRouteDecision(
                page_number=signals.page_number,
                page_type="scan",
                use_vision=True,
                reasons=reasons,
            )

        reasons.append(f"文本层字符数 {text_layer_chars}")

        if table_signal_count > 0 and chart_signal_count > 0:
            reasons.append(f"表格信号 {table_signal_count} 处、图表信号 {chart_signal_count} 处并存")
            return PageRouteDecision(
                page_number=signals.page_number,
                page_type="mixed",
                use_vision=True,
                reasons=reasons,
            )

        if table_signal_count > 0:
            reasons.append(f"表格信号 {table_signal_count} 处")
            return PageRouteDecision(
                page_number=signals.page_number,
                page_type="table",
                use_vision=False,
                reasons=reasons,
            )

        if chart_signal_count > 0:
            reasons.append(f"图表信号 {chart_signal_count} 处")
            return PageRouteDecision(
                page_number=signals.page_number,
                page_type="chart",
                use_vision=True,
                reasons=reasons,
            )

        reasons.append("仅文本内容，无需视觉模型")
        return PageRouteDecision(
            page_number=signals.page_number,
            page_type="text",
            use_vision=False,
            reasons=reasons,
        )
