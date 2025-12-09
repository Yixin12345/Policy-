from __future__ import annotations

import base64
import logging
from mimetypes import guess_type
from pathlib import Path
from typing import List, Optional

import fitz  # type: ignore

try:  # pragma: no cover - optional dependency guard
  import cv2  # type: ignore
except ImportError:  # pragma: no cover - optional dependency guard
  cv2 = None  # type: ignore

try:  # pragma: no cover - optional dependency guard
  from ...utils.auto_rotate_lines import choose_best_rotation
except ImportError:  # pragma: no cover - optional dependency guard
  choose_best_rotation = None  # type: ignore

from ...models.job import PageExtraction

logger = logging.getLogger(__name__)


def _auto_orient_image(image_path: Path) -> Optional[int]:
  """Rotate the given image in-place if analysis suggests it is sideways."""
  if cv2 is None or choose_best_rotation is None:
    return None

  img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
  if img is None:
    logger.warning("Unable to read image %s for auto-rotation", image_path)
    return None

  try:
    angle, rotated, _, _ = choose_best_rotation(img)
  except Exception as exc:  # pragma: no cover - defensive
    logger.exception("Auto-rotation failed for %s: %s", image_path, exc)
    return None

  if angle and angle % 360 != 0:
    if not cv2.imwrite(str(image_path), rotated):
      logger.warning("Failed to write rotated image for %s", image_path)
      return None
    return angle

  return 0


def pdf_to_images(pdf_path: Path, output_dir: Path, zoom: float = 3) -> List[PageExtraction]:
  pages: List[PageExtraction] = []
  output_dir.mkdir(parents=True, exist_ok=True)

  with fitz.open(pdf_path) as doc:
    for index in range(doc.page_count):
      page = doc.load_page(index)
      matrix = fitz.Matrix(zoom, zoom)
      pix = page.get_pixmap(matrix=matrix, alpha=False)
      image_path = output_dir / f"page-{index + 1}.png"
      pix.save(image_path)

      rotation = _auto_orient_image(image_path) or 0

      pages.append(
        PageExtraction(
          page_number=index + 1,
          status="pending",
          image_path=image_path,
          image_mime="image/png",
          rotation_applied=rotation,
        )
      )

  return pages


def image_to_data_url(image_path: Path) -> str:
  mime, _ = guess_type(image_path)
  mime = mime or "image/png"
  data = image_path.read_bytes()
  encoded = base64.b64encode(data).decode("utf-8")
  return f"data:{mime};base64,{encoded}"
