"""PDF rendering utilities for the infrastructure layer."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import fitz  # type: ignore

from .image_processor import auto_orient_image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderedPage:
    """Represents an image generated from a PDF page."""

    page_number: int
    image_path: Path
    image_mime: str = "image/png"
    rotation_applied: int = 0

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("page_number must be >= 1")
        if not isinstance(self.image_path, Path):
            object.__setattr__(self, "image_path", Path(self.image_path))


class PdfRenderer:
    """Renders PDF documents to image files for downstream processing."""

    def __init__(self, *, zoom: float = 3.0) -> None:
        self._zoom = zoom

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_page_count(self, pdf_path: Path | str) -> int:
        """Return the number of pages in the PDF."""

        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(pdf_path)

        with fitz.open(path) as document:
            return document.page_count

    def render(self, pdf_path: Path | str, output_dir: Optional[Path | str] = None) -> List[RenderedPage]:
        """Render the PDF to images and return metadata for each page."""

        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(pdf_path)

        if output_dir is None:
            output_dir = path.parent / f"{path.stem}-pages"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        rendered_pages: List[RenderedPage] = []

        with fitz.open(path) as document:
            for index in range(document.page_count):
                page = document.load_page(index)
                matrix = fitz.Matrix(self._zoom, self._zoom)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)

                image_path = output_dir / f"page-{index + 1}.png"
                pixmap.save(image_path)

                rotation = auto_orient_image(image_path) or 0
                rendered_pages.append(
                    RenderedPage(
                        page_number=index + 1,
                        image_path=image_path,
                        image_mime="image/png",
                        rotation_applied=int(rotation),
                    )
                )

        logger.debug("Rendered %s pages for %s", len(rendered_pages), pdf_path)
        return rendered_pages

    def render_to_inputs(self, pdf_path: Path | str, output_dir: Optional[Path | str] = None) -> List[dict]:
        """Convenience helper returning dictionaries suitable for the vision client."""

        pages = self.render(pdf_path, output_dir)
        return [
            {
                "page_number": page.page_number,
                "image_path": str(page.image_path),
                "image_mime": page.image_mime,
                "rotation_applied": page.rotation_applied,
            }
            for page in pages
        ]

    @staticmethod
    def ensure_pages(pages: Iterable[RenderedPage]) -> List[RenderedPage]:
        """Utility to coerce any iterable of pages to a list."""

        if isinstance(pages, list):
            return pages
        return list(pages)
