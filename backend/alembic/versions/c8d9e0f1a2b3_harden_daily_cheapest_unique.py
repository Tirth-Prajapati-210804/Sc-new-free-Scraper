"""Repair daily_cheapest + route_groups unique constraints (idempotent)

Revision ID: c8d9e0f1a2b3
Revises: becab032ed06
Create Date: 2026-04-26

Two real bugs this migration cleans up — both observed against the live
Render+Supabase deploy:

1. daily_cheapest_prices: the earlier b2c3d4e5f6a7 migration swapped the
   UNIQUE constraint from (origin, destination, depart_date) to the 4-column
   form INCLUDING route_group_id. The auto-generated 34756a4a8d9b then
   *reverted* it (because the model still had the old 3-column constraint
   in __table_args__). Result: every INSERT … ON CONFLICT
   (route_group_id, origin, destination, depart_date) failed with
   InvalidColumnReferenceError and the scraper was burning provider quota
   for zero rows persisted.

2. route_groups: the initial schema and the model both declared a *global*
   UNIQUE on `name`. As soon as a second user picked any name a previous
   user already used, the POST /route-groups call 500'd with a duplicate-key
   error. The right scope is per-owner, which we already have via
   uq_routegroups_user_name.

Idempotent on purpose: drops every legacy constraint variant by name, then
adds the canonical ones only if missing. Safe to re-run.
"""
from __future__ import annotations

from alembic import op

revision = "c8d9e0f1a2b3"
down_revision = "becab032ed06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── daily_cheapest_prices ────────────────────────────────────────────
    op.execute(
        "ALTER TABLE daily_cheapest_prices "
        "DROP CONSTRAINT IF EXISTS "
        "daily_cheapest_prices_origin_destination_depart_date_key"
    )
    op.execute(
        "ALTER TABLE daily_cheapest_prices "
        "DROP CONSTRAINT IF EXISTS uq_daily_cheapest_per_group"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_daily_cheapest_per_group'
                  AND conrelid = 'daily_cheapest_prices'::regclass
            ) THEN
                ALTER TABLE daily_cheapest_prices
                ADD CONSTRAINT uq_daily_cheapest_per_group
                UNIQUE (route_group_id, origin, destination, depart_date);
            END IF;
        END$$;
        """
    )

    # ── route_groups ─────────────────────────────────────────────────────
    # Drop the legacy global UNIQUE(name). uq_routegroups_user_name (added by
    # 34756a4a8d9b) already enforces the correct per-owner scope.
    op.execute(
        "ALTER TABLE route_groups "
        "DROP CONSTRAINT IF EXISTS route_groups_name_key"
    )
    # Make sure the per-owner constraint is in place even on databases where
    # the prior migration somehow didn't take.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_routegroups_user_name'
                  AND conrelid = 'route_groups'::regclass
            ) THEN
                ALTER TABLE route_groups
                ADD CONSTRAINT uq_routegroups_user_name
                UNIQUE (user_id, name);
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE daily_cheapest_prices "
        "DROP CONSTRAINT IF EXISTS uq_daily_cheapest_per_group"
    )
    op.execute(
        "ALTER TABLE daily_cheapest_prices "
        "ADD CONSTRAINT daily_cheapest_prices_origin_destination_depart_date_key "
        "UNIQUE (origin, destination, depart_date)"
    )
    op.execute(
        "ALTER TABLE route_groups "
        "ADD CONSTRAINT route_groups_name_key UNIQUE (name)"
    )
