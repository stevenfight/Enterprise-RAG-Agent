"""
文本分块工具 (Small-to-Big 策略)

将 Markdown 格式的报告按 token 数切分为两级文本块：
  - 父块 (Parent Chunk): ~500 tokens，用于 LLM 上下文
  - 子块 (Child Chunk): ~150 tokens，用于 Embedding 检索

检索时用子块匹配，返回对应父块的完整文本。

输出 JSON 结构：
{
  "metainfo": { "sha1": "...", "company_name": "...", "file_name": "..." },
  "content": { "parent_chunks": [
    {
      "id": 0,
      "lines": [1, 28],
      "tokens": 486,
      "pages": [1, 1],
      "source_file": "电信2024年度报告.pdf",
      "text": "...(完整父块文本)...",
      "child_chunks": [
        { "id": "0-0", "parent_id": 0, "tokens": 148, "text": "..." },
        { "id": "0-1", "parent_id": 0, "tokens": 152, "text": "..." },
        { "id": "0-2", "parent_id": 0, "tokens": 143, "text": "..." }
      ]
    }, ...
  ] }
}
"""

import csv
import json
import re
from pathlib import Path

import tiktoken

ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    return len(ENCODING.encode(text))


# 文档类型标签分类规则：按文件名子串匹配，命中即返回对应标签列表
TAG_RULES = [
    ("annual_report", ["年度报告", "年报", "【财报】"]),
    ("research_report", ["证券", "研报", "研究报"]),
    ("meeting_minutes", ["调研纪要", "会议纪要", "投资者关系"]),
]


def classify_doc_tags(file_name):
    """按文件名子串将文档分类为标签列表

    Args:
        file_name: 文件名（可含扩展名）

    Returns:
        list[str]: 命中的标签列表，未命中返回 ["other"]
    """
    name = file_name or ""
    for tag, keywords in TAG_RULES:
        if any(k in name for k in keywords):
            return [tag]
    return ["other"]


def _classify_doc_type(source_file, tags=None):
    """判定文档类型：优先使用已有 tags，缺省时回退文件名分类

    Args:
        source_file: 来源文件名
        tags: 已打标签列表（可为 None 或空列表）

    Returns:
        str: 文档类型，如 "annual_report" / "research_report" / "meeting_minutes" / "other"
    """
    if tags:
        return tags[0]
    return classify_doc_tags(source_file)[0]


def load_subset_csv(csv_path):
    csv_path = Path(csv_path)
    mapping = {}
    if not csv_path.exists():
        return mapping

    for encoding in ["utf-8", "gbk"]:
        try:
            with open(csv_path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    file_name = row.get("file_name", "").strip()
                    sha1 = row.get("sha1", "").strip()
                    company_name = row.get("company_name", "").strip()
                    if file_name:
                        stem = Path(file_name).stem
                        mapping[stem] = {
                            "sha1": sha1,
                            "company_name": company_name,
                        }
            break
        except UnicodeDecodeError:
            continue

    return mapping


_PHYSICAL_PAGE_RANGE_RE = re.compile(
    r"<!--\s*pdf-physical-page-range:\s*(\d+)\s*-\s*(\d+)\s*-->"
)


def build_line_page_map(pdf_path, md_path=None):
    try:
        import fitz
    except ImportError:
        return None

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return None

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return None

    page_char_ranges = []
    full_text = ""
    char_pos = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        page_char_ranges.append((char_pos, char_pos + len(text), page_num + 1))
        full_text += text
        char_pos += len(text)
    doc.close()

    md_text = ""
    md_file = Path(md_path) if md_path else None
    if md_file is None:
        md_stem = pdf_path.stem
        md_file = pdf_path.parent.parent / "debug_data" / "03_reports_markdown" / (md_stem + ".md")
    for encoding in ["utf-8", "gbk"]:
        try:
            if md_file.exists():
                md_text = md_file.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue

    def line_to_page(line_number, md_lines):
        if not page_char_ranges:
            return None
        marker_ranges = []
        for marker_line, marker_text in enumerate(md_lines, start=1):
            match = _PHYSICAL_PAGE_RANGE_RE.fullmatch(marker_text.strip())
            if match:
                marker_ranges.append((marker_line, int(match.group(1)), int(match.group(2))))
        if marker_ranges:
            active = None
            for marker in marker_ranges:
                if marker[0] <= line_number:
                    active = marker
                else:
                    break
            if active:
                marker_line, start_page, end_page = active
                next_marker_line = next(
                    (marker[0] for marker in marker_ranges if marker[0] > marker_line),
                    len(md_lines) + 1,
                )
                local_start = marker_line + 1
                local_end = max(local_start, next_marker_line - 1)
                ratio = (line_number - local_start) / max(local_end - local_start, 1)
                ratio = max(0.0, min(1.0, ratio))
                return min(end_page, start_page + int(round(ratio * (end_page - start_page))))
        char_offset = 0
        for i, line in enumerate(md_lines):
            if i + 1 == line_number:
                break
            char_offset += len(line) + 1

        ratio = char_offset / max(len(md_text), 1)
        pdf_char_pos = int(ratio * len(full_text))

        for start, end, page in page_char_ranges:
            if start <= pdf_char_pos < end:
                return page
        return page_char_ranges[-1][2] if page_char_ranges else None

    return line_to_page


_PAGE_LABEL_LINE_RE = re.compile(
    r"(?:^|[\s|])(?:第\s*)?([0-9]{1,4}|[ivxlcdm]{1,8})(?:\s*页)?\s*$",
    re.IGNORECASE,
)
_EXPLICIT_PAGE_LABEL_RE = re.compile(
    r"第\s*([0-9]{1,4})\s*页\s*(?:/\s*)?共\s*([0-9]{1,4})\s*页"
)
_SLASH_PAGE_LABEL_RE = re.compile(r"(?<![0-9])([0-9]{1,4})\s*/\s*([0-9]{1,4})(?![0-9])")


def _expand_pdf_page_labels(raw_labels, page_count):
    """展开 PDF 的显式 page label 元数据，不从相邻页面推测页码。"""
    if not isinstance(raw_labels, list) or not raw_labels:
        return {}

    ranges = []
    for item in raw_labels:
        if not isinstance(item, dict):
            continue
        try:
            start_page = int(item.get("startpage", -1))
        except (TypeError, ValueError):
            continue
        if start_page < 0 or start_page >= page_count:
            continue
        ranges.append((start_page, item))
    ranges.sort(key=lambda value: value[0])

    result = {}
    for index, (start_page, item) in enumerate(ranges):
        end_page = ranges[index + 1][0] if index + 1 < len(ranges) else page_count
        prefix = str(item.get("prefix", ""))
        style = str(item.get("style", "D"))
        try:
            first_number = int(item.get("firstpagenum", 1))
        except (TypeError, ValueError):
            first_number = 1
        for physical_page in range(start_page, end_page):
            number = first_number + physical_page - start_page
            if style in {"r", "R"}:
                value = _to_roman(number, upper=style == "R")
            else:
                value = str(number)
            result[physical_page + 1] = f"{prefix}{value}"
    return result


def _to_roman(number, upper=False):
    if number < 1:
        return str(number)
    values = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
              (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
              (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    result = []
    remaining = number
    for value, symbol in values:
        count, remaining = divmod(remaining, value)
        result.append(symbol * count)
    roman = "".join(result)
    return roman if upper else roman.lower()


def _extract_footer_page_label(page, page_count=None):
    """仅接受页面底部文本中直接出现的独立页码。"""
    try:
        height = float(page.rect.height)
        page_text = page.get_text()
        blocks = page.get_text("blocks")
    except Exception:
        return None
    explicit_match = _EXPLICIT_PAGE_LABEL_RE.search(str(page_text))
    if explicit_match:
        return explicit_match.group(1)
    slash_match = _SLASH_PAGE_LABEL_RE.search(str(page_text))
    if slash_match and page_count is not None and int(slash_match.group(2)) == page_count:
        return slash_match.group(1)

    candidates = []
    for block in blocks or []:
        if not isinstance(block, (tuple, list)) or len(block) < 5:
            continue
        try:
            y0 = float(block[1])
        except (TypeError, ValueError):
            continue
        if y0 < height * 0.85:
            continue
        block_lines = [line.strip() for line in str(block[4]).splitlines() if line.strip()]
        if not block_lines or len(block_lines) > 3:
            continue
        for line in block_lines[-1:]:
            normalized_line = line.strip().strip("-—_ ")
            match = _PAGE_LABEL_LINE_RE.search(normalized_line)
            if match:
                candidates.append(match.group(1))
    return candidates[-1] if candidates else None


def build_pdf_page_labels(pdf_path):
    """返回物理页序到文档印刷页码的直接证据映射。"""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
    except Exception:
        return {}
    try:
        explicit = _expand_pdf_page_labels(doc.get_page_labels(), len(doc))
        if explicit:
            return explicit
        return {
            page_number: label
            for page_number in range(1, len(doc) + 1)
            if (label := _extract_footer_page_label(doc[page_number - 1], len(doc))) is not None
        }
    finally:
        doc.close()


def _split_text_by_paragraphs(text):
    paragraphs = []
    current = []
    for line in text.split("\n"):
        if line.strip() == "":
            if current:
                paragraphs.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs


def split_into_child_chunks(parent_text, parent_id, child_size=150, child_overlap=30):
    paragraphs = _split_text_by_paragraphs(parent_text)

    para_tokens = []
    for p in paragraphs:
        t = count_tokens(p)
        para_tokens.append({"text": p, "tokens": t})

    children = []
    i = 0
    while i < len(para_tokens):
        child_segs = []
        child_token_count = 0

        j = i
        while j < len(para_tokens):
            seg = para_tokens[j]
            if child_token_count + seg["tokens"] > child_size and child_token_count > 0:
                break
            child_segs.append(seg)
            child_token_count += seg["tokens"]
            j += 1

        if not child_segs:
            child_segs = [para_tokens[i]]
            j = i + 1

        child_text = "\n\n".join(s["text"] for s in child_segs)
        child_idx = len(children)
        children.append({
            "id": f"{parent_id}-{child_idx}",
            "parent_id": parent_id,
            "tokens": count_tokens(child_text),
            "text": child_text,
        })

        if j >= len(para_tokens):
            break

        overlap_tokens = 0
        next_i = j
        for k in range(j - 1, i, -1):
            if k < len(para_tokens):
                overlap_tokens += para_tokens[k]["tokens"]
                next_i = k
                if overlap_tokens >= child_overlap:
                    break
        i = next_i if next_i > i else j

    return children


def split_markdown_file(md_path, chunk_size=500, chunk_overlap=100,
                        child_size=150, child_overlap=30, pdf_path=None):
    md_path = Path(md_path)
    for encoding in ["utf-8", "gbk"]:
        try:
            lines = md_path.read_text(encoding=encoding).splitlines()
            break
        except UnicodeDecodeError:
            continue
    else:
        lines = md_path.read_text(encoding="utf-8", errors="replace").splitlines()

    if not lines:
        return []

    line_to_page_fn = None
    page_labels = {}
    if pdf_path:
        line_to_page_fn = build_line_page_map(pdf_path, md_path=md_path)
        page_labels = build_pdf_page_labels(pdf_path)

    segments = []
    current_text = []
    start_line = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            if current_text:
                seg_text = "\n".join(current_text)
                segments.append({
                    "text": seg_text,
                    "start_line": start_line + 1,
                    "end_line": i,
                    "tokens": count_tokens(seg_text),
                })
                current_text = []
        else:
            if not current_text:
                start_line = i
            current_text.append(line)
    if current_text:
        seg_text = "\n".join(current_text)
        segments.append({
            "text": seg_text,
            "start_line": start_line + 1,
            "end_line": len(lines),
            "tokens": count_tokens(seg_text),
        })

    parent_chunks = []
    i = 0
    while i < len(segments):
        chunk_segs = []
        chunk_tokens = 0

        j = i
        while j < len(segments):
            seg = segments[j]
            if chunk_tokens + seg["tokens"] > chunk_size and chunk_tokens > 0:
                break
            chunk_segs.append(seg)
            chunk_tokens += seg["tokens"]
            j += 1

        if not chunk_segs:
            chunk_segs = [segments[i]]
            j = i + 1

        chunk_text = "\n\n".join(s["text"] for s in chunk_segs)
        chunk_text = _PHYSICAL_PAGE_RANGE_RE.sub("", chunk_text).strip()
        chunk_start_line = chunk_segs[0]["start_line"]
        chunk_end_line = chunk_segs[-1]["end_line"]

        pages = None
        if line_to_page_fn:
            p1 = line_to_page_fn(chunk_start_line, lines)
            p2 = line_to_page_fn(chunk_end_line, lines)
            if p1 and p2:
                pages = [p1, p2]

        parent_id = len(parent_chunks)
        child_chunks = split_into_child_chunks(
            chunk_text, parent_id, child_size, child_overlap
        )

        parent_data = {
            "id": parent_id,
            "lines": [chunk_start_line, chunk_end_line],
            "tokens": count_tokens(chunk_text),
            "text": chunk_text,
            "child_chunks": child_chunks,
        }
        if pages:
            parent_data["pages"] = pages
            document_pages = list(dict.fromkeys(
                page_labels[page] for page in pages if page in page_labels
            ))
            if document_pages:
                parent_data["document_pages"] = document_pages

        parent_chunks.append(parent_data)

        if j >= len(segments):
            break

        overlap_tokens = 0
        next_i = j
        for k in range(j - 1, i, -1):
            if k < len(segments):
                overlap_tokens += segments[k]["tokens"]
                next_i = k
                if overlap_tokens >= chunk_overlap:
                    break
        i = next_i if next_i > i else j

    return parent_chunks


def split_markdown_reports(md_dir, output_dir, subset_csv_path, pdf_dir=None,
                           chunk_size=500, chunk_overlap=100,
                           child_size=150, child_overlap=30):
    md_dir = Path(md_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mapping = load_subset_csv(subset_csv_path)

    md_files = sorted(md_dir.glob("*.md"))
    if not md_files:
        print(f"[错误] 未找到 Markdown 文件: {md_dir}")
        return

    pdf_dir = Path(pdf_dir) if pdf_dir else md_dir.parent.parent / "pdf_reports"

    print(f"[信息] 扫描到 {len(md_files)} 个 Markdown 文件")
    print(f"[信息] 父块参数: chunk_size={chunk_size} tokens, chunk_overlap={chunk_overlap} tokens")
    print(f"[信息] 子块参数: child_size={child_size} tokens, child_overlap={child_overlap} tokens")
    print(f"[信息] 输出目录: {output_dir}\n")

    total_parents = 0
    total_children = 0
    for md_path in md_files:
        stem = md_path.stem
        meta = mapping.get(stem, {"sha1": "", "company_name": ""})

        pdf_path = pdf_dir / (stem + ".pdf")

        parent_chunks = split_markdown_file(
            md_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
            child_size=child_size, child_overlap=child_overlap,
            pdf_path=pdf_path if pdf_path.exists() else None,
        )
        if not parent_chunks:
            print(f"  [跳过] {md_path.name}: 文件为空")
            continue

        for chunk in parent_chunks:
            chunk["source_file"] = stem + ".pdf"

        num_parents = len(parent_chunks)
        num_children = sum(len(c["child_chunks"]) for c in parent_chunks)
        total_parents += num_parents
        total_children += num_children

        has_pages = sum(1 for c in parent_chunks if "pages" in c)

        result = {
            "metainfo": {
                "sha1": meta["sha1"],
                "company_name": meta["company_name"],
                "file_name": md_path.name,
                "tags": classify_doc_tags(stem + ".pdf"),
            },
            "content": {
                "parent_chunks": parent_chunks,
            },
        }

        output_path = output_dir / (stem + ".json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        page_info = f", {has_pages}/{num_parents} 含页码" if has_pages > 0 else ""
        print(f"  [完成] {md_path.name} -> {stem}.json (父块:{num_parents}, 子块:{num_children}, 公司: {meta['company_name']}{page_info})")

    print(f"\n[汇总] 共处理 {len(md_files)} 个文件, 父块: {total_parents}, 子块: {total_children}")


def main():
    project_root = Path(__file__).resolve().parent.parent
    md_dir = project_root / "data" / "stock_data" / "debug_data" / "03_reports_markdown"
    output_dir = project_root / "data" / "stock_data" / "databases" / "chunked_reports"
    subset_csv_path = project_root / "data" / "stock_data" / "subset.csv"
    pdf_dir = project_root / "data" / "stock_data" / "pdf_reports"

    print("=" * 60)
    print("文本分块工具 (Small-to-Big 策略)")
    print("=" * 60)

    split_markdown_reports(md_dir, output_dir, subset_csv_path, pdf_dir=pdf_dir)

    print("\n" + "=" * 60)
    print("文本分块处理完成!")
    print(f"分块文件位置: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
