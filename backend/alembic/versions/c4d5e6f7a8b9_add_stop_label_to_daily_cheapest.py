from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_cheapest_prices",
        sa.Column("stop_label", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("daily_cheapest_prices", "stop_label")
