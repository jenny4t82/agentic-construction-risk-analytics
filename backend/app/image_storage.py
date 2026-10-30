"""Safe, file-backed storage for images associated with observations.

Only a deterministic storage key is persisted in the observation metadata. The
client never supplies a filesystem path, and retrieval validates the resolved
path stays inside the configured observation-image directory.
"""

import base64
import binascii
import hashlib
from pathlib import Path
from typing import Any, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OBSERVATION_IMAGE_ROOT = PROJECT_ROOT / "data" / "observations"
_VARIANTS = {
    "original": ("original", "image/jpeg"),
    "annotated": ("annotated", "image/png"),
}
_FORMAT_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _storage_key(observation_id: str) -> str:
    return hashlib.sha256(observation_id.encode("utf-8")).hexdigest()


def save_observation_images(
    observation_id: str,
    original_bytes: bytes,
    original_media_type: str,
    annotated_image_base64: Optional[str],
) -> dict[str, Any]:
    """Save image files and return JSON-safe metadata for the observation row."""

    extension = _FORMAT_EXTENSIONS[original_media_type]
    storage_key = _storage_key(observation_id)
    directory = OBSERVATION_IMAGE_ROOT / storage_key
    directory.mkdir(parents=True, exist_ok=True)
    original_path = directory / f"original{extension}"
    original_path.write_bytes(original_bytes)

    annotated_path: Optional[Path] = None
    if annotated_image_base64:
        try:
            annotated_bytes = base64.b64decode(annotated_image_base64, validate=True)
        except (ValueError, binascii.Error) as err:
            raise ValueError("annotated image data is invalid") from err
        annotated_path = directory / "annotated.png"
        annotated_path.write_bytes(annotated_bytes)

    from PIL import Image

    try:
        with Image.open(original_path) as image:
            width, height = image.size
    except Exception:
        # The upload endpoint already validates the image signature. Keep the
        # original bytes available even when Pillow cannot decode them.
        width, height = None, None

    return {
        "storage_key": storage_key,
        "original_filename": original_path.name,
        "annotated_filename": annotated_path.name if annotated_path else None,
        "original_media_type": original_media_type,
        "width": width,
        "height": height,
    }


def get_observation_image_path(
    observation_id: str,
    variant: str,
    image_metadata: Any,
) -> tuple[Path, str]:
    """Resolve a stored image without accepting arbitrary filesystem paths."""

    if variant not in _VARIANTS:
        raise ValueError("unsupported image variant")
    if not isinstance(image_metadata, dict):
        raise FileNotFoundError("image metadata is unavailable")

    storage_key = image_metadata.get("storage_key")
    expected_key = _storage_key(observation_id)
    if storage_key != expected_key:
        raise ValueError("image metadata does not match the observation")

    filename_key, default_media_type = _VARIANTS[variant]
    filename = image_metadata.get(f"{filename_key}_filename")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise FileNotFoundError("image variant is unavailable")

    candidate = (OBSERVATION_IMAGE_ROOT / storage_key / filename).resolve()
    root = OBSERVATION_IMAGE_ROOT.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as err:
        raise ValueError("image path is outside the observation storage directory") from err
    if not candidate.is_file():
        raise FileNotFoundError("image file is unavailable")

    media_type = (
        image_metadata.get("original_media_type")
        if variant == "original"
        else default_media_type
    )
    return candidate, str(media_type)
