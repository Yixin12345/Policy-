"""Image processing helpers used by the infrastructure layer."""
from __future__ import annotations

import base64
import logging
from mimetypes import guess_type
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency guard
    import cv2  # type: ignore
except ImportError:  # pragma: no cover - optional dependency guard
    cv2 = None  # type: ignore

try:  # pragma: no cover - optional dependency guard
    from backend.utils.auto_rotate_lines import choose_best_rotation
except ImportError:  # pragma: no cover - optional dependency guard
    choose_best_rotation = None  # type: ignore


def auto_orient_image(image_path: Path) -> Optional[int]:
    """Rotate the given image if automatic rotation is available.

    Returns the rotation angle that was applied. If auto-rotation could not be
    performed the function returns ``None``.
    """

    if cv2 is None or choose_best_rotation is None:
        return None

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        logger.warning("Unable to read image %s for auto-rotation", image_path)
        return None

    try:
        angle, rotated, _, _ = choose_best_rotation(image)
    except Exception as exc:  # pragma: no cover - best-effort helper
        logger.exception("Auto-rotation failed for %s: %s", image_path, exc)
        return None

    if angle and angle % 360 != 0:
        if not cv2.imwrite(str(image_path), rotated):
            logger.warning("Failed to write rotated image for %s", image_path)
            return None
        return int(angle)

    return 0


def image_to_data_url(image_path: Path) -> str:
    """Convert an image on disk to a data URL suitable for OpenAI Vision."""

    mime_type, _ = guess_type(image_path)
    mime_type = mime_type or "image/png"
    data = image_path.read_bytes()
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"
