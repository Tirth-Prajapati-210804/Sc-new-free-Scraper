"""add_search_profiles_legs_prices

Revision ID: c3d4e5f6a7b8
Revises: e8f3a1b2c4d5
Create Date: 2026-04-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "e8f3a1b2c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- search_profiles ---
    op.create_table(
        "search_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("days_ahead", sa.Integer(), nullable=False, server_default=sa.text("365")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- search_legs ---
    op.create_table(
        "search_legs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leg_order", sa.Integer(), nullable=False),
        sa.Column("origin_query", sa.String(200), nullable=False),
        sa.Column("destination_query", sa.String(200), nullable=False),
        sa.Column("resolved_origins", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("resolved_destinations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("min_halt_hours", sa.Float(), nullable=True),
        sa.Column("max_halt_hours", sa.Float(), nullable=True),
        sa.UniqueConstraint("profile_id", "leg_order", name="uq_search_legs_profile_order"),
    )

    # --- flight_prices ---
    op.create_table(
        "flight_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("leg_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("search_legs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("destination", sa.String(10), nullable=False),
        sa.Column("depart_date", sa.Date(), nullable=False),
        sa.Column("airline", sa.String(100), nullable=False, server_default=sa.text("''")),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("deep_link", sa.String(2048), nullable=True),
        sa.Column("stops", sa.Integer(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("leg_id", "origin", "destination", "depart_date", name="uq_flight_prices_leg_route_date"),
    )


def downgrade() -> None:
    op.drop_table("flight_prices")
    op.drop_table("search_legs")
    op.drop_table("search_profiles")
