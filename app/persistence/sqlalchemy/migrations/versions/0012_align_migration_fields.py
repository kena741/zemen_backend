"""Align marketing_tracker_column and service_tier_payment for Supabase migration.

Revision ID: 0012_align_migration_fields
Revises: 0011_fix_schema_gaps
Create Date: 2026-11-26 01:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_align_migration_fields"
down_revision: Union[str, Sequence[str], None] = "0011_fix_schema_gaps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. marketing_tracker_column: add sheet_id and width_px from Supabase
    op.execute(
        sa.text("ALTER TABLE marketing_tracker_column ADD COLUMN IF NOT EXISTS sheet_id UUID")
    )
    op.execute(
        sa.text("ALTER TABLE marketing_tracker_column ADD COLUMN IF NOT EXISTS width_px INTEGER")
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_marketing_tracker_column_sheet_id "
            "ON marketing_tracker_column (sheet_id)"
        )
    )

    # 2. service_tier_payment: convert id from BIGINT to UUID and add Supabase columns
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'service_tier_payment'
                      AND column_name = 'id'
                      AND data_type = 'bigint'
                ) THEN
                    ALTER TABLE service_tier_payment ADD COLUMN id_uuid UUID DEFAULT gen_random_uuid() NOT NULL;
                    ALTER TABLE service_tier_payment DROP CONSTRAINT IF EXISTS service_tier_payment_pkey;
                    ALTER TABLE service_tier_payment DROP COLUMN id;
                    ALTER TABLE service_tier_payment RENAME COLUMN id_uuid TO id;
                    ALTER TABLE service_tier_payment ADD PRIMARY KEY (id);
                    DROP SEQUENCE IF EXISTS service_tier_payment_id_seq;
                END IF;
            END $$;
            """
        )
    )
    op.execute(
        sa.text("ALTER TABLE service_tier_payment ADD COLUMN IF NOT EXISTS user_id TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE service_tier_payment ADD COLUMN IF NOT EXISTS from_tier_max INTEGER")
    )
    op.execute(
        sa.text("ALTER TABLE service_tier_payment ADD COLUMN IF NOT EXISTS to_tier_max INTEGER")
    )
    op.execute(
        sa.text("ALTER TABLE service_tier_payment ADD COLUMN IF NOT EXISTS tx_ref TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE service_tier_payment ADD COLUMN IF NOT EXISTS chapa_status TEXT")
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_service_tier_payment_tx_ref "
            "ON service_tier_payment (tx_ref)"
        )
    )

    # 3. users.phone: drop global UNIQUE index so dual-role / duplicate-phone
    # Supabase accounts can be migrated and backfilled without collisions.
    op.execute(sa.text("DROP INDEX IF EXISTS ix_users_phone"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_phone ON users (phone)"))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_users_phone"))
    op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)"))

    op.execute(sa.text("DROP INDEX IF EXISTS ix_service_tier_payment_tx_ref"))
    for col in ("chapa_status", "tx_ref", "to_tier_max", "from_tier_max", "user_id"):
        op.execute(sa.text(f"ALTER TABLE service_tier_payment DROP COLUMN IF EXISTS {col}"))

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'service_tier_payment'
                      AND column_name = 'id'
                      AND data_type = 'uuid'
                ) THEN
                    ALTER TABLE service_tier_payment DROP CONSTRAINT IF EXISTS service_tier_payment_pkey;
                    ALTER TABLE service_tier_payment DROP COLUMN id;
                    ALTER TABLE service_tier_payment ADD COLUMN id BIGSERIAL PRIMARY KEY;
                END IF;
            END $$;
            """
        )
    )

    op.execute(sa.text("DROP INDEX IF EXISTS ix_marketing_tracker_column_sheet_id"))
    op.execute(sa.text("ALTER TABLE marketing_tracker_column DROP COLUMN IF EXISTS width_px"))
    op.execute(sa.text("ALTER TABLE marketing_tracker_column DROP COLUMN IF EXISTS sheet_id"))
