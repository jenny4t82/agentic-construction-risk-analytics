"""Safety-agent building blocks for future workflow orchestration.

The functions in this module are ordinary Python functions today. They do not
create a LangGraph workflow, write to PostgreSQL, send notifications, or
change the existing API. Model detections remain separate from safety
conclusions and risk scoring remains owned by :mod:`risk_agent`.
"""

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .detector import normalize_detection_label
from .decision_engine import BAND_POLICY, SafetyDecision, evaluate_safety_decision
from .models import DetectedHazard, HazardAssessment, NormalizedObservation
from .risk_agent import LABEL_TO_HAZARD, SiteRiskAgent


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "weights" / "best.pt"
MODEL_PATH_ENV = "HAZARD_DETECTOR_WEIGHTS"


@dataclass(frozen=True)
class SafetyRecommendationDraft:
    """A recommendation ready for a future API or persistence adapter."""

    hazard_type: str
    recommendation_text: str
    priority: str
    status: str = "proposed"


@dataclass(frozen=True)
class Detection:
    """One raw model detection with its original class and bounding box."""

    class_name: str
    confidence: float
    bounding_box: tuple[float, float, float, float]
    class_id: Optional[int] = None


@dataclass(frozen=True)
class DetectionResult:
    """Structured detections and dimensions from one image inference."""

    image_path: Path
    image_width: Optional[int]
    image_height: Optional[int]
    detections: tuple[Detection, ...]


@dataclass(frozen=True)
class SafetyHazardEvidence:
    """A supported hazard conclusion tied to its raw model detection."""

    hazard: DetectedHazard
    detection: Detection


@dataclass(frozen=True)
class SafetyAssessment:
    """Safety findings, evidence, optional scoring, and recommendations."""

    detections: DetectionResult
    detected_hazards: tuple[DetectedHazard, ...]
    evidence: tuple[SafetyHazardEvidence, ...]
    assessments: tuple[HazardAssessment, ...]
    recommendations: tuple[SafetyRecommendationDraft, ...]


AlertDecision = SafetyDecision


RECOMMENDATIONS: dict[str, str] = {
    "missing_safety_helmet": (
        "Require approved head protection before work continues in the affected area."
    ),
    "missing_safety_gloves": (
        "Provide and require suitable protective gloves for the task before work continues."
    ),
    "missing_safety_boots": (
        "Require suitable protective footwear before work continues in the affected area."
    ),
    "missing_safety_goggles": (
        "Provide and require suitable eye protection before work continues."
    ),
    "missing_safety_vest": (
        "Require a high-visibility safety vest before work continues in the affected area."
    ),
    "missing_protective_mask": (
        "Assess the exposure and provide suitable respiratory protection before work continues."
    ),
}


def _resolve_model_path(model_path: Optional[str | Path]) -> Path:
    """Resolve an explicit, configured, or repository-default checkpoint path."""

    configured_path = model_path or os.getenv(MODEL_PATH_ENV)
    path = Path(configured_path) if configured_path else DEFAULT_MODEL_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.expanduser().resolve()


@lru_cache(maxsize=4)
def _load_cached_model(resolved_model_path: str) -> Any:
    """Load one model per resolved checkpoint path and reuse it safely."""

    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "Ultralytics is required to load the PPE model. Use the environment "
            "that contains the project's installed YOLO dependencies."
        ) from error

    try:
        return YOLO(resolved_model_path)
    except Exception as error:
        raise RuntimeError(
            f"Failed to load YOLO checkpoint '{resolved_model_path}': {error}"
        ) from error


def load_model(model_path: Optional[str | Path] = None) -> Any:
    """Load and cache the trained YOLO checkpoint.

    An explicit ``model_path`` takes precedence, followed by
    ``HAZARD_DETECTOR_WEIGHTS``. If neither is supplied, the repository
    checkpoint at ``weights/best.pt`` is used. Missing files raise an
    actionable ``FileNotFoundError``; this function never falls back to mock
    predictions.
    """

    resolved_path = _resolve_model_path(model_path)
    if not resolved_path.is_file():
        raise FileNotFoundError(
            f"YOLO checkpoint not found at '{resolved_path}'. Provide an existing "
            f"checkpoint with {MODEL_PATH_ENV} or pass model_path explicitly."
        )
    return _load_cached_model(str(resolved_path))


def _class_name(names: Any, class_id: int) -> str:
    """Read a class name from the model result's actual names mapping."""

    if isinstance(names, Mapping):
        return str(names.get(class_id, class_id))
    if isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        if 0 <= class_id < len(names):
            return str(names[class_id])
    return str(class_id)


def _scalar(value: Any) -> float:
    """Convert tensor-like scalar values returned by Ultralytics to float."""

    item = getattr(value, "item", None)
    return float(item() if callable(item) else value)


def detect_objects(image_path: str | Path, model: Any) -> DetectionResult:
    """Run the supplied YOLO model on an existing construction-site image.

    The result preserves the model's actual class names, confidence values,
    and ``xyxy`` coordinates. This function does not infer PPE compliance
    from missing detections; that interpretation belongs to ``assess_safety``.
    """

    resolved_image_path = Path(image_path).expanduser().resolve()
    if not resolved_image_path.is_file():
        raise FileNotFoundError(
            f"Input image not found at '{resolved_image_path}'. Provide an existing image file."
        )
    if model is None or not callable(getattr(model, "predict", None)):
        raise TypeError("model must provide a callable predict method")

    try:
        from PIL import Image  # type: ignore

        with Image.open(resolved_image_path) as image:
            image.load()
            image_width, image_height = image.size
    except Exception as error:
        raise ValueError(
            f"Input image could not be decoded at '{resolved_image_path}': {error}"
        ) from error

    try:
        results = model.predict(source=str(resolved_image_path), verbose=False)
    except Exception as error:
        raise RuntimeError(
            f"YOLO inference failed for '{resolved_image_path}': {error}"
        ) from error

    detections: list[Detection] = []
    for result in results or ():
        names = getattr(result, "names", {})
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue

        for index in range(len(boxes)):
            class_id = int(_scalar(boxes.cls[index]))
            confidence = _scalar(boxes.conf[index])
            coordinates = boxes.xyxy[index].tolist()
            if len(coordinates) != 4:
                raise RuntimeError(
                    f"YOLO returned an invalid bounding box for detection {index}."
                )
            detections.append(
                Detection(
                    class_name=_class_name(names, class_id),
                    confidence=confidence,
                    bounding_box=tuple(float(value) for value in coordinates),
                    class_id=class_id,
                )
            )

    return DetectionResult(
        image_path=resolved_image_path,
        image_width=image_width,
        image_height=image_height,
        detections=tuple(detections),
    )


def recommendation_for_hazard(hazard_type: str) -> Optional[str]:
    """Return a recommendation for a supported hazard type, if available."""

    return RECOMMENDATIONS.get(hazard_type)


def _priority_for_assessment(assessment: Optional[HazardAssessment]) -> str:
    """Translate an existing project risk band into response priority."""

    if assessment is None:
        return "pending"
    policy = BAND_POLICY.get(assessment.risk_band)
    return policy[1] if policy is not None else "pending"


def build_safety_recommendations(
    detected_hazards: Sequence[DetectedHazard],
    assessments: Sequence[HazardAssessment] = (),
) -> list[SafetyRecommendationDraft]:
    """Build proposed responses without changing or recalculating risk scores."""

    assessment_by_hazard = {
        (assessment.hazard_type, assessment.source_label): assessment
        for assessment in assessments
    }
    recommendations: list[SafetyRecommendationDraft] = []
    for hazard in detected_hazards:
        recommendation_text = recommendation_for_hazard(hazard.hazard_type)
        if recommendation_text is None:
            continue
        assessment = assessment_by_hazard.get(
            (hazard.hazard_type, hazard.source_label)
        )
        recommendations.append(
            SafetyRecommendationDraft(
                hazard_type=hazard.hazard_type,
                recommendation_text=recommendation_text,
                priority=_priority_for_assessment(assessment),
            )
        )
    return recommendations


def assess_safety(
    detections: DetectionResult,
    observation: Optional[NormalizedObservation] = None,
    observation_id: str = "image-observation",
) -> SafetyAssessment:
    """Convert explicit PPE-violation detections into a safety assessment.

    Only supported violation labels, through the existing detector mapping,
    become hazards. A completed risk assessment is produced only when the
    supplied observation has all inputs required by ``SiteRiskAgent``;
    otherwise the hazard and recommendation remain pending.
    """

    resolved_observation_id = (
        observation.observation_id if observation is not None else observation_id
    )
    agent = SiteRiskAgent()
    evidence: list[SafetyHazardEvidence] = []
    detected_hazards: list[DetectedHazard] = []
    assessments: list[HazardAssessment] = []

    for detection in detections.detections:
        normalized_label = normalize_detection_label(detection.class_name)
        if normalized_label is None:
            continue

        hazard = DetectedHazard(
            observation_id=resolved_observation_id,
            hazard_type=LABEL_TO_HAZARD[normalized_label],
            source_label=normalized_label,
            detection_confidence=detection.confidence,
        )
        detected_hazards.append(hazard)
        evidence.append(SafetyHazardEvidence(hazard=hazard, detection=detection))

        if observation is not None:
            assessment = agent.assess_hazard(hazard, observation)
            if assessment is not None:
                assessments.append(assessment)

    recommendations = build_safety_recommendations(detected_hazards, assessments)
    return SafetyAssessment(
        detections=detections,
        detected_hazards=tuple(detected_hazards),
        evidence=tuple(evidence),
        assessments=tuple(assessments),
        recommendations=tuple(recommendations),
    )


def decide_alert(assessment: SafetyAssessment) -> AlertDecision:
    """Apply the shared pure decision policy to experimental Safety Agent output."""
    return evaluate_safety_decision(
        assessment.detected_hazards,
        assessment.assessments,
        detection_complete=assessment.detections is not None,
    )
