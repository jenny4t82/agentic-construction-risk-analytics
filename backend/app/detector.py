"""Hazard detector adapter and class mapping for visual site observations.

This module decouples computer-vision inference from the risk-assessment core.
It filters detected objects to supported violation classes, translates them to
normalized hazard labels, counts people from contextual person detections, and
ensures compliant gear or ordinary site equipment are not treated as hazards.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set


# Roboflow Construction Site Safety (25 classes) mappings
ROBOFLOW_HAZARD_MAP: Dict[str, str] = {
    "NO-Hardhat": "no_helmet",
    "NO-Safety Vest": "no_vest",
    "NO-Mask": "no_mask",
}

# Ordinary equipment and compliant items that must NEVER be treated as hazards
NON_HAZARD_CLASSES: Set[str] = {
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
    "SUV",
    "bus",
    "mini-van",
    "semi",
    "trailer",
    "truck and trailer",
    "fire hydrant",
    "van",
}


def normalize_detection_label(raw_label: str) -> Optional[str]:
    """Map raw model/dataset class names to project normalized hazard labels.

    Returns None for non-hazards or unknown classes.
    """
    clean_label = raw_label.strip()
    if clean_label in ROBOFLOW_HAZARD_MAP:
        return ROBOFLOW_HAZARD_MAP[clean_label]

    # Flexible matching for lowercased, underscored, or hyphenated variants
    normalized_key = clean_label.lower().replace("_", "-").replace(" ", "-")
    for key, val in ROBOFLOW_HAZARD_MAP.items():
        if key.lower().replace("_", "-").replace(" ", "-") == normalized_key:
            return val

    # Direct fallback for already-normalized labels
    if clean_label in ("no_helmet", "no_vest", "no_mask", "no_gloves", "no_boots", "no_goggle"):
        return clean_label

    return None


@dataclass(frozen=True)
class BoundingBox:
    """A detected bounding box with confidence and class metadata."""

    class_name: str
    confidence: float
    x_min: float = 0.0
    y_min: float = 0.0
    x_max: float = 0.0
    y_max: float = 0.0
    class_id: Optional[int] = None


@dataclass(frozen=True)
class DetectionResult:
    """Filtered detection result ready for normalized observation construction."""

    hazard_labels: Sequence[str] = field(default_factory=tuple)
    people_count: int = 0
    boxes: Sequence[BoundingBox] = field(default_factory=tuple)
    max_confidence: Optional[float] = None


class BaseHazardDetector(ABC):
    """Abstract interface for construction hazard detectors."""

    @abstractmethod
    def detect(self, image_bytes: bytes) -> DetectionResult:
        """Run detection on image bytes and return filtered hazard results."""
        raise NotImplementedError


class UnconfiguredHazardDetector(BaseHazardDetector):
    """Placeholder detector when neither model weights nor mock mode are configured."""

    def detect(self, image_bytes: bytes) -> DetectionResult:
        raise RuntimeError(
            "Hazard detector is not configured. Provide model weights or enable "
            "explicit mock mode (e.g. HAZARD_DETECTOR_MODE=mock) for testing."
        )


class MockHazardDetector(BaseHazardDetector):
    """Deterministic mock detector for tests and headless environments.

    Does not require model weights, PyTorch, or GPU resources.
    """

    def __init__(
        self,
        canned_boxes: Optional[Sequence[BoundingBox]] = None,
        default_people_count: Optional[int] = None,
    ) -> None:
        self.canned_boxes = list(canned_boxes) if canned_boxes is not None else []
        self.default_people_count = default_people_count

    def set_canned_boxes(self, boxes: Sequence[BoundingBox]) -> None:
        """Update canned detections for subsequent test calls."""
        self.canned_boxes = list(boxes)

    def detect(self, image_bytes: bytes) -> DetectionResult:
        """Process canned detections and apply the standard filtering rules."""
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        hazard_labels: List[str] = []
        confidences: List[float] = []
        person_count = 0

        for box in self.canned_boxes:
            normalized_hazard = normalize_detection_label(box.class_name)
            if normalized_hazard is not None:
                if normalized_hazard not in hazard_labels:
                    hazard_labels.append(normalized_hazard)
                confidences.append(box.confidence)
            elif box.class_name.strip().lower() == "person":
                person_count += 1
            # Other classes (Hardhat, Safety Cone, Excavator, etc.) are deliberately ignored.

        if self.default_people_count is not None:
            person_count = self.default_people_count

        max_conf = max(confidences) if confidences else None

        return DetectionResult(
            hazard_labels=tuple(hazard_labels),
            people_count=person_count,
            boxes=tuple(self.canned_boxes),
            max_confidence=max_conf,
        )


class YOLOv8HazardDetector(BaseHazardDetector):
    """Ultralytics YOLOv8 detector adapter for local inference with trained weights.

    Requires optional dependencies from requirements-ml.txt.
    """

    def __init__(self, weights_path: str, confidence_threshold: float = 0.25) -> None:
        self.weights_path = weights_path
        self.confidence_threshold = confidence_threshold
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from ultralytics import YOLO  # type: ignore
            except ImportError as err:
                raise RuntimeError(
                    "ultralytics is required for YOLOv8HazardDetector. "
                    "Install optional dependencies from requirements-ml.txt."
                ) from err
            try:
                self._model = YOLO(self.weights_path)
            except Exception as err:
                raise RuntimeError(
                    f"Failed to load hazard detector weights from '{self.weights_path}': {err}"
                ) from err
        return self._model

    def detect(self, image_bytes: bytes) -> DetectionResult:
        """Run YOLO inference and extract normalized hazard labels."""
        import io

        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        try:
            from PIL import Image  # type: ignore
        except ImportError as err:
            raise RuntimeError(
                "Pillow is required for image decoding. "
                "Install optional dependencies from requirements-ml.txt."
            ) from err

        model = self._load_model()
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image.load()
        except Exception as err:
            raise ValueError(f"Failed to decode or parse image: {err}") from err

        try:
            results = model.predict(image, conf=self.confidence_threshold, verbose=False)
        except Exception as err:
            raise ValueError(f"Inference execution failed on image: {err}") from err

        boxes: List[BoundingBox] = []
        hazard_labels: List[str] = []
        confidences: List[float] = []
        person_count = 0

        if results and len(results) > 0:
            result = results[0]
            names = result.names
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                cls_name = names.get(cls_id, str(cls_id))

                coords = box.xyxy[0].tolist()
                bbox = BoundingBox(
                    class_name=cls_name,
                    confidence=conf,
                    x_min=coords[0],
                    y_min=coords[1],
                    x_max=coords[2],
                    y_max=coords[3],
                    class_id=cls_id,
                )
                boxes.append(bbox)

                normalized_hazard = normalize_detection_label(cls_name)
                if normalized_hazard is not None:
                    if normalized_hazard not in hazard_labels:
                        hazard_labels.append(normalized_hazard)
                    confidences.append(conf)
                elif cls_name.strip().lower() == "person":
                    person_count += 1

        return DetectionResult(
            hazard_labels=tuple(hazard_labels),
            people_count=person_count,
            boxes=tuple(boxes),
            max_confidence=max(confidences) if confidences else None,
        )
