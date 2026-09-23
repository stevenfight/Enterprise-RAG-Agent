"""M2.3 保守跨页续表关系测试。"""

from src.table_structure import TablePage, assess_cross_page_continuation, parse_html_table


def _table(caption: str, header: str = "项目", columns: int = 2):
    header_cells = "".join(f"<th>{header if index == 0 else f'列{index + 1}'}</th>" for index in range(columns))
    data_cells = "".join(f"<td>值{index + 1}</td>" for index in range(columns))
    return parse_html_table(
        f"<table><caption>{caption}</caption><tr>{header_cells}</tr><tr>{data_cells}</tr></table>"
    )


def test_adjacent_pages_with_compatible_title_header_and_columns_are_confirmed_continuation():
    """只有四项证据齐全时才确认续表关系，且不修改原表格真值。"""
    previous = TablePage(8, _table("合并资产负债表"))
    following = TablePage(9, _table("合并资产负债表（续）"))

    relation = assess_cross_page_continuation(previous, following)

    assert relation.status == "confirmed"
    assert relation.is_continuation is True
    assert relation.previous_page_number == 8
    assert relation.next_page_number == 9
    assert "物理页相邻" in relation.reasons
    assert previous.table.caption == "合并资产负债表"


def test_missing_or_conflicting_evidence_keeps_tables_separate_as_candidate_relation():
    """标题、表头或列结构不兼容时必须保持分离，仅留下待确认关系。"""
    previous = TablePage(8, _table("合并资产负债表"))
    title_conflict = TablePage(9, _table("合并利润表"))
    header_conflict = TablePage(9, _table("合并资产负债表（续）", header="科目"))
    column_conflict = TablePage(9, _table("合并资产负债表（续）", columns=3))

    for following in (title_conflict, header_conflict, column_conflict):
        relation = assess_cross_page_continuation(previous, following)
        assert relation.status == "candidate"
        assert relation.is_continuation is False
        assert relation.requires_review is True


def test_non_adjacent_pages_are_never_merged_even_when_other_signals_match():
    """物理页不相邻时不得确认续表，避免跨段误合并。"""
    relation = assess_cross_page_continuation(
        TablePage(8, _table("合并资产负债表")),
        TablePage(10, _table("合并资产负债表（续）")),
    )

    assert relation.status == "candidate"
    assert relation.is_continuation is False
    assert "物理页不相邻" in relation.reasons
