from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.pdf.pdf_renderer import PdfRenderer, RenderedPage


@pytest.fixture
def mock_pdf(tmp_path):
    document = MagicMock()
    document.page_count = 2
    page = MagicMock()
    pixmap = MagicMock()

    def load_page(index):
        page.page_number = index + 1
        return page

    page.get_pixmap.return_value = pixmap
    document.load_page.side_effect = load_page

    pixmap.save.side_effect = lambda path: Path(path).write_bytes(b"fake-image")

    context_manager = MagicMock()
    context_manager.__enter__.return_value = document
    context_manager.__exit__.return_value = None

    with (
        patch("backend.infrastructure.pdf.pdf_renderer.fitz.open", return_value=context_manager),
        patch("backend.infrastructure.pdf.pdf_renderer.auto_orient_image", return_value=0),
    ):
        yield document


def test_render_creates_images(tmp_path, mock_pdf):
    renderer = PdfRenderer(zoom=2.0)
    output_dir = tmp_path / "output"
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    pages = renderer.render(pdf_path, output_dir)

    assert len(pages) == 2
    assert all(isinstance(page, RenderedPage) for page in pages)
    for index, page in enumerate(pages, start=1):
        assert page.page_number == index
        assert page.image_path.exists()
        assert page.image_path.read_bytes() == b"fake-image"
        assert page.rotation_applied == 0


def test_get_page_count(tmp_path, mock_pdf):
    renderer = PdfRenderer()
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    count = renderer.get_page_count(pdf_path)
    assert count == 2


def test_render_raises_for_missing_file():
    renderer = PdfRenderer()
    with pytest.raises(FileNotFoundError):
        renderer.render("/nonexistent.pdf")
