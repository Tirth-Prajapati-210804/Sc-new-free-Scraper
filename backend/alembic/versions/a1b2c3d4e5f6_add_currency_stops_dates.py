"""add_currency_stops_dates

Adds currency, max_stops, start_date, and end_date columns to route_groups.

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-04-19 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "route_groups",
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
    )
    op.add_column("route_groups", sa.Column("max_stops", sa.Integer(), nullable=True))
    op.add_column("route_groups", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("route_groups", sa.Column("end_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("route_groups", "end_date")
    op.drop_column("route_groups", "start_date")
    op.drop_column("route_groups", "max_stops")
    op.drop_column("route_groups", "currency")
