# -*- coding: utf-8 -*-
"""VerifyTool 年报表格单位上下文测试。"""

from src.tools.verify_tool import VerifyTool


def test_verify_tool_applies_table_amount_unit_context_to_bare_cells():
    """表格单元格没有重复单位时，应使用表格前的金额单位声明。"""
    source_text = (
        "除特别注明外，金额单位为人民币百万元。"
        "<table><tr><td>项目</td><td>2024年</td><td>2023年</td></tr>"
        "<tr><td>营业收入</td><td>1,040,759</td><td>1,009,309</td><td>3.1%</td></tr></table>"
    )

    tool = VerifyTool()
    source_numbers = tool._extract_source_numbers(source_text)
    assert source_numbers[0]["unit"] == "百万"
    assert source_numbers[0]["currency"] == "人民币"
    assert source_numbers[-1]["unit"] == "%"
    assert source_numbers[-1]["currency"] == ""

    result = tool.run(
        claim="中国移动2024年营业收入为人民币10,408亿元",
        source_text=source_text,
    )

    assert result.data["valid"] is True
    assert result.data["matched_count"] == 1
