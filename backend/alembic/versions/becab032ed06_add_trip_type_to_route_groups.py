"""add trip_type to route_groups

Revision ID: becab032ed06
Revises: 34756a4a8d9b
Create Date: 2026-04-25 22:02:41.409114

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'becab032ed06'
down_revision: Union[str, None] = '34756a4a8d9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "route_groups",
        sa.Column(
            "trip_type",
            sa.String(length=20),
            nullable=False,
            server_default="one_way",
        ),
    )


def downgrade() -> None:
    op.drop_column("route_groups", "trip_type")