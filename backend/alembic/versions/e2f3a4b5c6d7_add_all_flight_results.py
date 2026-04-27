"""add_all_flight_results

Stores every flight offer returned by every provider (not just the cheapest).
Used to populate the "All Results" sheet in the Excel export.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "all_flight_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "route_group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("route_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
    )
    op.create_index(
        "ix_all_flight_results_group_route_date",
        "all_flight_results",
        ["route_group_id", "origin", "destination", "depart_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_all_flight_results_group_route_date", table_name="all_flight_results")
    op.drop_table("all_flight_results")
