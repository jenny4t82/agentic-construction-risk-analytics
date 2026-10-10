"""Data models used by the first rule-based backend version.

These models use only Python's standard library so the scoring logic can be
tested before FastAPI, a database, or computer-vision packages are added.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple


@dataclass(frozen=True)
class NormalizedObservation:
    """A consistent representation of one monitoring observation.

    ``labels`` are normalized labels supplied by a future data loader. For
    now, tests use synthetic labels and do not represent real site records.
    ``detection_confidence`` describes model certainty only; it is not the
    accident likelihood used by the project-defined risk formula.
    """

    observation_id: str
    timestamp: datetime
    source: str
    labels: Tuple[str, ...] = field(default_factory=tuple)
    people_count: int = 1
    duration_minutes: int = 1
    repeated_count: int = 0
    work_area: str = "unspecified"
    detection_confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.observation_id.strip():
            raise ValueError("observation_id must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not self.labels:
            raise ValueError("at least one observation label is required")
        if self.people_count < 1:
            raise ValueError("people_count must be at least 1")
        if self.duration_minutes < 1:
            raise ValueError("duration_minutes must be at least 1")
        if self.repeated_count < 0:
            raise ValueError("repeated_count cannot be negative")
        if self.detection_confidence is not None and not 0 <= self.detection_confidence <= 1:
            raise ValueError("detection_confidence must be between 0 and 1")


@dataclass(frozen=True)
class HazardAssessment:
    """The explainable result produced for one detected hazard."""

    observation_id: str
    hazard_type: str
    source_label: str
    severity: int
    likelihood: int
    exposure: int
    risk_score: int
    risk_band: str
    detection_confidence: Optional[float]
    explanation: str
