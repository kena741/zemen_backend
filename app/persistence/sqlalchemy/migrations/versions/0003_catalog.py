"""Service catalog, categories, and customer service details.

Revision ID: 0003_catalog
Revises: 0002_admin_rbac_documents
Create Date: 2026-11-12 13:20:10.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_catalog"
down_revision: Union[str, Sequence[str], None] = "0002_admin_rbac_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Postgres ENUM types
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE feature_request_status_enum AS ENUM (
            'none', 'pending', 'rejected', 'accepted'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    # 2. category
    op.create_table(
        "category",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. sub_category
    op.create_table(
        "sub_category",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("categoryId", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sub_category_categoryId"), "sub_category", ["categoryId"], unique=False)

    # 4. service
    op.create_table(
        "service",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("serviceName", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("categoryId", sa.Uuid(), nullable=False),
        sa.Column("categoryModel", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("subCategoryId", sa.Uuid(), nullable=False),
        sa.Column("subCategoryModel", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("serviceLocationMode", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("discount", sa.Text(), nullable=True),
        sa.Column("prePayment", sa.Boolean(), nullable=False),
        sa.Column("feature", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("serviceImage", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("likedUser", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("reviewCount", sa.Integer(), nullable=True),
        sa.Column("reviewSum", sa.Numeric(), nullable=True),
        sa.Column("location", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("duration", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("isArchived", sa.Boolean(), nullable=True),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("allows_custom_offer", sa.Boolean(), nullable=False),
        sa.Column("pricing_type", sa.Text(), nullable=False),
        sa.Column("billing_interval", sa.Text(), nullable=True),
        sa.Column("billing_interval_count", sa.Integer(), nullable=True),
        sa.Column("prePaymentPercent", sa.Numeric(), nullable=True),
        sa.Column("video", sa.Text(), nullable=True),
        sa.Column("feature_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feature_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feature_requested_status", postgresql.ENUM("none", "pending", "rejected", "accepted", name="feature_request_status_enum", create_type=False), nullable=True),
        sa.Column("feature_rejection_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_service_provider_id"), "service", ["provider_id"], unique=False)

    # 5. customers_service
    op.create_table(
        "customers_service",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_services", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customers_service_customer_id"), "customers_service", ["customer_id"], unique=False)

    # 6. customer_service_details
    op.create_table(
        "customer_service_details",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_service_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("service_name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("service_location_mode", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(), nullable=True),
        sa.Column("discount", sa.Text(), nullable=True),
        sa.Column("pre_payment", sa.Boolean(), nullable=True),
        sa.Column("feature", sa.Boolean(), nullable=True),
        sa.Column("status", sa.Boolean(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("service_image", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("liked_user", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("review_sum", sa.Numeric(), nullable=True),
        sa.Column("location", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("duration", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("sub_category_id", sa.Uuid(), nullable=True),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("category_title", sa.Text(), nullable=True),
        sa.Column("sub_category_title", sa.Text(), nullable=True),
        sa.Column("provider_name", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customer_service_details_customer_service_id"), "customer_service_details", ["customer_service_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_customer_service_details_customer_service_id"), table_name="customer_service_details")
    op.drop_table("customer_service_details")
    op.drop_index(op.f("ix_customers_service_customer_id"), table_name="customers_service")
    op.drop_table("customers_service")
    op.drop_index(op.f("ix_service_provider_id"), table_name="service")
    op.drop_table("service")
    op.drop_index(op.f("ix_sub_category_categoryId"), table_name="sub_category")
    op.drop_table("sub_category")
    op.drop_table("category")
    op.execute("DROP TYPE IF EXISTS feature_request_status_enum CASCADE")
