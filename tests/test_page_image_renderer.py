"""PDF 物理页图渲染与缓存的确定性测试。"""

from pathlib import Path

import fitz
import pytest


def _two_page_pdf(path: Path) -> None:
    document = fitz.open()
    first = document.new_page()
    first.draw_rect(fitz.Rect(0, 0, 100, 100), color=(1, 0, 0), fill=(1, 0, 0))
    second = document.new_page()
    second.draw_rect(fitz.Rect(0, 0, 100, 100), color=(0, 0, 1), fill=(0, 0, 1))
    document.save(path)
    document.close()


def test_page_renderer_creates_cached_page_and_thumbnail_from_physical_page(tmp_path: Path):
    from src.page_image_renderer import PageImageRenderer

    pdf_path = tmp_path / "report.pdf"
    _two_page_pdf(pdf_path)
    renderer = PageImageRenderer(tmp_path / "rendered")

    first = renderer.render("version-1", pdf_path, physical_page_number=2)
    second = renderer.render("version-1", pdf_path, physical_page_number=2)

    assert first.physical_page_number == 2
    assert first.created is True
    assert first.image_path.exists()
    assert first.thumbnail_path.exists()
    assert second.created is False
    assert second.artifact_id == first.artifact_id
    assert second.image_path == first.image_path


def test_page_renderer_rejects_out_of_range_or_unsafe_document_version_id(tmp_path: Path):
    from src.page_image_renderer import PageImageRenderer

    pdf_path = tmp_path / "report.pdf"
    _two_page_pdf(pdf_path)
    renderer = PageImageRenderer(tmp_path / "rendered")

    with pytest.raises(ValueError, match="物理页"):
        renderer.render("version-1", pdf_path, physical_page_number=3)
    with pytest.raises(ValueError, match="document_version_id"):
        renderer.render("../unsafe", pdf_path, physical_page_number=1)
    with pytest.raises(ValueError, match="document_version_id"):
        renderer.render(None, pdf_path, physical_page_number=1)


def test_page_renderer_uses_short_png_temporary_name_for_deep_output_paths(tmp_path: Path):
    from src.page_image_renderer import PageImageRenderer

    output_path = tmp_path / "rendered" / "version-1" / (
        "a" * 64 + ".thumbnail.png"
    )

    temporary_path = PageImageRenderer._temporary_path(output_path)

    assert temporary_path.parent == output_path.parent
    assert temporary_path.suffix == ".png"
    assert output_path.stem not in temporary_path.name
    assert ".thumbnail" not in temporary_path.name
