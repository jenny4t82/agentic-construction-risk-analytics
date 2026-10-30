"""Tests for retained observation images and safe image retrieval."""

import base64
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ["DATABASE_URL"] = ""

from app.detector import BoundingBox
from app.image_storage import get_observation_image_path, save_observation_images
from app.main import _build_image_metadata, app
from app.database import get_db
from app.db_models import Observation


def png_bytes(width: int = 120, height: int = 80) -> bytes:
    image = Image.new("RGB", (width, height), color=(120, 120, 120))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class ImagePersistenceTests(unittest.TestCase):
    def test_saved_images_retain_dimensions_and_detection_coordinates(self) -> None:
        boxes = [
            BoundingBox(
                class_name="NO-Hardhat",
                confidence=0.88,
                x_min=10,
                y_min=12,
                x_max=60,
                y_max=70,
            )
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.image_storage.OBSERVATION_IMAGE_ROOT", Path(directory)):
                metadata = _build_image_metadata(
                    observation_id="image-test-1",
                    image_bytes=png_bytes(),
                    image_media_type="image/png",
                    annotated_image=None,
                    boxes=boxes,
                )

                image_metadata = metadata["image"]
                self.assertEqual(image_metadata["width"], 120)
                self.assertEqual(image_metadata["height"], 80)
                self.assertEqual(image_metadata["detections"][0]["x_max"], 60)
                path, media_type = get_observation_image_path(
                    "image-test-1", "original", image_metadata
                )
                self.assertTrue(path.is_file())
                self.assertEqual(media_type, "image/png")

    def test_image_endpoint_retrieves_saved_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.image_storage.OBSERVATION_IMAGE_ROOT", Path(directory)):
                image_metadata = save_observation_images(
                    observation_id="image-test-2",
                    original_bytes=png_bytes(),
                    original_media_type="image/png",
                    annotated_image_base64=base64.b64encode(png_bytes(40, 40)).decode(),
                )
                observation = Observation(
                    observation_id="image-test-2",
                    observed_at=datetime.now(timezone.utc),
                    source="test",
                    raw_metadata={"image": image_metadata},
                )
                session = MagicMock()
                session.execute.return_value.scalar_one_or_none.return_value = observation
                app.dependency_overrides[get_db] = lambda: session
                try:
                    response = TestClient(app).get(
                        "/observations/image-test-2/image/annotated"
                    )
                finally:
                    app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG"))

    def test_unavailable_and_invalid_image_references_return_404(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = Observation(
            observation_id="image-test-3",
            observed_at=datetime.now(timezone.utc),
            source="test",
            raw_metadata={"image": {"storage_key": "wrong"}},
        )
        app.dependency_overrides[get_db] = lambda: session
        try:
            client = TestClient(app)
            unavailable = client.get("/observations/image-test-3/image/original")
            invalid_variant = client.get("/observations/image-test-3/image/other")
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(unavailable.status_code, 404)
        self.assertIn("Image unavailable", unavailable.json()["detail"])
        self.assertEqual(invalid_variant.status_code, 404)


if __name__ == "__main__":
    unittest.main()
