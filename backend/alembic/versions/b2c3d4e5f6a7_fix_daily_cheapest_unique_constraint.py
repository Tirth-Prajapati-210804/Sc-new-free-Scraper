"""Fix daily_cheapest_prices unique constraint to include route_group_id

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-18

Problem: The old constraint (origin, destination, depart_date) meant two different
route groups scraping the same route/date would overwrite each other's data.
Fix: Constraint now includes route_group_id so each group keeps its own cheapest price.
"""
from __future__ import annotations

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old cross-group constraint
    op.drop_constraint(
        "daily_cheapest_prices_origin_destination_depart_date_key",
        "daily_cheapest_prices",
        type_="unique",
    )
    # Add per-route-group constraint — each group tracks its own cheapest price
    op.create_unique_constraint(
        "uq_daily_cheapest_per_group",
        "daily_cheapest_prices",
        ["route_group_id", "origin", "destination", "depart_date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_daily_cheapest_per_group", "daily_cheapest_prices", type_="unique")
    op.create_unique_constraint(
        "daily_cheapest_prices_origin_destination_depart_date_key",
        "daily_cheapest_prices",
        ["origin", "destination", "depart_date"],
    )
