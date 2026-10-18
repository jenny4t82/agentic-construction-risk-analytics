"""SQLAlchemy ORM models for the PostgreSQL persistence layer.

These classes are deliberately separate from the API dataclasses and Pydantic
models. They describe database storage and relationships only; Alembic owns
schema creation and the application does not call ``create_all()`` at startup.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all PostgreSQL ORM models."""


class Observation(Base):
    """Persisted input observation, including nullable risk inputs."""

    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint(
            "people_count IS NULL OR people_count >= 1",
            name="ck_observations_people_count",
        ),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 1",
            name="ck_observations_duration_minutes",
        ),
        CheckConstraint(
            "repeated_count IS NULL OR repeated_count >= 0",
            name="ck_observations_repeated_count",
        ),
        CheckConstraint(
            "detection_confidence IS NULL OR "
            "(detection_confidence >= 0 AND detection_confidence <= 1)",
            name="ck_observations_detection_confidence",
        ),
    )

    observation_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    work_area: Mapped[str | None] = mapped_column(Text, nullable=True)
    people_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repeated_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detection_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    detected_hazards: Mapped[list["DetectedHazardRecord"]] = relationship(
        back_populates="observation"
    )
    workflow_runs: Mapped[list["AgentWorkflowRun"]] = relationship(
        back_populates="observation"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="observation")


class AgentWorkflowRun(Base):
    """Audit row for one role execution within a logical workflow."""

    __tablename__ = "agent_workflow_runs"
    __table_args__ = (
        CheckConstraint(
            "agent_role IN ("
            "'hazard_detection', 'risk_assessment', "
            "'safety_response', 'reporting_alerts')",
            name="ck_workflow_runs_agent_role",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_workflow_runs_status",
        ),
    )

    workflow_run_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    workflow_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False, default=uuid4, index=True
    )
    observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("observations.observation_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    agent_role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    input_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    observation: Mapped[Observation | None] = relationship(
        back_populates="workflow_runs"
    )
    recommendations: Mapped[list["SafetyRecommendation"]] = relationship(
        back_populates="created_by_workflow_run"
    )


class DetectedHazardRecord(Base):
    """A persisted hazard detection, independent of risk scoring."""

    __tablename__ = "detected_hazards"
    __table_args__ = (
        CheckConstraint(
            "detection_confidence IS NULL OR "
            "(detection_confidence >= 0 AND detection_confidence <= 1)",
            name="ck_detected_hazards_detection_confidence",
        ),
    )

    detected_hazard_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("observations.observation_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    hazard_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_label: Mapped[str] = mapped_column(String(128), nullable=False)
    detection_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    detector_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detector_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    observation: Mapped[Observation] = relationship(back_populates="detected_hazards")
    assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="detected_hazard"
    )
    recommendations: Mapped[list["SafetyRecommendation"]] = relationship(
        back_populates="detected_hazard"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="detected_hazard")


class RiskAssessment(Base):
    """A versioned pending or completed assessment for one detection."""

    __tablename__ = "risk_assessments"
    __table_args__ = (
        UniqueConstraint(
            "detected_hazard_id",
            "assessment_version",
            name="uq_risk_assessments_detection_version",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_risk_assessments_status",
        ),
        CheckConstraint(
            "assessment_version >= 1",
            name="ck_risk_assessments_version",
        ),
        CheckConstraint(
            "severity IS NULL OR (severity >= 1 AND severity <= 5)",
            name="ck_risk_assessments_severity",
        ),
        CheckConstraint(
            "likelihood IS NULL OR (likelihood >= 1 AND likelihood <= 5)",
            name="ck_risk_assessments_likelihood",
        ),
        CheckConstraint(
            "exposure IS NULL OR (exposure >= 1 AND exposure <= 4)",
            name="ck_risk_assessments_exposure",
        ),
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 1 AND risk_score <= 100)",
            name="ck_risk_assessments_score",
        ),
        CheckConstraint(
            "risk_band IS NULL OR risk_band IN "
            "('Low', 'Moderate', 'High', 'Critical')",
            name="ck_risk_assessments_band",
        ),
        CheckConstraint(
            "(status = 'pending' AND risk_score IS NULL AND risk_band IS NULL) "
            "OR (status = 'completed' AND severity IS NOT NULL "
            "AND likelihood IS NOT NULL AND exposure IS NOT NULL "
            "AND risk_score IS NOT NULL AND risk_band IS NOT NULL "
            "AND assessed_at IS NOT NULL)",
            name="ck_risk_assessments_completion_fields",
        ),
    )

    assessment_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    detected_hazard_id: Mapped[int] = mapped_column(
        ForeignKey("detected_hazards.detected_hazard_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assessment_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending"
    )
    severity: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    likelihood: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    exposure: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_inputs: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    scoring_rule_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="milestone1-v1"
    )
    assessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    detected_hazard: Mapped[DetectedHazardRecord] = relationship(
        back_populates="assessments"
    )
    recommendations: Mapped[list["SafetyRecommendation"]] = relationship(
        back_populates="assessment"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="assessment")


class SafetyRecommendation(Base):
    """A response action associated with a detected hazard."""

    __tablename__ = "safety_recommendations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'acknowledged', 'completed', 'dismissed')",
            name="ck_recommendations_status",
        ),
    )

    recommendation_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    detected_hazard_id: Mapped[int] = mapped_column(
        ForeignKey("detected_hazards.detected_hazard_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("risk_assessments.assessment_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_by_workflow_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_workflow_runs.workflow_run_id", ondelete="RESTRICT"),
        nullable=True,
    )
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="proposed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    detected_hazard: Mapped[DetectedHazardRecord] = relationship(
        back_populates="recommendations"
    )
    assessment: Mapped[RiskAssessment | None] = relationship(
        back_populates="recommendations"
    )
    created_by_workflow_run: Mapped[AgentWorkflowRun | None] = relationship(
        back_populates="recommendations"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="recommendation")


class Alert(Base):
    """A notification or escalation event."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'dismissed')",
            name="ck_alerts_status",
        ),
        CheckConstraint(
            "risk_band IS NULL OR risk_band IN "
            "('Low', 'Moderate', 'High', 'Critical')",
            name="ck_alerts_band",
        ),
        CheckConstraint(
            "detected_hazard_id IS NOT NULL OR assessment_id IS NOT NULL "
            "OR recommendation_id IS NOT NULL",
            name="ck_alerts_source_reference",
        ),
    )

    alert_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("observations.observation_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    detected_hazard_id: Mapped[int | None] = mapped_column(
        ForeignKey("detected_hazards.detected_hazard_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("risk_assessments.assessment_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("safety_recommendations.recommendation_id", ondelete="RESTRICT"),
        nullable=True,
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    risk_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="open"
    )
    recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deduplication_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    observation: Mapped[Observation] = relationship(back_populates="alerts")
    detected_hazard: Mapped[DetectedHazardRecord | None] = relationship(
        back_populates="alerts"
    )
    assessment: Mapped[RiskAssessment | None] = relationship(
        back_populates="alerts"
    )
    recommendation: Mapped[SafetyRecommendation | None] = relationship(
        back_populates="alerts"
    )
