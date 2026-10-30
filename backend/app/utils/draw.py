"""Draw YOLO bounding boxes onto an image and return base64-encoded PNG."""

import base64
import io
import logging
from typing import Optional, Sequence

from PIL import Image, ImageDraw, ImageFont

from ..detector import BoundingBox

logger = logging.getLogger(__name__)

# Hazard classes get a red-ish palette; non-hazard classes get a cooler palette.
_HAZARD_COLOR = (220, 38, 38)       # red-600
_NON_HAZARD_COLOR = (59, 130, 246)  # blue-500


def _color_for_class(class_name: str) -> tuple[int, int, int]:
    """Return a fixed colour depending on whether the class is a hazard."""
    lowered = class_name.strip().lower()
    if lowered.startswith("no-") or lowered.startswith("no_"):
        return _HAZARD_COLOR
    return _NON_HAZARD_COLOR


def draw_bounding_boxes(
    image_bytes: bytes, boxes: Sequence[BoundingBox]
) -> Optional[str]:
    """Return a base64-encoded PNG with YOLO boxes drawn.

    Parameters
    ----------
    image_bytes:
        Original uploaded image data (JPEG / PNG / WebP).
    boxes:
        Sequence of :class:`BoundingBox` from the detector.

    Returns
    -------
    Optional[str]
        Base64-encoded PNG string (no ``data:`` prefix), or ``None``
        if the image could not be decoded by Pillow.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()  # force full decode
        img = img.convert("RGB")
    except Exception:
        logger.warning("Could not decode image for annotation; skipping overlay.")
        return None

    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for box in boxes:
        x0, y0 = int(box.x_min), int(box.y_min)
        x1, y1 = int(box.x_max), int(box.y_max)
        color = _color_for_class(box.class_name)

        # Draw bounding rectangle
        draw.rectangle([x0, y0, x1, y1], outline=color, width=3)

        # Label text
        label = f"{box.class_name} {box.confidence:.0%}"

        # Compute text size – use textbbox (Pillow >= 10) with fallback
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = len(label) * 7, 12

        # Background rectangle behind label (above the box edge)
        bg_y0 = max(y0 - th - 4, 0)
        draw.rectangle([x0, bg_y0, x0 + tw + 6, y0], fill=color)
        draw.text((x0 + 3, bg_y0 + 1), label, fill="white", font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
