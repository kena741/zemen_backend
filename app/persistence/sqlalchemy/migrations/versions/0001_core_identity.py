"""Core identity and authentication migration.

Revision ID: 0001_core_identity
Revises: None
Create Date: 2026-11-12 13:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_core_identity"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # 2. Postgres ENUM types
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE provider_type AS ENUM ('individual', 'company');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE company_verification_status AS ENUM (
            'not_submitted', 'pending', 'approved', 'rejected'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    # 3. users
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("hashed_password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False),
        sa.Column("email_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phone_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sign_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)

    # 4. user_refresh_tokens
    op.create_table(
        "user_refresh_tokens",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_refresh_tokens_token_hash"), "user_refresh_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_user_refresh_tokens_user_id"), "user_refresh_tokens", ["user_id"], unique=False)

    # 5. companies
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("legal_name", sa.Text(), nullable=True),
        sa.Column("trade_name", sa.Text(), nullable=True),
        sa.Column("tax_id", sa.Text(), nullable=True),
        sa.Column("business_registration_number", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("verification_status", postgresql.ENUM("not_submitted", "pending", "approved", "rejected", name="company_verification_status", create_type=False), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. customer
    op.create_table(
        "customer",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone_number", sa.Text(), nullable=True),
        sa.Column("profile_image", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_type", sa.Text(), nullable=True),
        sa.Column("country_code", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Text(), nullable=True),
        sa.Column("longitude", sa.Text(), nullable=True),
        sa.Column("fcm_token", sa.Text(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("total_bookings", sa.Integer(), nullable=True),
        sa.Column("last_booking_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=True),
        sa.Column("review_sum", sa.Numeric(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("contact_persons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customer_user_id"), "customer", ["user_id"], unique=False)

    # 7. provider
    op.create_table(
        "provider",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("provider_type", postgresql.ENUM("individual", "company", name="provider_type", create_type=False), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone_number", sa.Text(), nullable=True),
        sa.Column("user_name", sa.Text(), nullable=True),
        sa.Column("profile_image", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_type", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("sub_category", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("sub_category_id", sa.Uuid(), nullable=True),
        sa.Column("country_code", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("fcm_token", sa.Text(), nullable=True),
        sa.Column("service_address", sa.Text(), nullable=True),
        sa.Column("service_availability", sa.Text(), nullable=True),
        sa.Column("experience_interval", sa.Text(), nullable=True),
        sa.Column("experience_duration", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=True),
        sa.Column("review_sum", sa.Numeric(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("is_served", sa.Boolean(), nullable=True),
        sa.Column("served_category", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("served_sub_category", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=True),
        sa.Column("review_status", sa.Text(), nullable=True),
        sa.Column("is_email_verified", sa.Boolean(), nullable=True),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("contact_persons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provider_user_id"), "provider", ["user_id"], unique=False)

    # 8. handyman
    op.create_table(
        "handyman",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("firstName", sa.Text(), nullable=True),
        sa.Column("lastName", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phoneNumber", sa.Text(), nullable=True),
        sa.Column("userName", sa.Text(), nullable=True),
        sa.Column("profileImage", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("isActive", sa.Boolean(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("userType", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("subCategory", sa.Text(), nullable=True),
        sa.Column("categoryId", sa.Uuid(), nullable=True),
        sa.Column("subCategoryId", sa.Uuid(), nullable=True),
        sa.Column("countryCode", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("fcmToken", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_handyman_provider_id"), "handyman", ["provider_id"], unique=False)
    op.create_index(op.f("ix_handyman_user_id"), "handyman", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_handyman_user_id"), table_name="handyman")
    op.drop_index(op.f("ix_handyman_provider_id"), table_name="handyman")
    op.drop_table("handyman")
    op.drop_index(op.f("ix_provider_user_id"), table_name="provider")
    op.drop_table("provider")
    op.drop_index(op.f("ix_customer_user_id"), table_name="customer")
    op.drop_table("customer")
    op.drop_table("companies")
    op.drop_index(op.f("ix_user_refresh_tokens_user_id"), table_name="user_refresh_tokens")
    op.drop_index(op.f("ix_user_refresh_tokens_token_hash"), table_name="user_refresh_tokens")
    op.drop_table("user_refresh_tokens")
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS company_verification_status CASCADE")
    op.execute("DROP TYPE IF EXISTS provider_type CASCADE")
