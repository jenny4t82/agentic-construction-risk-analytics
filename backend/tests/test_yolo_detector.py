"""Dependency-free tests for the Ultralytics detector adapter."""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.detector import YOLOv8HazardDetector


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


class FakeBox:
    def __init__(self, class_id: int, confidence: float) -> None:
        self.cls = [FakeScalar(class_id)]
        self.conf = [FakeScalar(confidence)]
        self.xyxy = [FakeCoordinates([1.0, 2.0, 30.0, 40.0])]


class FakeResult:
    names = {
        0: "Excavator",
        1: "Hardhat",
        2: "NO-Hardhat",
        3: "NO-Mask",
        4: "NO-Safety Vest",
        5: "Person",
        6: "Safety Vest",
        7: "truck",
    }

    def __init__(self) -> None:
        self.boxes = [
            FakeBox(2, 0.91),
            FakeBox(3, 0.82),
            FakeBox(4, 0.88),
            FakeBox(5, 0.95),
            FakeBox(1, 0.94),
            FakeBox(6, 0.93),
            FakeBox(7, 0.90),
            FakeBox(0, 0.89),
        ]


class FakeModel:
    instances = 0
    predictions = 0

    def __init__(self, weights_path: str) -> None:
        type(self).instances += 1
        self.weights_path = weights_path

    def predict(self, image: object, conf: float, verbose: bool) -> list[FakeResult]:
        type(self).predictions += 1
        return [FakeResult()]


class FakeImage:
    def load(self) -> None:
        return None


class YoloDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeModel.instances = 0
        FakeModel.predictions = 0
        self.fake_ultralytics = types.SimpleNamespace(YOLO=FakeModel)
        self.fake_image_module = types.SimpleNamespace(
            open=lambda image_bytes: FakeImage()
        )
        self.fake_pil = types.SimpleNamespace(Image=self.fake_image_module)

    def test_supported_violations_are_mapped_and_other_classes_filtered(self) -> None:
        detector = YOLOv8HazardDetector("synthetic-best.pt")

        with patch.dict(
            sys.modules,
            {
                "ultralytics": self.fake_ultralytics,
                "PIL": self.fake_pil,
                "PIL.Image": self.fake_image_module,
            },
        ):
            result = detector.detect(b"synthetic-image")

        self.assertEqual(
            set(result.hazard_labels), {"no_helmet", "no_mask", "no_vest"}
        )
        self.assertEqual(result.people_count, 1)
        self.assertEqual(result.max_confidence, 0.91)
        self.assertEqual(len(result.boxes), 8)

    def test_model_is_loaded_once_per_detector_instance(self) -> None:
        detector = YOLOv8HazardDetector("synthetic-best.pt")

        with patch.dict(
            sys.modules,
            {
                "ultralytics": self.fake_ultralytics,
                "PIL": self.fake_pil,
                "PIL.Image": self.fake_image_module,
            },
        ):
            detector.detect(b"synthetic-image")
            detector.detect(b"synthetic-image")

        self.assertEqual(FakeModel.instances, 1)
        self.assertEqual(FakeModel.predictions, 2)

    def test_invalid_or_missing_weights_raises_runtime_error(self) -> None:
        class FailingModel:
            def __init__(self, weights_path: str) -> None:
                raise FileNotFoundError(f"No such file or directory: '{weights_path}'")

        failing_ultralytics = types.SimpleNamespace(YOLO=FailingModel)
        detector = YOLOv8HazardDetector("nonexistent-weights.pt")

        with patch.dict(
            sys.modules,
            {
                "ultralytics": failing_ultralytics,
                "PIL": self.fake_pil,
                "PIL.Image": self.fake_image_module,
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "Failed to load hazard detector weights"):
                detector.detect(b"synthetic-image")


if __name__ == "__main__":
    unittest.main()
