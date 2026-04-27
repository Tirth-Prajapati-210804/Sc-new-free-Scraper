"""add stops and duration_minutes to daily_cheapest_prices

Revision ID: e8f3a1b2c4d5
Revises: 0b2f4d5cbeb7
Create Date: 2026-04-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f3a1b2c4d5"
down_revision: Union[str, None] = "0b2f4d5cbeb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "daily_cheapest_prices",
        sa.Column("stops", sa.Integer(), nullable=True),
    )
    op.add_column(
        "daily_cheapest_prices",
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("daily_cheapest_prices", "duration_minutes")
    op.drop_column("daily_cheapest_prices", "stops")
