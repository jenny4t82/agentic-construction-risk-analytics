"""Record when an alert was dismissed.

Revision ID: 0003_alert_dismissed_at
Revises: 0002_user_accounts
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_alert_dismissed_at"
down_revision = "0002_user_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "dismissed_at")
