"""M2.1 可解释 PageRouter：区分 text/table/chart/scan/mixed，并证明纯文本页不调用视觉模型。"""

import pytest

from src.page_router import PageRouter, PageSignals


def _signals(**overrides):
    """构造单页信号包，默认为一个只有正文文本的普通页面。"""
    base = dict(
        page_number=1,
        text_layer_chars=1200,
        html_table_count=0,
        md_table_count=0,
        image_count=0,
        chart_region_count=0,
        table_region_count=0,
    )
    base.update(overrides)
    return PageSignals(**base)


def test_text_page_does_not_request_vision():
    """纯文本页路由结果必须为 text 且不请求视觉模型，决策理由可审计。"""
    router = PageRouter()

    decision = router.route(_signals())

    assert decision.page_number == 1
    assert decision.page_type == "text"
    assert decision.use_vision is False
    assert decision.reasons
    assert any("文本" in reason for reason in decision.reasons)


def test_table_chart_scan_mixed_are_distinguished():
    """表格、图表、扫描、混合四种页面类型按信号区分。"""
    router = PageRouter()

    table_decision = router.route(_signals(html_table_count=2, table_region_count=1))
    chart_decision = router.route(_signals(chart_region_count=1))
    scan_decision = router.route(_signals(text_layer_chars=0))
    mixed_decision = router.route(_signals(md_table_count=1, image_count=2))

    assert table_decision.page_type == "table"
    assert chart_decision.page_type == "chart"
    assert scan_decision.page_type == "scan"
    assert mixed_decision.page_type == "mixed"


def test_vision_requesting_types_and_table_policy():
    """扫描页/图表页/混合页请求视觉；表格页不直接请求（按 M2.5 复杂度门禁另行决策）。"""
    router = PageRouter()

    scan_decision = router.route(_signals(text_layer_chars=0))
    chart_decision = router.route(_signals(chart_region_count=1))
    mixed_decision = router.route(_signals(html_table_count=1, chart_region_count=1))
    table_decision = router.route(_signals(html_table_count=2))

    assert scan_decision.use_vision is True
    assert chart_decision.use_vision is True
    assert mixed_decision.use_vision is True
    assert table_decision.use_vision is False

    for decision in (scan_decision, chart_decision, mixed_decision, table_decision):
        assert decision.reasons


def test_low_text_page_with_table_signal_is_not_scan():
    """有文本层但字符很少、且带表格信号的页面不误判为扫描页。"""
    router = PageRouter()

    decision = router.route(_signals(text_layer_chars=10, html_table_count=1))

    assert decision.page_type == "table"
    assert decision.reasons
