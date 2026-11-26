"""Relax NOT NULL constraints on columns that are nullable in Supabase.

Revision ID: 0014_relax_nullable_cols
Revises: 0013_fix_uuid_jsonb_types
Create Date: 2026-11-26 11:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_relax_nullable_cols"
down_revision: Union[str, Sequence[str], None] = "0013_fix_uuid_jsonb_types"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    targets = (
        ("wallet_transaction", "amount"),
        ("wallet_transaction", "type"),
        ("notifications", "created_at"),
        ("page_views", "provider_id"),
        ("page_views", "updated_at"),
        ("opportunity_stage_history", "opportunity_id"),
    )
    for table, col in targets:
        op.execute(sa.text(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" DROP NOT NULL'))


def downgrade() -> None:
    pass
