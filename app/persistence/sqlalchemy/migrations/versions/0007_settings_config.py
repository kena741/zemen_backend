"""Platform settings, system configuration, coupons, taxes, and currencies.

Revision ID: 0007_settings_config
Revises: 0006_content_marketing
Create Date: 2026-11-12 13:20:30.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_settings_config"
down_revision: Union[str, Sequence[str], None] = "0006_content_marketing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. app_settings
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. banner
    op.create_table(
        "banner",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("banner_name", sa.Text(), nullable=True),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. country_tax
    op.create_table(
        "country_tax",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("isFix", sa.Boolean(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. coupon
    op.create_table(
        "coupon",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("expiredAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("isPrivate", sa.Boolean(), nullable=True),
        sa.Column("isFix", sa.Boolean(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("minAmount", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. currencies
    op.create_table(
        "currencies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decimalDigits", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("symbolAtRight", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. languages
    op.create_table(
        "languages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 7. mobile_app_config
    op.create_table(
        "mobile_app_config",
        sa.Column("app_key", sa.Text(), nullable=False),
        sa.Column("maintenance_mode", sa.Boolean(), nullable=False),
        sa.Column("maintenance_message", sa.Text(), nullable=True),
        sa.Column("maintenance_affected_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("update_needed", sa.Boolean(), nullable=False),
        sa.Column("update_message", sa.Text(), nullable=True),
        sa.Column("update_affected_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("app_key"),
    )


def downgrade() -> None:
    op.drop_table("mobile_app_config")
    op.drop_table("languages")
    op.drop_table("currencies")
    op.drop_table("coupon")
    op.drop_table("country_tax")
    op.drop_table("banner")
    op.drop_table("app_settings")
