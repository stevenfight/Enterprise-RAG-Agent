"""B2.8 代码审查缺陷的回归测试。"""

import ast
import types

import pytest

from src.evaluation.thresholds import load_thresholds
from src.tools.verify_tool import VerifyTool
from src.verified_financial_facts import VerifiedFinancialFactRegistry


def test_verify_tool_matches_equal_zero_values():
    result = VerifyTool().run(
        claim="该指标为0亿元",
        source_text="经审计确认，该指标为0亿元，较上年有所变化。",
    )

    assert result.data["valid"] is True
    assert result.data["match_details"][0]["relative_error"] == 0.0


def test_verify_tool_preserves_negative_sign_and_large_units():
    tool = VerifyTool()

    negative = tool._extract_numbers("净利润-1.5亿元")
    trillion = tool._extract_numbers("总资产1.5万亿元")
    hundred_billion = tool._extract_numbers("营业收入2千亿元")

    assert negative[0]["value"] == -1.5
    assert negative[0]["unit"] == "亿"
    assert trillion[0]["unit"] == "万亿"
    assert tool._scale_to_unit(trillion[0]["value"], "万亿", "亿") == 15000
    assert hundred_billion[0]["unit"] == "千亿"
    assert tool._scale_to_unit(hundred_billion[0]["value"], "千亿", "亿") == 2000


def test_verify_tool_uses_unrounded_error_for_match_decision():
    result = VerifyTool().run(
        claim="营业收入105.005亿元",
        source_text="经审计确认，营业收入为100亿元，数据完整。",
    )

    detail = result.data["match_details"][0]
    assert detail["relative_error"] > 0.05
    assert detail["matched"] is False


@pytest.mark.parametrize("high_risk_failure_limit", ["1", 1.2, -1, True])
def test_thresholds_reject_invalid_high_risk_failure_limit(tmp_path, high_risk_failure_limit):
    path = tmp_path / "thresholds.yaml"
    path.write_text(
        "minimum_pass_rate: 0.95\n"
        f"high_risk_failure_limit: {high_risk_failure_limit!r}\n"
        "claim_level_evidence_support: enabled\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_thresholds(path)


def test_thresholds_reject_boolean_minimum_pass_rate(tmp_path):
    path = tmp_path / "thresholds.yaml"
    path.write_text(
        "minimum_pass_rate: true\n"
        "high_risk_failure_limit: 0\n"
        "claim_level_evidence_support: enabled\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_thresholds(path)


def test_footer_label_uses_current_page_not_total_page(monkeypatch):
    from src.text_splitter import _extract_footer_page_label

    page = types.SimpleNamespace(
        rect=types.SimpleNamespace(height=1000),
        get_text=lambda mode=None: (
            [(0, 900, 500, 950, "第 12 页 共 222 页", 0, 0)]
            if mode == "blocks" else "第 12 页 共 222 页"
        ),
    )

    assert _extract_footer_page_label(page, page_count=222) == "12"


def test_streamlit_uses_src_package_imports():
    tree = ast.parse(open("app_streamlit.py", encoding="utf-8").read())
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert "src.retrieval" in imported_modules
    assert "src.query_processor" in imported_modules
    assert "src.conversation" in imported_modules
    assert "src.tools.verify_tool" in imported_modules
    assert "src.planner" in imported_modules
    assert "src.reflector" in imported_modules
    assert not any(module.split(".")[0] in {"retrieval", "query_processor", "conversation", "tools", "planner", "reflector"} for module in imported_modules)


def test_empty_company_list_is_not_available():
    comparison = VerifiedFinancialFactRegistry().get_comparison(
        metric_key="operating_revenue",
        fiscal_year=2024,
        companies=[],
    )

    assert comparison == {"available": False, "items": []}
