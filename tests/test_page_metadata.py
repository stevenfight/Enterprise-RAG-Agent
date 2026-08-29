"""页码身份测试：物理页与文档印刷页必须分离。"""

import sys
import types


def _install_fake_fitz(monkeypatch, pages, labels=None):
    class FakePage:
        def __init__(self, text, blocks):
            self._text = text
            self._blocks = blocks
            self.rect = types.SimpleNamespace(height=1000)

        def get_text(self, mode=None):
            if mode == "blocks":
                return self._blocks
            return self._text

    class FakeDoc:
        def __init__(self):
            self.pages = pages

        def __len__(self):
            return len(self.pages)

        def __getitem__(self, index):
            return self.pages[index]

        def get_page_labels(self):
            return labels or []

        def close(self):
            pass

    fake_module = types.SimpleNamespace(open=lambda _path: FakeDoc())
    monkeypatch.setitem(sys.modules, "fitz", fake_module)


def test_pdf_page_labels_prefer_explicit_pdf_labels(monkeypatch, tmp_path):
    from src.text_splitter import build_pdf_page_labels

    pdf_path = tmp_path / "报告.pdf"
    pdf_path.write_bytes(b"%PDF")
    pages = [
        types.SimpleNamespace(get_text=lambda *_: "", rect=types.SimpleNamespace(height=1000)),
        types.SimpleNamespace(get_text=lambda *_: "", rect=types.SimpleNamespace(height=1000)),
    ]
    _install_fake_fitz(monkeypatch, pages, [{"startpage": 0, "prefix": "", "style": "D", "firstpagenum": 8}])

    assert build_pdf_page_labels(pdf_path) == {1: "8", 2: "9"}


def test_pdf_page_labels_read_footer_without_guessing(monkeypatch, tmp_path):
    from src.text_splitter import build_pdf_page_labels

    pdf_path = tmp_path / "报告.pdf"
    pdf_path.write_bytes(b"%PDF")
    pages = [
        types.SimpleNamespace(
            get_text=lambda *_: "正文",
            get_text_blocks=None,
            rect=types.SimpleNamespace(height=1000),
        ),
        types.SimpleNamespace(
            get_text=lambda mode=None: [(0, 900, 500, 950, "页脚\n- ii -\n", 0, 0)] if mode == "blocks" else "正文",
            rect=types.SimpleNamespace(height=1000),
        ),
    ]
    _install_fake_fitz(monkeypatch, pages)

    assert build_pdf_page_labels(pdf_path) == {2: "ii"}


def test_pdf_page_labels_do_not_treat_table_number_as_footer(monkeypatch, tmp_path):
    from src.text_splitter import build_pdf_page_labels

    pdf_path = tmp_path / "报告.pdf"
    pdf_path.write_bytes(b"%PDF")
    pages = [
        types.SimpleNamespace(
            get_text=lambda mode=None: (
                [(0, 700, 500, 950, "指标\n收入\n0\n", 0, 0)]
                if mode == "blocks" else "指标\n收入\n0\n"
            ),
            rect=types.SimpleNamespace(height=1000),
        )
    ]
    _install_fake_fitz(monkeypatch, pages)

    assert build_pdf_page_labels(pdf_path) == {}


def test_pdf_page_labels_accept_total_page_slash_format(monkeypatch, tmp_path):
    from src.text_splitter import build_pdf_page_labels

    pdf_path = tmp_path / "年报.pdf"
    pdf_path.write_bytes(b"%PDF")
    pages = [
        types.SimpleNamespace(
            get_text=lambda mode=None: (
                [(0, 800, 500, 950, "公司年报 1 / 2\n", 0, 0)]
                if mode == "blocks" else "公司年报 1 / 2\n"
            ),
            rect=types.SimpleNamespace(height=1000),
        ),
        types.SimpleNamespace(
            get_text=lambda mode=None: (
                [(0, 800, 500, 950, "公司年报 2 / 2\n", 0, 0)]
                if mode == "blocks" else "公司年报 2 / 2\n"
            ),
            rect=types.SimpleNamespace(height=1000),
        ),
    ]
    _install_fake_fitz(monkeypatch, pages)

    assert build_pdf_page_labels(pdf_path) == {1: "1", 2: "2"}


def test_document_page_number_can_start_after_cover(monkeypatch, tmp_path):
    from src.text_splitter import build_pdf_page_labels

    pdf_path = tmp_path / "年报.pdf"
    pdf_path.write_bytes(b"%PDF")
    pages = [
        types.SimpleNamespace(
            get_text=lambda mode=None: (
                [(0, 800, 500, 950, "封面\n", 0, 0)] if mode == "blocks" else "封面\n"
            ),
            rect=types.SimpleNamespace(height=1000),
        ),
        types.SimpleNamespace(
            get_text=lambda mode=None: (
                [(0, 800, 500, 950, "年报正文 1 / 2\n", 0, 0)]
                if mode == "blocks" else "年报正文 1 / 2\n"
            ),
            rect=types.SimpleNamespace(height=1000),
        ),
    ]
    _install_fake_fitz(monkeypatch, pages)

    assert build_pdf_page_labels(pdf_path) == {2: "1"}


def test_split_keeps_physical_pages_and_adds_document_pages(monkeypatch, tmp_path):
    from src.text_splitter import split_markdown_file

    pdf_path = tmp_path / "报告.pdf"
    pdf_path.write_bytes(b"%PDF")
    md_path = tmp_path / "报告.md"
    md_path.write_text("标题\n\n正文", encoding="utf-8")
    monkeypatch.setattr("src.text_splitter.build_line_page_map", lambda _path, **_kwargs: lambda line, _lines: 2)
    monkeypatch.setattr("src.text_splitter.build_pdf_page_labels", lambda _path: {2: "ii"})

    chunks = split_markdown_file(md_path, chunk_size=500, child_size=150, pdf_path=pdf_path)

    assert chunks[0]["pages"] == [2, 2]
    assert chunks[0]["document_pages"] == ["ii"]


def test_line_page_map_uses_hot_load_markdown_path_and_batch_markers(monkeypatch, tmp_path):
    from src.text_splitter import build_line_page_map

    pdf_path = tmp_path / "报告.pdf"
    md_path = tmp_path / "报告.md"
    pdf_path.write_bytes(b"%PDF")
    md_path.write_text(
        "<!-- pdf-physical-page-range: 1-150 -->\n" + "\n".join(["前半段"] * 4)
        + "\n<!-- pdf-physical-page-range: 151-300 -->\n" + "\n".join(["后半段"] * 4),
        encoding="utf-8",
    )
    _install_fake_fitz(
        monkeypatch,
        [types.SimpleNamespace(
            get_text=lambda *_: "page text",
            rect=types.SimpleNamespace(height=1000),
        ) for _ in range(300)],
    )
    monkeypatch.setattr("src.text_splitter.build_pdf_page_labels", lambda _path: {})

    line_to_page = build_line_page_map(pdf_path, md_path=md_path)
    lines = md_path.read_text(encoding="utf-8").splitlines()

    assert line_to_page(2, lines) <= 150
    assert line_to_page(7, lines) >= 151
