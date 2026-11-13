"""Finance, payments, wallet transactions, and withdrawals.

Revision ID: 0005_finance_payouts
Revises: 0004_bookings_operations
Create Date: 2026-11-12 13:20:20.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_finance_payouts"
down_revision: Union[str, Sequence[str], None] = "0004_bookings_operations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. payments
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("payment_type", sa.Text(), nullable=True),
        sa.Column("payment_status", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_charge_payment_status", sa.Text(), nullable=True),
        sa.Column("extra_charge_payment_type", sa.Text(), nullable=True),
        sa.Column("extra_charge_amount", sa.Numeric(), nullable=True),
        sa.Column("tax_amount", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payments_customer_id"), "payments", ["customer_id"], unique=False)

    # 2. wallet_transaction
    op.create_table(
        "wallet_transaction",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wallet_transaction_customer_id"), "wallet_transaction", ["customer_id"], unique=False)
    op.create_index(op.f("ix_wallet_transaction_provider_id"), "wallet_transaction", ["provider_id"], unique=False)

    # 3. withdrawal_history
    op.create_table(
        "withdrawal_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("providerId", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("paymentStatus", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_payment_method_id", sa.Uuid(), nullable=True),
        sa.Column("bank_id", sa.Uuid(), nullable=True),
        sa.Column("bank_name", sa.Text(), nullable=True),
        sa.Column("account_number", sa.Text(), nullable=True),
        sa.Column("account_holder_name", sa.Text(), nullable=True),
        sa.Column("chapa_reference", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_withdrawal_history_providerId"), "withdrawal_history", ["providerId"], unique=False)

    # 4. provider_payment_methods
    op.create_table(
        "provider_payment_methods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("providerID", sa.Uuid(), nullable=False),
        sa.Column("bankID", sa.Uuid(), nullable=False),
        sa.Column("accountNumber", sa.Text(), nullable=False),
        sa.Column("accountHolderName", sa.Text(), nullable=False),
        sa.Column("isDefault", sa.Boolean(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bankCode", sa.Text(), nullable=True),
        sa.Column("bankName", sa.Text(), nullable=True),
        sa.Column("chapaRecipientId", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provider_payment_methods_providerID"), "provider_payment_methods", ["providerID"], unique=False)

    # 5. service_tier_payment
    op.create_table(
        "service_tier_payment",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("tier_id", sa.BigInteger(), nullable=True),
        sa.Column("tier_name", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("payment_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("commission_percent", sa.Numeric(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration", sa.Text(), nullable=True),
        sa.Column("is_subscribed", sa.Boolean(), nullable=False),
        sa.Column("plan_type", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("service_limit", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 7. bank_details
    op.create_table(
        "bank_details",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("bank_name", sa.Text(), nullable=False),
        sa.Column("account_number", sa.Text(), nullable=False),
        sa.Column("account_holder_name", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("bank_details")
    op.drop_table("subscriptions")
    op.drop_table("service_tier_payment")
    op.drop_index(op.f("ix_provider_payment_methods_providerID"), table_name="provider_payment_methods")
    op.drop_table("provider_payment_methods")
    op.drop_index(op.f("ix_withdrawal_history_providerId"), table_name="withdrawal_history")
    op.drop_table("withdrawal_history")
    op.drop_index(op.f("ix_wallet_transaction_provider_id"), table_name="wallet_transaction")
    op.drop_index(op.f("ix_wallet_transaction_customer_id"), table_name="wallet_transaction")
    op.drop_table("wallet_transaction")
    op.drop_index(op.f("ix_payments_customer_id"), table_name="payments")
    op.drop_table("payments")
