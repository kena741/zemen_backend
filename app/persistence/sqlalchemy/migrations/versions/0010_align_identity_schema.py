"""Align customer, provider, and companies schema with ORM models.

Revision ID: 0010_align_identity_schema
Revises: 0009_telegram_invite_tracking
Create Date: 2026-11-18 15:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0010_align_identity_schema"
down_revision: Union[str, Sequence[str], None] = "0009_telegram_invite_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Customer table adjustments
    customer_cols = [
        ("phone", sa.Text(), True, None),
        ("profile_pic", sa.Text(), True, None),
        ("user_name", sa.Text(), True, None),
        ("login_type", sa.Text(), True, None),
        ("wallet_amount", sa.Numeric(), True, sa.text("0.0")),
        ("default_address", postgresql.JSONB(astext_type=sa.Text()), True, None),
        ("customer_addresses", postgresql.JSONB(astext_type=sa.Text()), True, None),
        ("signup_source", sa.Text(), True, None),
        ("admin_note", sa.Text(), True, None),
        ("updated_at", sa.DateTime(timezone=True), True, sa.text("now()")),
        ("archived_at", sa.DateTime(timezone=True), True, None),
    ]
    for col_name, col_type, nullable, default in customer_cols:
        op.execute(
            sa.text(
                f"ALTER TABLE customer ADD COLUMN IF NOT EXISTS {col_name} "
                f"{col_type.compile(dialect=op.get_bind().dialect)}"
                + (f" DEFAULT {default.text}" if default is not None else "")
            )
        )

    # 2. Provider table adjustments
    provider_cols = [
        ('"firstName"', sa.Text(), True, None),
        ('"lastName"', sa.Text(), True, None),
        ('"userName"', sa.Text(), True, None),
        ('"phoneNumber"', sa.Text(), True, None),
        ('"profileImage"', sa.Text(), True, None),
        ('"countryCode"', sa.Text(), True, None),
        ('"userType"', sa.Text(), True, None),
        ('"fcmToken"', sa.Text(), True, None),
        ('"socialLinks"', postgresql.JSONB(astext_type=sa.Text()), True, sa.text("'{}'::jsonb")),
        ('"signupSource"', sa.Text(), True, None),
        ('"professionId"', sa.Text(), True, None),
        ('"categoryId"', sa.Text(), True, None),
        ('"walletAmount"', sa.Text(), True, sa.text("'0'")),
        ('"createdAt"', sa.DateTime(timezone=True), True, sa.text("now()")),
        ('"updateAt"', sa.DateTime(timezone=True), True, sa.text("now()")),
        ("banner", sa.Text(), True, None),
        ("country", sa.Text(), True, None),
        ("currency", sa.Text(), True, sa.text("'ETB'")),
        ("location", postgresql.JSONB(astext_type=sa.Text()), True, None),
        ("wallet_amount", sa.Text(), True, sa.text("'0'")),
        ("social_links", postgresql.JSONB(astext_type=sa.Text()), True, sa.text("'{}'::jsonb")),
        ("activation_paid", sa.Boolean(), True, sa.text("false")),
        ("activation_paid_at", sa.DateTime(timezone=True), True, None),
        ("activation_tx_ref", sa.Text(), True, None),
        ("service_tier_max", sa.Integer(), True, sa.text("0")),
        ("service_tier_paid_at", sa.DateTime(timezone=True), True, None),
        ("verified_subcategory_ids", postgresql.ARRAY(sa.Uuid(as_uuid=True)), True, sa.text("'{}'::uuid[]")),
        ("signup_source", sa.Text(), True, None),
        ("profession_id", sa.Text(), True, None),
        ("company_license_url", sa.Text(), True, None),
        ("company_rejection_reason", sa.Text(), True, None),
        ("company_verification_status", postgresql.ENUM("not_submitted", "pending", "approved", "rejected", name="company_verification_status", create_type=False), True, sa.text("'not_submitted'")),
        ("service_tier_tx_ref", sa.Text(), True, None),
        ("admin_note", sa.Text(), True, None),
        ("updated_at", sa.DateTime(timezone=True), True, sa.text("now()")),
        ("archived_at", sa.DateTime(timezone=True), True, None),
    ]
    for col_name, col_type, nullable, default in provider_cols:
        op.execute(
            sa.text(
                f"ALTER TABLE provider ADD COLUMN IF NOT EXISTS {col_name} "
                f"{col_type.compile(dialect=op.get_bind().dialect)}"
                + (f" DEFAULT {default.text}" if default is not None else "")
            )
        )

    # 3. Companies table adjustments
    companies_cols = [
        ("provider_id", sa.Uuid(as_uuid=True), True, None),
        ("company_name", sa.Text(), True, None),
        ("industry", sa.Text(), True, None),
        ("company_size", sa.Text(), True, None),
        ("headquarters", sa.Text(), True, None),
        ("founded", sa.Text(), True, None),
        ("profile_bio", sa.Text(), True, None),
        ("banner_image", sa.Text(), True, None),
    ]
    for col_name, col_type, nullable, default in companies_cols:
        op.execute(
            sa.text(
                f"ALTER TABLE companies ADD COLUMN IF NOT EXISTS {col_name} "
                f"{col_type.compile(dialect=op.get_bind().dialect)}"
                + (f" DEFAULT {default.text}" if default is not None else "")
            )
        )


def downgrade() -> None:
    pass
