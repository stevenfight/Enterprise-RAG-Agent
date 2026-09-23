"""M2.2 MinerU 表格结构适配器：保留多级表头、row/colspan、脚注、单位、期间和原始值。

结构化真值只来自 MinerU HTML/Markdown 原文，不从 preprocess_table_text 的扁平结果反推。
"""

import src.table_structure as table_structure
from src.table_structure import parse_html_table, parse_markdown_table


def test_html_table_preserves_colspan_and_raw_values():
    """HTML 表头跨列（colspan）与原始值必须原样保留，网格按 span 展开。"""
    html = (
        "<table>"
        "<caption>合并利润表</caption>"
        '<tr><th colspan="2">2024年度</th><th>2023年度</th></tr>'
        "<tr><td>营业收入（万元）</td><td>1,234.56注1</td><td>1,117.05</td></tr>"
        "</table>"
    )
    structure = parse_html_table(html)
    assert structure.source_format == "html"
    assert structure.caption == "合并利润表"
    grid = structure.grid()
    assert grid[0] == ["2024年度", "2024年度", "2023年度"]
    assert grid[1] == ["营业收入（万元）", "1,234.56注1", "1,117.05"]
    spanned = [cell for cell in structure.cells if cell.col_span == 2]
    assert len(spanned) == 1
    assert spanned[0].text == "2024年度"
    assert spanned[0].row == 0 and spanned[0].col == 0
    assert spanned[0].is_header is True


def test_html_table_preserves_rowspan_multilevel_header():
    """HTML 表头跨行（rowspan）构成多级表头时，跨行关系与被覆盖格必须保留。"""
    html = (
        "<table>"
        '<tr><th rowspan="2">项目</th><th>2024年度</th></tr>'
        "<tr><th>金额（万元）</th></tr>"
        "<tr><td>营业收入</td><td>1,234.56</td></tr>"
        "</table>"
    )
    structure = parse_html_table(html)
    grid = structure.grid()
    assert grid[0] == ["项目", "2024年度"]
    assert grid[1] == ["项目", "金额（万元）"]
    assert grid[2] == ["营业收入", "1,234.56"]
    spanned = [cell for cell in structure.cells if cell.row_span == 2]
    assert len(spanned) == 1
    assert spanned[0].text == "项目"
    assert spanned[0].is_header is True


def test_markdown_table_preserves_empty_cells_units_and_periods():
    """Markdown 表格必须保留空单元格、单位、期间与原始文本，不做扁平化改写。"""
    markdown = (
        "| 项目 | 2024年度 | 2023年度 |\n"
        "| --- | --- | --- |\n"
        "| 营业收入（万元） | 1,234.56 | 1,117.05 |\n"
        "| 净利润 |  | 892.30 |\n"
    )
    structure = parse_markdown_table(markdown)
    assert structure.source_format == "markdown"
    grid = structure.grid()
    assert grid[0] == ["项目", "2024年度", "2023年度"]
    assert grid[2] == ["净利润", "", "892.30"]
    empty_cells = [cell for cell in structure.cells if cell.text == ""]
    assert len(empty_cells) == 1
    assert empty_cells[0].row == 2 and empty_cells[0].col == 1
    assert structure.cells[0].is_header is True


def test_structured_truth_not_derived_from_flat_text():
    """结构化真值链不依赖 preprocess_table_text：模块零导入且排版符号原样保留。"""
    imported_from_retrieval = [
        name
        for name, obj in vars(table_structure).items()
        if getattr(obj, "__module__", None) == "src.retrieval"
    ]
    assert imported_from_retrieval == []
    html = (
        "<table>"
        "<tr><td>项目:注释-注1</td><td>1,234.56</td></tr>"
        "</table>"
    )
    structure = parse_html_table(html)
    assert structure.grid()[0] == ["项目:注释-注1", "1,234.56"]
