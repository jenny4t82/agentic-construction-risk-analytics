"""Focused tests for the ordinary Safety Agent functions.

The fake model and temporary image in these tests verify parsing and safety
logic only. They are not evidence of inference on a real construction image.
"""

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from PIL import Image

from app.models import NormalizedObservation
from app.safety_agent import (
    DEFAULT_MODEL_PATH,
    Detection,
    DetectionResult,
    assess_safety,
    decide_alert,
    detect_objects,
    load_model,
)


class FakeScalar:
    def __init__(self, value: float) -> None:
        self.value = value

    def item(self) -> float:
        return self.value


class FakeCoordinates:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


class FakeBoxCollection:
    def __init__(self) -> None:
        self.cls = [FakeScalar(5), FakeScalar(7)]
        self.conf = [FakeScalar(0.91), FakeScalar(0.83)]
        self.xyxy = [
            FakeCoordinates([10.0, 20.0, 100.0, 200.0]),
            FakeCoordinates([30.0, 40.0, 120.0, 220.0]),
        ]

    def __len__(self) -> int:
        return len(self.cls)


class FakeResult:
    names = {5: "NO-Hardhat", 7: "NO-Safety Vest"}

    def __init__(self) -> None:
        self.boxes = FakeBoxCollection()


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def predict(self, *, source: str, verbose: bool) -> list[FakeResult]:
        self.calls.append((source, verbose))
        return [FakeResult()]


def make_detection_result(*class_names: str) -> DetectionResult:
    detections = tuple(
        Detection(
            class_name=name,
            confidence=0.9,
            bounding_box=(10.0, 20.0, 100.0, 200.0),
        )
        for name in class_names
    )
    return DetectionResult(
        image_path=Path("unit-test-image.png"),
        image_width=640,
        image_height=480,
        detections=detections,
    )


class SafetyAgentTests(unittest.TestCase):
    def test_checkpoint_path_uses_pathlib_and_project_root(self) -> None:
        self.assertIsInstance(DEFAULT_MODEL_PATH, Path)
        self.assertEqual(DEFAULT_MODEL_PATH.name, "best.pt")
        self.assertEqual(DEFAULT_MODEL_PATH.parent.name, "weights")
        self.assertEqual(DEFAULT_MODEL_PATH.parents[1].name, "agentic-construction-risk-analytics")

    def test_relative_checkpoint_path_is_resolved_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            checkpoint = project_root / "weights" / "custom.pt"
            checkpoint.parent.mkdir()
            checkpoint.write_bytes(b"checkpoint")

            with patch("app.safety_agent.PROJECT_ROOT", project_root), patch(
                "app.safety_agent._load_cached_model", return_value=object()
            ) as cached_loader:
                load_model("weights/custom.pt")

            cached_loader.assert_called_once_with(str(checkpoint.resolve()))

    def test_loads_real_checkpoint_when_available(self) -> None:
        if not DEFAULT_MODEL_PATH.is_file():
            self.skipTest("weights/best.pt is not available")
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            self.skipTest("Ultralytics is not installed in this environment")

        model = load_model()

        self.assertTrue(hasattr(model, "names"))
        self.assertEqual(len(model.names), 25)
        self.assertIn("NO-Hardhat", model.names.values())

    def test_missing_checkpoint_is_reported(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "YOLO checkpoint not found"):
            load_model("missing-checkpoint.pt")

    def test_detection_result_preserves_names_confidence_boxes_and_dimensions(self) -> None:
        model = FakeModel()
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "unit-test.png"
            Image.new("RGB", (640, 480), color="white").save(image_path)

            result = detect_objects(image_path, model)

        self.assertEqual((result.image_width, result.image_height), (640, 480))
        self.assertEqual([d.class_name for d in result.detections], ["NO-Hardhat", "NO-Safety Vest"])
        self.assertEqual([d.confidence for d in result.detections], [0.91, 0.83])
        self.assertEqual(result.detections[0].bounding_box, (10.0, 20.0, 100.0, 200.0))
        self.assertEqual(model.calls[0][1], False)

    def test_all_supported_ppe_violations_become_hazards(self) -> None:
        assessment = assess_safety(
            make_detection_result("NO-Hardhat", "NO-Safety Vest", "NO-Mask")
        )

        self.assertEqual(
            [hazard.hazard_type for hazard in assessment.detected_hazards],
            [
                "missing_safety_helmet",
                "missing_safety_vest",
                "missing_protective_mask",
            ],
        )
        self.assertEqual(len(assessment.evidence), 3)
        self.assertEqual(len(assessment.recommendations), 3)

    def test_complete_observation_reuses_existing_risk_scoring(self) -> None:
        observation = NormalizedObservation(
            observation_id="obs-1",
            timestamp=datetime.now(timezone.utc),
            source="image",
            labels=("no_helmet",),
            people_count=2,
            duration_minutes=30,
            repeated_count=1,
        )

        assessment = assess_safety(make_detection_result("NO-Hardhat"), observation)

        self.assertEqual(len(assessment.assessments), 1)
        self.assertEqual(assessment.assessments[0].risk_score, 30)
        self.assertEqual(assessment.assessments[0].risk_band, "Moderate")
        self.assertEqual(assessment.recommendations[0].priority, "medium")

    def test_missing_scoring_inputs_leave_assessment_pending(self) -> None:
        observation = NormalizedObservation(
            observation_id="obs-2",
            timestamp=datetime.now(timezone.utc),
            source="image",
            labels=("no_helmet",),
            duration_minutes=30,
            repeated_count=1,
        )

        assessment = assess_safety(make_detection_result("NO-Hardhat"), observation)

        self.assertEqual(len(assessment.detected_hazards), 1)
        self.assertEqual(assessment.assessments, ())
        self.assertEqual(assessment.recommendations[0].priority, "pending")

    def test_supported_violation_proposes_alert(self) -> None:
        decision = decide_alert(assess_safety(make_detection_result("NO-Mask")))

        self.assertTrue(decision.alert_recommended)
        self.assertEqual(decision.priority, "pending")
        self.assertIn("explicit supported PPE violation", decision.reason)

    def test_compliant_only_detection_does_not_propose_alert(self) -> None:
        decision = decide_alert(
            assess_safety(make_detection_result("Person", "Hardhat", "Safety Vest", "Mask"))
        )

        self.assertFalse(decision.alert_recommended)
        self.assertEqual(decision.priority, "none")

    def test_invalid_image_path_is_reported(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "Input image not found"):
            detect_objects("missing-image.jpg", FakeModel())


if __name__ == "__main__":
    unittest.main()
