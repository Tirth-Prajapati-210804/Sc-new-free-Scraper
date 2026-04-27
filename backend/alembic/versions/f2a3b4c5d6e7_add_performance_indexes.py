"""add_performance_indexes

Revision ID: f2a3b4c5d6e7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-22 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_collection_runs_started_at", "collection_runs", ["started_at"])
    op.create_index("ix_scrape_logs_route_group", "scrape_logs", ["route_group_id"])
    op.create_index("ix_scrape_logs_created_at", "scrape_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_scrape_logs_created_at", table_name="scrape_logs")
    op.drop_index("ix_scrape_logs_route_group", table_name="scrape_logs")
    op.drop_index("ix_collection_runs_started_at", table_name="collection_runs")
