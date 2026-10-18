"""Create the initial construction risk persistence schema.

Revision ID: 0001_initial_schema
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observations",
        sa.Column("observation_id", sa.String(length=255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("work_area", sa.Text(), nullable=True),
        sa.Column("people_count", sa.Integer(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("repeated_count", sa.Integer(), nullable=True),
        sa.Column("detection_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("raw_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "people_count IS NULL OR people_count >= 1",
            name="ck_observations_people_count",
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 1",
            name="ck_observations_duration_minutes",
        ),
        sa.CheckConstraint(
            "repeated_count IS NULL OR repeated_count >= 0",
            name="ck_observations_repeated_count",
        ),
        sa.CheckConstraint(
            "detection_confidence IS NULL OR "
            "(detection_confidence >= 0 AND detection_confidence <= 1)",
            name="ck_observations_detection_confidence",
        ),
        sa.PrimaryKeyConstraint("observation_id"),
    )
    op.create_index("ix_observations_observed_at", "observations", ["observed_at"])

    op.create_table(
        "agent_workflow_runs",
        sa.Column(
            "workflow_run_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_id", sa.String(length=255), nullable=True),
        sa.Column("agent_role", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_summary", postgresql.JSONB(), nullable=True),
        sa.Column("output_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "agent_role IN ('hazard_detection', 'risk_assessment', "
            "'safety_response', 'reporting_alerts')",
            name="ck_workflow_runs_agent_role",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_workflow_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["observations.observation_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("workflow_run_id"),
    )
    op.create_index(
        "ix_agent_workflow_runs_workflow_id",
        "agent_workflow_runs",
        ["workflow_id"],
    )
    op.create_index(
        "ix_agent_workflow_runs_observation_id",
        "agent_workflow_runs",
        ["observation_id"],
    )

    op.create_table(
        "detected_hazards",
        sa.Column(
            "detected_hazard_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("observation_id", sa.String(length=255), nullable=False),
        sa.Column("hazard_type", sa.String(length=128), nullable=False),
        sa.Column("source_label", sa.String(length=128), nullable=False),
        sa.Column("detection_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("detector_name", sa.String(length=128), nullable=True),
        sa.Column("detector_version", sa.String(length=64), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint(
            "detection_confidence IS NULL OR "
            "(detection_confidence >= 0 AND detection_confidence <= 1)",
            name="ck_detected_hazards_detection_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["observations.observation_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("detected_hazard_id"),
    )
    op.create_index(
        "ix_detected_hazards_observation_id",
        "detected_hazards",
        ["observation_id"],
    )

    op.create_table(
        "risk_assessments",
        sa.Column(
            "assessment_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("detected_hazard_id", sa.BigInteger(), nullable=False),
        sa.Column("assessment_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=True),
        sa.Column("likelihood", sa.SmallInteger(), nullable=True),
        sa.Column("exposure", sa.SmallInteger(), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_band", sa.String(length=32), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("missing_inputs", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "scoring_rule_version",
            sa.String(length=64),
            server_default="milestone1-v1",
            nullable=False,
        ),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_risk_assessments_status",
        ),
        sa.CheckConstraint(
            "assessment_version >= 1",
            name="ck_risk_assessments_version",
        ),
        sa.CheckConstraint(
            "severity IS NULL OR (severity >= 1 AND severity <= 5)",
            name="ck_risk_assessments_severity",
        ),
        sa.CheckConstraint(
            "likelihood IS NULL OR (likelihood >= 1 AND likelihood <= 5)",
            name="ck_risk_assessments_likelihood",
        ),
        sa.CheckConstraint(
            "exposure IS NULL OR (exposure >= 1 AND exposure <= 4)",
            name="ck_risk_assessments_exposure",
        ),
        sa.CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 1 AND risk_score <= 100)",
            name="ck_risk_assessments_score",
        ),
        sa.CheckConstraint(
            "risk_band IS NULL OR risk_band IN "
            "('Low', 'Moderate', 'High', 'Critical')",
            name="ck_risk_assessments_band",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND risk_score IS NULL AND risk_band IS NULL) "
            "OR (status = 'completed' AND severity IS NOT NULL "
            "AND likelihood IS NOT NULL AND exposure IS NOT NULL "
            "AND risk_score IS NOT NULL AND risk_band IS NOT NULL "
            "AND assessed_at IS NOT NULL)",
            name="ck_risk_assessments_completion_fields",
        ),
        sa.ForeignKeyConstraint(
            ["detected_hazard_id"],
            ["detected_hazards.detected_hazard_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint(
            "detected_hazard_id",
            "assessment_version",
            name="uq_risk_assessments_detection_version",
        ),
    )
    op.create_index(
        "ix_risk_assessments_detected_hazard_id",
        "risk_assessments",
        ["detected_hazard_id"],
    )

    op.create_table(
        "safety_recommendations",
        sa.Column(
            "recommendation_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("detected_hazard_id", sa.BigInteger(), nullable=False),
        sa.Column("assessment_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_workflow_run_id", sa.BigInteger(), nullable=True),
        sa.Column("recommendation_text", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="proposed", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint(
            "status IN ('proposed', 'acknowledged', 'completed', 'dismissed')",
            name="ck_recommendations_status",
        ),
        sa.ForeignKeyConstraint(
            ["detected_hazard_id"],
            ["detected_hazards.detected_hazard_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["risk_assessments.assessment_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_workflow_run_id"],
            ["agent_workflow_runs.workflow_run_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("recommendation_id"),
    )
    op.create_index(
        "ix_safety_recommendations_detected_hazard_id",
        "safety_recommendations",
        ["detected_hazard_id"],
    )
    op.create_index(
        "ix_safety_recommendations_assessment_id",
        "safety_recommendations",
        ["assessment_id"],
    )

    op.create_table(
        "alerts",
        sa.Column(
            "alert_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("observation_id", sa.String(length=255), nullable=False),
        sa.Column("detected_hazard_id", sa.BigInteger(), nullable=True),
        sa.Column("assessment_id", sa.BigInteger(), nullable=True),
        sa.Column("recommendation_id", sa.BigInteger(), nullable=True),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("risk_band", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=True),
        sa.Column("deduplication_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'dismissed')",
            name="ck_alerts_status",
        ),
        sa.CheckConstraint(
            "risk_band IS NULL OR risk_band IN "
            "('Low', 'Moderate', 'High', 'Critical')",
            name="ck_alerts_band",
        ),
        sa.CheckConstraint(
            "detected_hazard_id IS NOT NULL OR assessment_id IS NOT NULL "
            "OR recommendation_id IS NOT NULL",
            name="ck_alerts_source_reference",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["observations.observation_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["detected_hazard_id"],
            ["detected_hazards.detected_hazard_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["risk_assessments.assessment_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["safety_recommendations.recommendation_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("alert_id"),
        sa.UniqueConstraint("deduplication_key"),
    )
    op.create_index("ix_alerts_observation_id", "alerts", ["observation_id"])
    op.create_index(
        "ix_alerts_detected_hazard_id", "alerts", ["detected_hazard_id"]
    )
    op.create_index("ix_alerts_assessment_id", "alerts", ["assessment_id"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("safety_recommendations")
    op.drop_table("risk_assessments")
    op.drop_table("detected_hazards")
    op.drop_table("agent_workflow_runs")
    op.drop_table("observations")
