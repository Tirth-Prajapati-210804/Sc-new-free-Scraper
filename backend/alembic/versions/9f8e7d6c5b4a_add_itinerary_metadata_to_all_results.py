from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "9f8e7d6c5b4a"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "all_flight_results",
        sa.Column("stop_label", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "all_flight_results",
        sa.Column("itinerary_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("all_flight_results", "itinerary_data")
    op.drop_column("all_flight_results", "stop_label")
