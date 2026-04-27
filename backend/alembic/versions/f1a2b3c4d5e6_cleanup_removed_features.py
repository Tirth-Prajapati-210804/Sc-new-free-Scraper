"""cleanup_removed_features

Drops orphaned tables from removed features (Search Profiles, multi-user Search
Profiles), and fixes the currency server_default in all_flight_results from USD
to CAD to match the SerpAPI provider configuration.

Revision ID: f1a2b3c4d5e6
Revises: e2f3a4b5c6d7
Create Date: 2026-04-17 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop orphaned tables created by the removed Search Profiles feature.
    # flight_prices depends on search_legs and search_profiles via FKs, so
    # drop it first, then the parent tables.
    op.drop_table("flight_prices")
    op.drop_index("ix_search_profiles_user_id", table_name="search_profiles")
    op.drop_table("search_legs")
    op.drop_table("search_profiles")

    # Fix currency default in all_flight_results: was USD, should be CAD
    # to match the SerpAPI provider which returns CAD prices.
    op.alter_column(
        "all_flight_results",
        "currency",
        server_default=sa.text("'CAD'"),
        existing_type=sa.String(8),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "all_flight_results",
        "currency",
        server_default=sa.text("'USD'"),
        existing_type=sa.String(8),
        existing_nullable=False,
    )
    # Restore orphaned tables (downgrade only — not intended for production use)
    op.create_table(
        "search_profiles",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("days_ahead", sa.Integer(), nullable=False, server_default=sa.text("365")),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_search_profiles_user_id", "search_profiles", ["user_id"])
    op.create_table(
        "search_legs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leg_order", sa.Integer(), nullable=False),
        sa.Column("origin_query", sa.String(200), nullable=False),
        sa.Column("destination_query", sa.String(200), nullable=False),
    )
    op.create_table(
        "flight_prices",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("leg_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("destination", sa.String(10), nullable=False),
        sa.Column("depart_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("provider", sa.String(50), nullable=False),
    )
