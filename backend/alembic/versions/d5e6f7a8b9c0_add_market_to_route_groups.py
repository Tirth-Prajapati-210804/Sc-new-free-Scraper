"""add market to route groups

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-05-15 09:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "route_groups",
        sa.Column(
            "market",
            sa.String(length=8),
            nullable=False,
            server_default="us",
        ),
    )
    op.alter_column("route_groups", "market", server_default=None)


def downgrade() -> None:
    op.drop_column("route_groups", "market")
