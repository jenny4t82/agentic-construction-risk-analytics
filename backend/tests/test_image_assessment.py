import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

# Keep unit tests stateless even when the developer's root .env is present.
os.environ["DATABASE_URL"] = ""

from app.detector import (
    BoundingBox,
    MockHazardDetector,
    YOLOv8HazardDetector,
    normalize_detection_label,
)
from app.main import app, get_hazard_detector
from app.auth import get_current_user


# Valid minimal image fixtures
TINY_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xd9"
TINY_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"


class DetectorUnitTests(unittest.TestCase):
    def test_violation_class_normalization(self) -> None:
        self.assertEqual(normalize_detection_label("NO-Hardhat"), "no_helmet")
        self.assertEqual(normalize_detection_label("no-hardhat"), "no_helmet")
        self.assertEqual(normalize_detection_label("NO-Safety Vest"), "no_vest")
        self.assertEqual(normalize_detection_label("no_safety_vest"), "no_vest")
        self.assertEqual(normalize_detection_label("NO-Mask"), "no_mask")
        self.assertEqual(normalize_detection_label("no-mask"), "no_mask")

    def test_compliant_and_equipment_classes_are_not_hazards(self) -> None:
        non_hazards = [
            "Person",
            "Hardhat",
            "Safety Vest",
            "Mask",
            "Gloves",
            "Safety Cone",
            "Ladder",
            "Excavator",
            "dump truck",
            "wheel loader",
            "machinery",
            "vehicle",
            "truck",
            "sedan",
        ]
        for name in non_hazards:
            self.assertIsNone(
                normalize_detection_label(name),
                f"{name} should not be normalized to a hazard",
            )

    def test_mock_detector_filters_and_counts_people(self) -> None:
        mock = MockHazardDetector(
            canned_boxes=[
                BoundingBox(class_name="Person", confidence=0.95),
                BoundingBox(class_name="Person", confidence=0.92),
                BoundingBox(class_name="Hardhat", confidence=0.88),
                BoundingBox(class_name="NO-Hardhat", confidence=0.89),
                BoundingBox(class_name="NO-Safety Vest", confidence=0.84),
                BoundingBox(class_name="Safety Cone", confidence=0.91),
                BoundingBox(class_name="Excavator", confidence=0.77),
            ]
        )

        res = mock.detect(TINY_JPEG)

        self.assertEqual(res.people_count, 2)
        self.assertEqual(set(res.hazard_labels), {"no_helmet", "no_vest"})
        self.assertEqual(res.max_confidence, 0.89)


class DetectorSelectionTests(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_default_repository_weights_are_selected_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            default_weights = Path(temp_dir) / "weights" / "best.pt"
            default_weights.parent.mkdir()
            default_weights.write_bytes(b"test weights")

            with patch.dict(os.environ, {}, clear=True), patch(
                "app.main.DEFAULT_WEIGHTS_PATH", default_weights
            ):
                detector = get_hazard_detector()

            self.assertIsInstance(detector, YOLOv8HazardDetector)
            self.assertEqual(detector.weights_path, str(default_weights))

    def test_relative_configured_weights_are_resolved_from_project_root(self) -> None:
        project_root = Path("C:/project-root")
        with patch.dict(
            os.environ,
            {"HAZARD_DETECTOR_WEIGHTS": "weights/custom.pt"},
            clear=True,
        ), patch("app.main.PROJECT_ROOT", project_root), patch(
            "app.main._get_yolo_detector"
        ) as detector_factory:
            get_hazard_detector()

        detector_factory.assert_called_once_with(
            str(project_root / "weights" / "custom.pt")
        )


class ImageAssessmentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: object()
        self.mock_detector = MockHazardDetector()
        app.dependency_overrides[get_hazard_detector] = lambda: self.mock_detector

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_image_assessment_with_violations_and_full_scoring(self) -> None:
        self.mock_detector.set_canned_boxes(
            [
                BoundingBox(class_name="Person", confidence=0.95),
                BoundingBox(class_name="Person", confidence=0.90),
                BoundingBox(class_name="NO-Hardhat", confidence=0.88),
                BoundingBox(class_name="NO-Safety Vest", confidence=0.82),
            ]
        )

        response = self.client.post(
            "/assessments/image?duration_minutes=45&repeated_count=3&work_area=zone-north",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result["detected_hazards"]), 2)
        self.assertEqual(result["pending_hazards"], [])

        self.assertEqual(len(result["assessments"]), 2)
        self.assertEqual(result["safety_decision"]["outcome"], "alert")
        self.assertEqual(result["safety_decision"]["risk_band"], "High")
        self.assertEqual(result["safety_decision"]["priority"], "high")
        self.assertEqual(len(result["safety_decision"]["supporting_evidence"]), 2)

        hazard_types = {a["hazard_type"] for a in result["assessments"]}
        self.assertEqual(
            hazard_types, {"missing_safety_helmet", "missing_safety_vest"}
        )

        # Helmet assessment: severity 5, likelihood 4 (repeated=3), exposure 2 (people=2, duration=45) => 40
        helmet_assessment = next(
            a
            for a in result["assessments"]
            if a["hazard_type"] == "missing_safety_helmet"
        )
        self.assertEqual(helmet_assessment["risk_score"], 40)
        self.assertEqual(helmet_assessment["risk_band"], "High")

        # Vest assessment: severity 4, likelihood 4, exposure 2 => 32
        vest_assessment = next(
            a
            for a in result["assessments"]
            if a["hazard_type"] == "missing_safety_vest"
        )
        self.assertEqual(vest_assessment["risk_score"], 32)
        self.assertEqual(vest_assessment["risk_band"], "Moderate")

    def test_single_violation_uses_its_detection_confidence(self) -> None:
        self.mock_detector.set_canned_boxes([
            BoundingBox(class_name="Person", confidence=0.99),
            BoundingBox(class_name="NO-Hardhat", confidence=0.61),
        ])
        response = self.client.post(
            "/assessments/image?duration_minutes=20&repeated_count=0",
            content=TINY_JPEG, headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["detected_hazards"][0]["detection_confidence"], 0.61)
        self.assertEqual(payload["assessments"][0]["detection_confidence"], 0.61)

    def test_matching_class_maximum_does_not_leak_across_hazards(self) -> None:
        self.mock_detector.set_canned_boxes([
            BoundingBox(class_name="NO-Hardhat", confidence=0.61),
            BoundingBox(class_name="NO-Hardhat", confidence=0.73),
            BoundingBox(class_name="NO-Safety Vest", confidence=0.77),
            BoundingBox(class_name="Person", confidence=0.99),
        ])
        response = self.client.post(
            "/assessments/image?people_count=1&duration_minutes=20&repeated_count=0",
            content=TINY_JPEG, headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        expected = {"missing_safety_helmet": 0.73, "missing_safety_vest": 0.77}
        for field in ("detected_hazards", "assessments"):
            self.assertEqual(
                {item["hazard_type"]: item["detection_confidence"] for item in payload[field]},
                expected,
            )
        self.assertEqual(
            {item["hazard_type"]: item["detection_confidence"]
             for item in payload["safety_decision"]["supporting_evidence"]},
            expected,
        )

    def test_compliant_only_image_yields_no_hazards(self) -> None:
        self.mock_detector.set_canned_boxes(
            [
                BoundingBox(class_name="Person", confidence=0.95),
                BoundingBox(class_name="Hardhat", confidence=0.91),
                BoundingBox(class_name="Safety Vest", confidence=0.89),
                BoundingBox(class_name="Safety Cone", confidence=0.87),
            ]
        )

        response = self.client.post(
            "/assessments/image?duration_minutes=30&repeated_count=1",
            content=TINY_PNG,
            headers={"Content-Type": "image/png"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["detected_hazards"], [])
        self.assertEqual(result["assessments"], [])
        self.assertEqual(result["pending_hazards"], [])
        self.assertEqual(result["safety_decision"]["outcome"], "no_alert")
        self.assertIn("does not confirm site safety", result["safety_decision"]["reason"])

    def test_pending_hazards_when_scoring_inputs_missing(self) -> None:
        self.mock_detector.set_canned_boxes(
            [
                BoundingBox(class_name="NO-Hardhat", confidence=0.90),
            ]
        )

        # duration_minutes and repeated_count are not provided
        response = self.client.post(
            "/assessments/image",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result["detected_hazards"]), 1)
        self.assertEqual(result["assessments"], [])
        self.assertEqual(len(result["pending_hazards"]), 1)
        self.assertEqual(result["safety_decision"]["outcome"], "pending")
        self.assertEqual(
            result["pending_hazards"][0]["hazard_type"], "missing_safety_helmet"
        )

    def test_explicit_people_count_override(self) -> None:
        # Detector sees 1 person, but form provides people_count=8
        self.mock_detector.set_canned_boxes(
            [
                BoundingBox(class_name="Person", confidence=0.90),
                BoundingBox(class_name="NO-Hardhat", confidence=0.85),
            ]
        )

        response = self.client.post(
            "/assessments/image?people_count=8&duration_minutes=15&repeated_count=1",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        # Exposure for people_count=8 (>=5) is 3; severity=5; likelihood=3 (repeated=1) => score=45
        self.assertEqual(result["assessments"][0]["exposure"], 3)
        self.assertEqual(result["assessments"][0]["risk_score"], 45)

    def test_multipart_form_data_upload(self) -> None:
        self.mock_detector.set_canned_boxes(
            [
                BoundingBox(class_name="NO-Mask", confidence=0.86),
                BoundingBox(class_name="Person", confidence=0.91),
            ]
        )

        response = self.client.post(
            "/assessments/image",
            files={"file": ("site_face.jpg", TINY_JPEG, "image/jpeg")},
            data={"duration_minutes": "30", "repeated_count": "1"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result["assessments"]), 1)
        # Mask severity=2, likelihood=3, exposure=1 (people=1, duration=30 => people>=2 or dur>=30 gives 2) => score 2*3*2 = 12 (Low)
        self.assertEqual(
            result["assessments"][0]["hazard_type"], "missing_protective_mask"
        )
        self.assertEqual(result["assessments"][0]["risk_band"], "Low")

    def test_empty_image_rejected(self) -> None:
        response = self.client.post(
            "/assessments/image",
            content=b"",
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())

    def test_corrupt_or_non_image_rejected(self) -> None:
        response = self.client.post(
            "/assessments/image",
            content=b"not an image at all",
            headers={"Content-Type": "text/plain"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("unsupported or corrupt", response.json()["detail"].lower())

    def test_invalid_parameter_rejected(self) -> None:
        response = self.client.post(
            "/assessments/image?duration_minutes=0",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 422)

    def test_unconfigured_detector_returns_503(self) -> None:
        app.dependency_overrides.pop(get_hazard_detector, None)
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.main.DEFAULT_WEIGHTS_PATH", Path("missing-best.pt")
        ):
            response = self.client.post(
                "/assessments/image",
                content=TINY_JPEG,
                headers={"Content-Type": "image/jpeg"},
            )
            self.assertEqual(response.status_code, 503)
            self.assertIn("not configured", response.json()["detail"].lower())

    def test_explicit_mock_mode_via_environment(self) -> None:
        app.dependency_overrides.pop(get_hazard_detector, None)
        with patch.dict(os.environ, {"HAZARD_DETECTOR_MODE": "mock"}):
            response = self.client.post(
                "/assessments/image",
                content=TINY_JPEG,
                headers={"Content-Type": "image/jpeg"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["detected_hazards"], [])

    def test_corrupted_image_decode_failure_returns_400(self) -> None:
        class FaultyDetector(MockHazardDetector):
            def detect(self, image_bytes: bytes):
                raise ValueError("Corrupted image stream: cannot read raster data")

        app.dependency_overrides[get_hazard_detector] = lambda: FaultyDetector()
        response = self.client.post(
            "/assessments/image",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("image decoding failed", response.json()["detail"].lower())

    def test_oversized_content_length_rejected_with_413(self) -> None:
        response = self.client.post(
            "/assessments/image",
            content=TINY_JPEG,
            headers={
                "Content-Type": "image/jpeg",
                "Content-Length": str(15 * 1024 * 1024),
            },
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("10mb", response.json()["detail"].lower())

    def test_oversized_body_stream_rejected_with_413(self) -> None:
        oversized_data = b"\xff\xd8\xff\xe0" + b"\x00" * (10 * 1024 * 1024 + 1024)
        response = self.client.post(
            "/assessments/image",
            content=oversized_data,
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("10mb", response.json()["detail"].lower())

    def test_multiple_files_in_multipart_rejected(self) -> None:
        boundary = "testboundary123"
        multipart_body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file1"; filename="img1.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("latin1") + TINY_JPEG + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file2"; filename="img2.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("latin1") + TINY_JPEG + f"\r\n--{boundary}--\r\n".encode("latin1")

        response = self.client.post(
            "/assessments/image",
            content=multipart_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("multiple image files", response.json()["detail"].lower())

    def test_whitespace_observation_id_normalization_with_violations(self) -> None:
        self.mock_detector.set_canned_boxes(
            [
                BoundingBox(class_name="NO-Hardhat", confidence=0.88),
            ]
        )
        response = self.client.post(
            "/assessments/image?observation_id=   ",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 200)
        obs_id = response.json()["observation_id"]
        self.assertTrue(obs_id.startswith("img-obs-"))
        self.assertEqual(len(response.json()["detected_hazards"]), 1)

    def test_whitespace_observation_id_normalization_without_violations(self) -> None:
        self.mock_detector.set_canned_boxes([])
        response = self.client.post(
            "/assessments/image?observation_id=   ",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )
        self.assertEqual(response.status_code, 200)
        obs_id = response.json()["observation_id"]
        self.assertTrue(obs_id.startswith("img-obs-"))
        self.assertEqual(response.json()["detected_hazards"], [])

    def test_missing_weights_path_returns_controlled_503(self) -> None:
        app.dependency_overrides.pop(get_hazard_detector, None)
        with patch.dict(
            os.environ,
            {"HAZARD_DETECTOR_WEIGHTS": "nonexistent_model_weights.pt"},
            clear=True,
        ):
            response = self.client.post(
                "/assessments/image",
                content=TINY_JPEG,
                headers={"Content-Type": "image/jpeg"},
            )
            self.assertEqual(response.status_code, 503)
            self.assertIn("service unavailable", response.json()["detail"].lower())


class AnnotatedImageTests(unittest.TestCase):
    """Tests for the annotated_image field returned with YOLO bounding boxes."""

    @classmethod
    def _make_real_png(cls, width: int = 100, height: int = 100) -> bytes:
        """Create a real in-memory PNG that Pillow can decode."""
        from PIL import Image as PILImage
        import io as _io
        img = PILImage.new("RGB", (width, height), color=(128, 128, 128))
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def setUp(self) -> None:
        self.client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: object()
        self.mock_detector = MockHazardDetector()
        app.dependency_overrides[get_hazard_detector] = lambda: self.mock_detector

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_annotated_image_present_with_hazard_detections(self) -> None:
        """When hazards are detected, response includes a valid base64 PNG."""
        import base64
        self.mock_detector.set_canned_boxes([
            BoundingBox(class_name="NO-Hardhat", confidence=0.88,
                        x_min=10, y_min=10, x_max=50, y_max=50),
            BoundingBox(class_name="Person", confidence=0.95,
                        x_min=5, y_min=5, x_max=90, y_max=90),
        ])

        real_png = self._make_real_png()
        response = self.client.post(
            "/assessments/image?duration_minutes=30&repeated_count=1",
            content=real_png,
            headers={"Content-Type": "image/png"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()

        # annotated_image must be present and non-null
        self.assertIn("annotated_image", result)
        self.assertIsNotNone(result["annotated_image"])

        # Must decode to valid PNG bytes
        decoded = base64.b64decode(result["annotated_image"])
        self.assertTrue(decoded.startswith(b"\x89PNG\r\n\x1a\n"),
                        "annotated_image is not a valid PNG")

    def test_annotated_image_present_when_no_hazards(self) -> None:
        """Compliant-only images still get an annotated_image (no boxes drawn)."""
        import base64
        self.mock_detector.set_canned_boxes([
            BoundingBox(class_name="Person", confidence=0.95,
                        x_min=5, y_min=5, x_max=90, y_max=90),
            BoundingBox(class_name="Hardhat", confidence=0.91,
                        x_min=10, y_min=10, x_max=50, y_max=50),
        ])

        real_png = self._make_real_png()
        response = self.client.post(
            "/assessments/image",
            content=real_png,
            headers={"Content-Type": "image/png"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn("annotated_image", result)
        self.assertIsNotNone(result["annotated_image"])

        decoded = base64.b64decode(result["annotated_image"])
        self.assertTrue(decoded.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_annotated_image_null_when_image_not_decodable(self) -> None:
        """Stub JPEG bytes that PIL cannot decode → annotated_image is None."""
        self.mock_detector.set_canned_boxes([
            BoundingBox(class_name="NO-Hardhat", confidence=0.88),
        ])

        # TINY_JPEG is valid enough for the magic-byte check but not PIL-decodable
        response = self.client.post(
            "/assessments/image",
            content=TINY_JPEG,
            headers={"Content-Type": "image/jpeg"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        # annotated_image should be null (graceful degradation)
        self.assertIsNone(result["annotated_image"])

    def test_annotated_image_with_multipart_upload(self) -> None:
        """Multipart form upload also returns an annotated image."""
        import base64
        self.mock_detector.set_canned_boxes([
            BoundingBox(class_name="NO-Safety Vest", confidence=0.82,
                        x_min=20, y_min=20, x_max=80, y_max=80),
        ])

        real_png = self._make_real_png(200, 200)
        response = self.client.post(
            "/assessments/image",
            files={"file": ("site.png", real_png, "image/png")},
            data={"duration_minutes": "15", "repeated_count": "2"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIsNotNone(result["annotated_image"])
        decoded = base64.b64decode(result["annotated_image"])
        self.assertTrue(decoded.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_risk_scoring_unchanged_with_annotated_image(self) -> None:
        """Risk scores must not change because of the annotated-image feature."""
        self.mock_detector.set_canned_boxes([
            BoundingBox(class_name="Person", confidence=0.95,
                        x_min=5, y_min=5, x_max=90, y_max=90),
            BoundingBox(class_name="Person", confidence=0.90,
                        x_min=10, y_min=10, x_max=85, y_max=85),
            BoundingBox(class_name="NO-Hardhat", confidence=0.88,
                        x_min=15, y_min=15, x_max=55, y_max=55),
            BoundingBox(class_name="NO-Safety Vest", confidence=0.82,
                        x_min=20, y_min=20, x_max=60, y_max=60),
        ])

        real_png = self._make_real_png()
        response = self.client.post(
            "/assessments/image?duration_minutes=45&repeated_count=3&work_area=zone-north",
            content=real_png,
            headers={"Content-Type": "image/png"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()

        # Same risk scores as the original test_image_assessment_with_violations_and_full_scoring
        self.assertEqual(len(result["assessments"]), 2)
        hazard_types = {a["hazard_type"] for a in result["assessments"]}
        self.assertEqual(hazard_types, {"missing_safety_helmet", "missing_safety_vest"})

        helmet = next(a for a in result["assessments"]
                      if a["hazard_type"] == "missing_safety_helmet")
        self.assertEqual(helmet["risk_score"], 40)
        self.assertEqual(helmet["risk_band"], "High")

        vest = next(a for a in result["assessments"]
                    if a["hazard_type"] == "missing_safety_vest")
        self.assertEqual(vest["risk_score"], 32)
        self.assertEqual(vest["risk_band"], "Moderate")


if __name__ == "__main__":
    unittest.main()
