"""M2.2 MinerU 表格结构适配器：把 MinerU HTML/Markdown 表格解析为结构化真值。

结构化真值只来自 MinerU 原文，保留多级表头、row/colspan、脚注、单位、期间和原始值；
本模块与 preprocess_table_text 的检索扁平化链路完全无关（扁平文本不得反推表格真值）。
"""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass
class TableCell:
    """结构化单元格：原始文本、起始行列位置、跨行跨列关系与表头标记。"""

    text: str
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False


@dataclass
class TableStructure:
    """结构化表格：来源格式、题注与按文档顺序排列的单元格列表。"""

    source_format: str
    caption: str = ""
    cells: list = field(default_factory=list)

    def grid(self):
        """展开 row/colspan 后的网格视图：按（行, 列）读取原始文本。"""
        if not self.cells:
            return []
        max_row = max(cell.row + cell.row_span - 1 for cell in self.cells)
        max_col = max(cell.col + cell.col_span - 1 for cell in self.cells)
        grid = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]
        for cell in self.cells:
            for row in range(cell.row, cell.row + cell.row_span):
                for col in range(cell.col, cell.col + cell.col_span):
                    grid[row][col] = cell.text
        return grid


@dataclass(frozen=True)
class TablePage:
    """表格所在物理页；跨页判定只读取此对象，不修改表格真值。"""

    page_number: int
    table: TableStructure


@dataclass(frozen=True)
class CrossPageTableRelation:
    """相邻页表格的保守续表判定结果。"""

    previous_page_number: int
    next_page_number: int
    status: str
    is_continuation: bool
    requires_review: bool
    reasons: tuple[str, ...]


def _normalized_caption(caption):
    """归一化常见续表标识，仅用于比较，不改变原始题注。"""
    normalized = re.sub(r"\s+", "", caption or "")
    normalized = normalized.replace("（续）", "").replace("(续)", "")
    return re.sub(r"续表$|续$", "", normalized)


def _header_signature(table):
    """提取逐行表头与列数；没有显式表头时拒绝自动合并。"""
    header_rows = sorted({cell.row for cell in table.cells if cell.is_header})
    grid = table.grid()
    if not header_rows or not grid:
        return (), 0
    return tuple(tuple(grid[row]) for row in header_rows), max(len(row) for row in grid)


def assess_cross_page_continuation(previous, following):
    """仅在页码相邻、题注、表头与列结构均兼容时确认续表。"""
    reasons = []
    page_adjacent = following.page_number == previous.page_number + 1
    if page_adjacent:
        reasons.append("物理页相邻")
    else:
        reasons.append("物理页不相邻")

    previous_caption = _normalized_caption(previous.table.caption)
    following_caption = _normalized_caption(following.table.caption)
    captions_compatible = bool(previous_caption and following_caption and previous_caption == following_caption)
    if captions_compatible:
        reasons.append("题注兼容")
    else:
        reasons.append("题注缺失或不兼容")

    previous_headers, previous_columns = _header_signature(previous.table)
    following_headers, following_columns = _header_signature(following.table)
    headers_compatible = bool(previous_headers and previous_headers == following_headers)
    if headers_compatible:
        reasons.append("表头兼容")
    else:
        reasons.append("表头缺失或不兼容")

    columns_compatible = bool(previous_columns and previous_columns == following_columns)
    if columns_compatible:
        reasons.append("列结构兼容")
    else:
        reasons.append("列结构不兼容")

    confirmed = page_adjacent and captions_compatible and headers_compatible and columns_compatible
    if confirmed:
        return CrossPageTableRelation(
            previous.page_number,
            following.page_number,
            "confirmed",
            True,
            False,
            tuple(reasons),
        )
    reasons.append("证据不足，保持分离并待确认")
    return CrossPageTableRelation(
        previous.page_number,
        following.page_number,
        "candidate",
        False,
        True,
        tuple(reasons),
    )


def _positive_int(raw):
    """把 HTML rowspan/colspan 属性解析为正整数，非法值按 1 处理。"""
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return 1
    return value if value >= 1 else 1


class _MinerUHtmlTableParser(HTMLParser):
    """基于标准库 HTMLParser 的 MinerU HTML 表格解析器，不引入第三方依赖。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self.caption_parts = []
        self._table_depth = 0
        self._row_index = -1
        self._in_caption = False
        self._cell_draft = None
        self._occupied = set()

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table_depth += 1
            return
        if self._table_depth != 1:
            return
        if tag == "caption":
            self._in_caption = True
        elif tag == "tr":
            self._row_index += 1
        elif tag in ("td", "th") and self._row_index >= 0:
            attr_map = dict(attrs)
            col = self._next_free_col(self._row_index)
            self._cell_draft = {
                "text_parts": [],
                "row": self._row_index,
                "col": col,
                "row_span": _positive_int(attr_map.get("rowspan")),
                "col_span": _positive_int(attr_map.get("colspan")),
                "is_header": tag == "th",
            }

    def handle_data(self, data):
        if self._table_depth != 1:
            return
        if self._in_caption:
            self.caption_parts.append(data)
        elif self._cell_draft is not None:
            self._cell_draft["text_parts"].append(data)

    def handle_endtag(self, tag):
        if tag == "table":
            if self._table_depth > 0:
                self._table_depth -= 1
            return
        if self._table_depth != 1:
            return
        if tag == "caption":
            self._in_caption = False
        elif tag in ("td", "th") and self._cell_draft is not None:
            self._finish_cell()

    def _next_free_col(self, row):
        """为当前行寻找下一个未被跨行跨列覆盖的列位置。"""
        col = 0
        while (row, col) in self._occupied:
            col += 1
        return col

    def _finish_cell(self):
        """把单元格草稿固化为 TableCell，并登记其 span 覆盖的网格位置。"""
        draft = self._cell_draft
        self._cell_draft = None
        cell = TableCell(
            text="".join(draft["text_parts"]).strip(),
            row=draft["row"],
            col=draft["col"],
            row_span=draft["row_span"],
            col_span=draft["col_span"],
            is_header=draft["is_header"],
        )
        self.cells.append(cell)
        for row in range(cell.row, cell.row + cell.row_span):
            for col in range(cell.col, cell.col + cell.col_span):
                self._occupied.add((row, col))


def parse_html_table(html):
    """解析 MinerU HTML 表格，保留多级表头（row/colspan）、题注与原始单元格值。"""
    parser = _MinerUHtmlTableParser()
    parser.feed(html)
    parser.close()
    return TableStructure(
        source_format="html",
        caption="".join(parser.caption_parts).strip(),
        cells=parser.cells,
    )


def _split_markdown_row(line):
    """切分一行 Markdown 表格行，去首尾竖线并保留单元格原始文本（外层去空白）。"""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [segment.strip() for segment in stripped.split("|")]


def _is_markdown_separator(line):
    """判断一行是否为 Markdown 表头分隔行（仅含连字符、冒号与空白）。"""
    stripped = line.strip()
    if not stripped:
        return False
    segments = _split_markdown_row(stripped)
    return bool(segments) and all(
        segment and set(segment) <= set("-: ") for segment in segments
    )


def parse_markdown_table(markdown):
    """解析 MinerU Markdown 表格，保留空单元格、单位、期间与原始文本。"""
    lines = markdown.splitlines()
    header_index = -1
    for index in range(len(lines) - 1):
        if "|" in lines[index] and _is_markdown_separator(lines[index + 1]):
            header_index = index
            break
    if header_index < 0:
        return TableStructure(source_format="markdown", caption="", cells=[])
    body_lines = []
    for line in lines[header_index + 2:]:
        if "|" not in line:
            break
        body_lines.append(line)
    cells = []
    all_rows = [lines[header_index]] + body_lines
    for row_index, line in enumerate(all_rows):
        for col_index, text in enumerate(_split_markdown_row(line)):
            cells.append(
                TableCell(
                    text=text,
                    row=row_index,
                    col=col_index,
                    is_header=(row_index == 0),
                )
            )
    return TableStructure(source_format="markdown", caption="", cells=cells)
