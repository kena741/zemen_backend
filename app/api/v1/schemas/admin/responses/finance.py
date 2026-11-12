"""Response schemas for Admin Finance, Payouts, and Taxes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WithdrawalResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    provider_id: UUID | None = Field(default=None, serialization_alias="providerId")
    amount: float
    payment_status: str = Field(serialization_alias="paymentStatus")
    admin_note: str | None = Field(default=None, serialization_alias="adminNote")
    note: str | None = None
    payment_date: str | None = Field(default=None, serialization_alias="paymentDate")
    payment_method_id: str | None = Field(default=None, serialization_alias="paymentMethodId")
    holder_name: str | None = Field(default=None, serialization_alias="holderName")
    bank_name: str | None = Field(default=None, serialization_alias="bankName")
    account_number: str | None = Field(default=None, serialization_alias="accountNumber")
    swift_code: str | None = Field(default=None, serialization_alias="swiftCode")
    rejection_reason: str | None = Field(default=None, serialization_alias="rejectionReason")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")
    provider_phone: str | None = Field(default=None, serialization_alias="providerPhone")
    provider_email: str | None = Field(default=None, serialization_alias="providerEmail")
    created_date: datetime = Field(serialization_alias="createdDate")


class WithdrawalListResponse(BaseModel):
    data: list[WithdrawalResponseItem]


class WithdrawalSingleResponse(BaseModel):
    status: str = "success"
    data: WithdrawalResponseItem


class ProviderPaymentMethodResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    provider_id: UUID = Field(serialization_alias="providerId")
    method_type: str = Field(serialization_alias="methodType")
    method_code: str = Field(serialization_alias="methodCode")
    method_name: str = Field(serialization_alias="methodName")
    holder_name: str | None = Field(default=None, serialization_alias="holderName")
    account_number: str | None = Field(default=None, serialization_alias="accountNumber")
    swift_code: str | None = Field(default=None, serialization_alias="swiftCode")
    bank_name: str | None = Field(default=None, serialization_alias="bankName")
    branch_city: str | None = Field(default=None, serialization_alias="branchCity")
    branch_country: str | None = Field(default=None, serialization_alias="branchCountry")
    is_active: bool = Field(serialization_alias="isActive")
    is_default: bool = Field(serialization_alias="isDefault")
    currency: str = "ETB"


class ProviderPaymentMethodsResponse(BaseModel):
    data: dict[str, ProviderPaymentMethodResponseItem | None]


class ProviderPayoutAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    provider_id: UUID = Field(serialization_alias="providerId")
    current_wallet_balance: float = Field(serialization_alias="currentWalletBalance")
    total_earned: float = Field(serialization_alias="totalEarned")
    total_completed_payouts: float = Field(serialization_alias="totalCompletedPayouts")
    pending_payout_amount: float = Field(serialization_alias="pendingPayoutAmount")
    total_commission_paid: float = Field(serialization_alias="totalCommissionPaid")
    booking_count: int = Field(serialization_alias="bookingCount")
    completed_booking_count: int = Field(serialization_alias="completedBookingCount")


class EnrichedWalletTransactionResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    amount: str | None = None
    is_credit: bool | None = Field(default=None, serialization_alias="isCredit")
    note: str | None = None
    payment_type: str | None = Field(default=None, serialization_alias="paymentType")
    transaction_id: str | None = Field(default=None, serialization_alias="transactionId")
    type: str | None = None
    user_id: UUID | None = Field(default=None, serialization_alias="userId")
    provider_id: UUID | None = Field(default=None, serialization_alias="providerId")
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")
    user_full_name: str | None = Field(default=None, serialization_alias="userFullName")
    user_email: str | None = Field(default=None, serialization_alias="userEmail")
    created_date: datetime | None = Field(default=None, serialization_alias="createdDate")


class WalletTransactionListResponse(BaseModel):
    data: list[EnrichedWalletTransactionResponseItem]


class CountryTaxResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str | None = None
    country: str | None = None
    value: float
    type: str | None = "percentage"
    is_fix: bool = Field(serialization_alias="isFix")
    active: bool
    created_at: datetime = Field(serialization_alias="createdAt")


class CountryTaxListResponse(BaseModel):
    data: list[CountryTaxResponseItem]


class ChapaBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    currency: str = "ETB"
    available_balance: float = Field(default=0.0, serialization_alias="availableBalance")
    ledger_balance: float = Field(default=0.0, serialization_alias="ledgerBalance")
