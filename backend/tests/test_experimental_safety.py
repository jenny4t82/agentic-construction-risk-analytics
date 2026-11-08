"""Tests for the experimental safety visualization backend endpoint.

Verifies:
- Valid image processing (JPEG/PNG) and exact response schema
- Invalid image formats and empty files (HTTP 400)
- Request size limit enforcement (HTTP 413)
- Service and inference failure handling (HTTP 503)
- Absence of database writes or history modifications
- Separation of raw model detections from fully scored risk assessments
"""

import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))

os.environ["DATABASE_URL"] = ""

from app.db_models import (
    Alert,
    DetectedHazardRecord,
    Observation,
    RiskAssessment,
    SafetyRecommendation,
)
from app.main import app
from app.auth import get_current_user
from app.safety_agent import (
    DEFAULT_MODEL_PATH,
    Detection,
    DetectionResult,
    load_model,
)

TINY_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xd9"
)
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_test_image_bytes(width: int = 100, height: int = 80, format: str = "JPEG") -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (width, height), color=(200, 100, 50))
    image.save(buffer, format=format)
    return buffer.getvalue()


class ExperimentalSafetyEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: object()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_valid_image_response_structure_with_mocked_inference(self) -> None:
        test_img = _make_test_image_bytes(320, 240, "JPEG")
        fake_result = DetectionResult(
            image_path=Path("mock.jpg"),
            image_width=320,
            image_height=240,
            detections=(
                Detection(
                    class_name="NO-Hardhat",
                    confidence=0.88,
                    bounding_box=(20.0, 30.0, 80.0, 90.0),
                    class_id=5,
                ),
                Detection(
                    class_name="Person",
                    confidence=0.92,
                    bounding_box=(15.0, 25.0, 150.0, 220.0),
                    class_id=8,
                ),
            ),
        )

        with patch("app.main.detect_objects", return_value=fake_result), patch(
            "app.main.load_model", return_value=MagicMock()
        ):
            response = self.client.post(
                "/experimental/safety/detect",
                content=test_img,
                headers={"Content-Type": "image/jpeg"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Dimension checks
        self.assertEqual(data["image_width"], 320)
        self.assertEqual(data["image_height"], 240)

        # Raw detections check
        self.assertEqual(len(data["detections"]), 2)
        det_no_hardhat = next(d for d in data["detections"] if d["class_name"] == "NO-Hardhat")
        self.assertEqual(det_no_hardhat["confidence"], 0.88)
        self.assertEqual(det_no_hardhat["box"], [20.0, 30.0, 80.0, 90.0])
        self.assertTrue(det_no_hardhat["is_hazard"])

        det_person = next(d for d in data["detections"] if d["class_name"] == "Person")
        self.assertEqual(det_person["confidence"], 0.92)
        self.assertFalse(det_person["is_hazard"])

        # Safety findings check
        self.assertEqual(len(data["detected_hazards"]), 1)
        self.assertEqual(data["detected_hazards"][0]["hazard_type"], "missing_safety_helmet")
        self.assertEqual(data["detected_hazards"][0]["source_label"], "no_helmet")

        # Distinguish unscored detections from fully scored assessments
        self.assertFalse(data["is_risk_assessed"])
        self.assertEqual(data["assessments"], [])
        self.assertIn("pending/unscored", data["status_note"])

        # Recommendations check
        self.assertEqual(len(data["recommendations"]), 1)
        self.assertEqual(data["recommendations"][0]["hazard_type"], "missing_safety_helmet")
        self.assertEqual(data["recommendations"][0]["priority"], "pending")

        # Alert decision check
        self.assertFalse(data["alert"]["alert_recommended"])
        self.assertEqual(data["safety_decision"]["outcome"], "pending")
        self.assertIn("complete, consistent risk assessment is unavailable", data["alert"]["reason"])
        self.assertEqual(data["alert"]["priority"], "pending")
        self.assertEqual(data["routing_decision"], "assessment_pending")
        self.assertEqual(data["routing_status"], "pending")

    def test_alias_endpoint_detect_safety(self) -> None:
        test_img = _make_test_image_bytes(100, 100, "PNG")
        fake_result = DetectionResult(
            image_path=Path("mock.png"),
            image_width=100,
            image_height=100,
            detections=(),
        )

        with patch("app.main.detect_objects", return_value=fake_result), patch(
            "app.main.load_model", return_value=MagicMock()
        ):
            response = self.client.post(
                "/experimental/detect-safety",
                content=test_img,
                headers={"Content-Type": "image/png"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["detections"], [])
        self.assertFalse(data["alert"]["alert_recommended"])
        self.assertEqual(data["safety_decision"]["outcome"], "no_alert")
        self.assertEqual(data["routing_decision"], "no_supported_ppe_violations")
        self.assertEqual(data["routing_status"], "no_findings")

    def test_multipart_form_upload(self) -> None:
        test_img = _make_test_image_bytes(200, 150, "JPEG")
        fake_result = DetectionResult(
            image_path=Path("site_test.jpg"),
            image_width=200,
            image_height=150,
            detections=(),
        )

        with patch("app.main.detect_objects", return_value=fake_result), patch(
            "app.main.load_model", return_value=MagicMock()
        ):
            response = self.client.post(
                "/experimental/safety/detect",
                files={"file": ("site_test.jpg", test_img, "image/jpeg")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["image_width"], 200)

    def test_optional_operational_inputs_produce_scored_assessments(self) -> None:
        test_img = _make_test_image_bytes(200, 150, "JPEG")
        fake_result = DetectionResult(
            image_path=Path("site_test.jpg"),
            image_width=200,
            image_height=150,
            detections=(
                Detection(
                    class_name="NO-Hardhat",
                    confidence=0.9,
                    bounding_box=(10.0, 10.0, 50.0, 50.0),
                    class_id=5,
                ),
            ),
        )

        with patch("app.main.detect_objects", return_value=fake_result), patch(
            "app.main.load_model", return_value=MagicMock()
        ):
            response = self.client.post(
                "/experimental/safety/detect?people_count=3&duration_minutes=45&repeated_count=2&work_area=Scaffold+B",
                content=test_img,
                headers={"Content-Type": "image/jpeg"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_risk_assessed"])
        self.assertEqual(len(data["assessments"]), 1)
        self.assertGreater(data["assessments"][0]["risk_score"], 0)
        self.assertEqual(data["safety_decision"]["outcome"], "warning")
        self.assertEqual(data["safety_decision"]["risk_band"], "Moderate")
        self.assertEqual(data["safety_decision"]["priority"], "medium")
        self.assertIn("completed", data["status_note"])

    def test_invalid_image_format_rejected(self) -> None:
        response = self.client.post(
            "/experimental/safety/detect",
            content=b"this is plain text and definitely not an image",
            headers={"Content-Type": "text/plain"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Supported formats", response.json()["detail"])

    def test_empty_image_rejected(self) -> None:
        response = self.client.post(
            "/experimental/safety/detect",
            content=b"",
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("must not be empty", response.json()["detail"])

    def test_oversized_image_rejected(self) -> None:
        oversized = b"X" * (10 * 1024 * 1024 + 1024)
        response = self.client.post(
            "/experimental/safety/detect",
            content=oversized,
            headers={
                "Content-Type": "image/jpeg",
                "Content-Length": str(len(oversized)),
            },
        )
        self.assertEqual(response.status_code, 413)

    def test_model_unavailable_returns_503(self) -> None:
        test_img = _make_test_image_bytes(50, 50, "JPEG")
        with patch("app.main.load_model", side_effect=FileNotFoundError("Weights missing")):
            response = self.client.post(
                "/experimental/safety/detect",
                content=test_img,
                headers={"Content-Type": "image/jpeg"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("service unavailable", response.json()["detail"])

    def test_inference_failure_returns_503(self) -> None:
        test_img = _make_test_image_bytes(50, 50, "JPEG")
        with patch("app.main.load_model", return_value=MagicMock()), patch(
            "app.main.detect_objects", side_effect=RuntimeError("GPU computation failed")
        ):
            response = self.client.post(
                "/experimental/safety/detect",
                content=test_img,
                headers={"Content-Type": "image/jpeg"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("inference failed", response.json()["detail"])

    def test_absence_of_database_writes(self) -> None:
        """Verify that the experimental endpoint never writes to PostgreSQL or calls persistence adapters."""
        mock_db = MagicMock()
        mock_db.get.return_value = None
        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            test_img = _make_test_image_bytes(100, 100, "JPEG")
            fake_result = DetectionResult(
                image_path=Path("mock.jpg"),
                image_width=100,
                image_height=100,
                detections=(
                    Detection(
                        class_name="NO-Hardhat",
                        confidence=0.85,
                        bounding_box=(10.0, 10.0, 50.0, 50.0),
                        class_id=5,
                    ),
                ),
            )

            with patch("app.main.detect_objects", return_value=fake_result), patch(
                "app.main.load_model", return_value=MagicMock()
            ), patch("app.main.persist_observation_bundle") as mock_persist, patch(
                "app.main.save_observation_images"
            ) as mock_save_images:
                response = self.client.post(
                    "/experimental/safety/detect",
                    content=test_img,
                    headers={"Content-Type": "image/jpeg"},
                )

            self.assertEqual(response.status_code, 200)

            # Confirm 0 persistence calls were made
            mock_db.add.assert_not_called()
            mock_db.commit.assert_not_called()
            mock_db.flush.assert_not_called()
            mock_persist.assert_not_called()
            mock_save_images.assert_not_called()
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_with_real_yolo_weights_if_present(self) -> None:
        """Execute against the actual trained weights if present in repository."""
        if not DEFAULT_MODEL_PATH.is_file():
            self.skipTest("weights/best.pt not present")

        test_img = _make_test_image_bytes(256, 256, "JPEG")
        response = self.client.post(
            "/experimental/safety/detect",
            content=test_img,
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["image_width"], 256)
        self.assertEqual(data["image_height"], 256)
        self.assertIn("detections", data)
        self.assertIn("alert", data)


if __name__ == "__main__":
    unittest.main()
