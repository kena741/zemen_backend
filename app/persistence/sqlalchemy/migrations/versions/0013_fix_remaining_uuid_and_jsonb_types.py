"""Convert remaining legacy BIGINT id columns to UUID and customer.address to JSONB.

Revision ID: 0013_fix_remaining_uuid_and_jsonb_types
Revises: 0012_align_migration_fields
Create Date: 2026-11-26 11:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_fix_uuid_jsonb_types"
down_revision: Union[str, Sequence[str], None] = "0012_align_migration_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BIGINT_TO_UUID_TABLES = (
    "sub_category_documents",
    "provider_customer",
    "bank_details",
    "wallet_transaction",
    "notifications",
    "page_views",
)


def upgrade() -> None:
    for table in _BIGINT_TO_UUID_TABLES:
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = '{table}'
                          AND column_name = 'id'
                          AND data_type = 'bigint'
                    ) THEN
                        ALTER TABLE "{table}" ADD COLUMN id_uuid UUID DEFAULT gen_random_uuid() NOT NULL;
                        ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{table}_pkey";
                        ALTER TABLE "{table}" DROP COLUMN id;
                        ALTER TABLE "{table}" RENAME COLUMN id_uuid TO id;
                        ALTER TABLE "{table}" ADD PRIMARY KEY (id);
                        DROP SEQUENCE IF EXISTS "{table}_id_seq";
                    END IF;
                END $$;
                """
            )
        )

    # Convert customer.address from text to jsonb (matching Customer ORM model & Supabase)
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'customer'
                      AND column_name = 'address'
                      AND data_type = 'text'
                ) THEN
                    ALTER TABLE customer
                    ALTER COLUMN address TYPE jsonb
                    USING CASE
                        WHEN address IS NULL OR btrim(address) = '' THEN NULL
                        WHEN left(btrim(address), 1) IN ('{', '[', '"') THEN address::jsonb
                        ELSE to_jsonb(address)
                    END;
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    pass
