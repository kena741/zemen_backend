"""Bookings, operations, and customer job requests.

Revision ID: 0004_bookings_operations
Revises: 0003_catalog
Create Date: 2026-11-12 13:20:15.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_bookings_operations"
down_revision: Union[str, Sequence[str], None] = "0003_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Postgres ENUM types
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE status AS ENUM (
            'pending', 'accepted', 'rejected', 'on_the_way', 'in_progress',
            'hold', 'completed', 'pending_extra_payment', 'pending_approval', 'admin_paid'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE booked_service_status_enum AS ENUM (
            'booked', 'booked_accepted', 'booked_rejected', 'pending_customer_payment',
            'paid_for_service_booked', 'booked_cancelled', 'service_started',
            'service_completion_approval', 'service_completion_approved_by_customer'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE payment_status_enum AS ENUM (
            'pending_payment', 'payment_approved_by_admin', 'payment_rejected_by_admin',
            'payment_completed', 'payment_cancelled'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    # 2. booked_service
    op.create_table(
        "booked_service",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("handyman_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("provider_user_id", sa.Uuid(), nullable=True),
        sa.Column("customer_user_id", sa.Uuid(), nullable=True),
        sa.Column("serviceName", sa.Text(), nullable=True),
        sa.Column("firstName", sa.Text(), nullable=False),
        sa.Column("lastName", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phoneNumber", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=True),
        sa.Column("discount", sa.Text(), nullable=True),
        sa.Column("totalAmount", sa.Numeric(), nullable=True),
        sa.Column("subTotal", sa.Numeric(), nullable=True),
        sa.Column("taxList", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("bookingDate", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paymentCompleted", sa.Boolean(), nullable=False),
        sa.Column("prePaymentExtraChargePayment", sa.Boolean(), nullable=False),
        sa.Column("postJobPayment", sa.Boolean(), nullable=False),
        sa.Column("providerMySelf", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("serviceImage", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bookingAddress", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("serviceDetails", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("paymentType", sa.Text(), nullable=True),
        sa.Column("payment_status", postgresql.ENUM("pending_payment", "payment_approved_by_admin", "payment_rejected_by_admin", "payment_completed", "payment_cancelled", name="payment_status_enum", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "accepted", "rejected", "on_the_way", "in_progress", "hold", "completed", "pending_extra_payment", "pending_approval", "admin_paid", name="status", create_type=False), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("countryCode", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("currentPeriodStart", sa.DateTime(timezone=True), nullable=True),
        sa.Column("currentPeriodEnd", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nextCycleDue", sa.Boolean(), nullable=False),
        sa.Column("service_proof", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("service_proof_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("adminCommission", sa.Numeric(), nullable=True),
        sa.Column("otp", sa.Text(), nullable=True),
        sa.Column("startTime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("endTime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("holdTime", postgresql.ARRAY(postgresql.JSONB(astext_type=sa.Text())), nullable=True),
        sa.Column("extraChargeAmount", sa.Text(), nullable=True),
        sa.Column("extraChargeGst", sa.Boolean(), nullable=True),
        sa.Column("extraChargeModel", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("postJob", sa.Boolean(), nullable=True),
        sa.Column("coupon", sa.Text(), nullable=True),
        sa.Column("archive_note", sa.Text(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("nextCycleNotifiedAt", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_booked_service_customer_id"), "booked_service", ["customer_id"], unique=False)
    op.create_index(op.f("ix_booked_service_provider_id"), "booked_service", ["provider_id"], unique=False)
    op.create_index(op.f("ix_booked_service_service_id"), "booked_service", ["service_id"], unique=False)

    # 3. job_request
    op.create_table(
        "job_request",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("price", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Text(), nullable=True),
        sa.Column("longitude", sa.Text(), nullable=True),
        sa.Column("service_image", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=True),
        sa.Column("payment_type", sa.Text(), nullable=True),
        sa.Column("service_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sub_total", sa.Numeric(), nullable=True),
        sa.Column("tax_list", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. service_offer
    op.create_table(
        "service_offer",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("offer_price", sa.Numeric(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("booked_service_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("service_offer")
    op.drop_table("job_request")
    op.drop_index(op.f("ix_booked_service_service_id"), table_name="booked_service")
    op.drop_index(op.f("ix_booked_service_provider_id"), table_name="booked_service")
    op.drop_index(op.f("ix_booked_service_customer_id"), table_name="booked_service")
    op.drop_table("booked_service")
    op.execute("DROP TYPE IF EXISTS payment_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS booked_service_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS status CASCADE")
