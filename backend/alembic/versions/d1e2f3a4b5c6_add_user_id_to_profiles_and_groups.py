"""add_user_id_to_profiles_and_groups

Adds a nullable user_id FK to search_profiles and route_groups for multi-user support.
Existing rows keep user_id=NULL — they remain visible only to admins until re-assigned.

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_id to search_profiles — nullable so existing rows are unaffected
    op.add_column(
        "search_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_search_profiles_user_id", "search_profiles", ["user_id"])

    # Add user_id to route_groups — nullable so existing rows are unaffected
    op.add_column(
        "route_groups",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_route_groups_user_id", "route_groups", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_route_groups_user_id", table_name="route_groups")
    op.drop_column("route_groups", "user_id")
    op.drop_index("ix_search_profiles_user_id", table_name="search_profiles")
    op.drop_column("search_profiles", "user_id")
