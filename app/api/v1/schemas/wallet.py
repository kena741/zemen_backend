"""Pydantic schemas for Wallet ledger, balances, payout methods, and withdrawals."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class WalletTransactionOut(MobileApiSchema):
    id: UUID
    amount: str | float | Decimal | None = None
    created_date: datetime | None = Field(default=None, serialization_alias="createdDate")
    is_credit: bool | None = Field(default=None, serialization_alias="isCredit")
    note: str | None = None
    payment_type: str | None = Field(default=None, serialization_alias="paymentType")
    transaction_id: str | None = Field(default=None, serialization_alias="transactionId")
    type: str | None = None
    user_id: UUID | None = Field(default=None, serialization_alias="userId")
    provider_id: UUID | None = Field(default=None, serialization_alias="providerId")
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")


class WithdrawalOut(MobileApiSchema):
    id: UUID
    amount: str | float | Decimal | None = None
    created_date: datetime | None = Field(default=None, serialization_alias="createdDate")
    note: str | None = None
    payment_status: str | None = Field(default=None, serialization_alias="paymentStatus")
    provider_id: UUID | None = Field(default=None, serialization_alias="providerId")
    holder_name: str | None = Field(default=None, serialization_alias="holderName")
    bank_name: str | None = Field(default=None, serialization_alias="bankName")
    account_number: str | None = Field(default=None, serialization_alias="accountNumber")
    rejection_reason: str | None = Field(default=None, serialization_alias="rejectionReason")


class WalletBalanceOut(MobileApiSchema):
    balance: float
    currency: str = "ETB"


class ProviderPaymentMethodOut(MobileApiSchema):
    id: UUID
    provider_id: UUID = Field(serialization_alias="providerId")
    bank_name: str | None = Field(default=None, serialization_alias="bankName")
    account_number: str | None = Field(default=None, serialization_alias="accountNumber")
    holder_name: str | None = Field(default=None, serialization_alias="holderName")
    is_default: bool = Field(default=False, serialization_alias="isDefault")
    is_active: bool = Field(default=True, serialization_alias="isActive")


class ProviderPaymentMethodCreate(MobileApiSchema):
    bank_name: str = Field(alias="bankName")
    account_number: str = Field(alias="accountNumber")
    holder_name: str | None = Field(default=None, alias="holderName")
