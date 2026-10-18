import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.detector import (
    BoundingBox,
    MockHazardDetector,
    normalize_detection_label,
)
from app.main import app, get_hazard_detector


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


class ImageAssessmentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
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
        app.dependency_overrides.clear()
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post(
                "/assessments/image",
                content=TINY_JPEG,
                headers={"Content-Type": "image/jpeg"},
            )
            self.assertEqual(response.status_code, 503)
            self.assertIn("not configured", response.json()["detail"].lower())

    def test_explicit_mock_mode_via_environment(self) -> None:
        app.dependency_overrides.clear()
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
        app.dependency_overrides.clear()
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


if __name__ == "__main__":
    unittest.main()
