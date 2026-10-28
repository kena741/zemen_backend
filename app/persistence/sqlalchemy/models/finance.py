from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Numeric, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base
from app.persistence.sqlalchemy.enums import PAYMENT_STATUS


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    booking_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(PAYMENT_STATUS, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WalletTransaction(Base):
    __tablename__ = "wallet_transaction"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    amount: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_date: Mapped[datetime | None] = mapped_column("createdDate", DateTime(timezone=True), nullable=True)
    is_credit: Mapped[bool | None] = mapped_column("isCredit", Boolean, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_type: Mapped[str | None] = mapped_column("paymentType", Text, nullable=True)
    transaction_id: Mapped[str | None] = mapped_column("transactionId", Text, nullable=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[UUID | None] = mapped_column("userId", Uuid(as_uuid=True), nullable=True)
    provider_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    customer_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)


class WithdrawalHistory(Base):
    __tablename__ = "withdrawal_history"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    admin_note: Mapped[str | None] = mapped_column("adminNote", Text, nullable=True)
    amount: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_date: Mapped[datetime | None] = mapped_column("createdDate", DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_date: Mapped[str | None] = mapped_column("paymentDate", Text, nullable=True)
    payment_status: Mapped[str | None] = mapped_column("paymentStatus", Text, nullable=True)
    provider_id: Mapped[UUID | None] = mapped_column("providerId", Uuid(as_uuid=True), nullable=True, index=True)
    payment_method_id: Mapped[str | None] = mapped_column("paymentMethodId", Text, nullable=True)
    holder_name: Mapped[str | None] = mapped_column("holderName", Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column("bankName", Text, nullable=True)
    account_number: Mapped[str | None] = mapped_column("accountNumber", Text, nullable=True)
    swift_code: Mapped[str | None] = mapped_column("swiftCode", Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column("rejectionReason", Text, nullable=True)


class ProviderPaymentMethod(Base):
    __tablename__ = "provider_payment_methods"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider_id: Mapped[UUID] = mapped_column("providerID", Uuid(as_uuid=True), nullable=False, index=True)
    method_type: Mapped[str] = mapped_column(Text, nullable=False, default="bank")
    method_code: Mapped[str] = mapped_column(Text, nullable=False)
    method_name: Mapped[str] = mapped_column(Text, nullable=False)
    holder_name: Mapped[str | None] = mapped_column("holderName", Text, nullable=True)
    account_number: Mapped[str | None] = mapped_column("accountNumber", Text, nullable=True)
    swift_code: Mapped[str | None] = mapped_column("swiftCode", Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column("bankName", Text, nullable=True)
    branch_city: Mapped[str | None] = mapped_column("branchCity", Text, nullable=True)
    branch_country: Mapped[str | None] = mapped_column("branchCountry", Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="ETB")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
