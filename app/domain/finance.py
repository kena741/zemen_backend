"""Domain models for Finance, Withdrawals, Taxes, and Provider Wallet Analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass
class WithdrawalDomain:
    id: UUID
    provider_id: UUID | None
    amount: float
    payment_status: str
    admin_note: str | None = None
    note: str | None = None
    payment_date: str | None = None
    payment_method_id: str | None = None
    holder_name: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    swift_code: str | None = None
    rejection_reason: str | None = None
    provider_name: str | None = None
    provider_phone: str | None = None
    provider_email: str | None = None
    created_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ProviderPaymentMethodDomain:
    id: UUID
    provider_id: UUID
    method_type: str = "bank"
    method_code: str = "cbe"
    method_name: str = "Bank Transfer"
    holder_name: str | None = None
    account_number: str | None = None
    swift_code: str | None = None
    bank_name: str | None = None
    branch_city: str | None = None
    branch_country: str | None = "Ethiopia"
    is_active: bool = True
    is_default: bool = False
    currency: str = "ETB"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ProviderPayoutAnalysisDomain:
    provider_id: UUID
    current_wallet_balance: float
    total_earned: float
    total_completed_payouts: float
    pending_payout_amount: float
    total_commission_paid: float
    booking_count: int
    completed_booking_count: int


@dataclass
class EnrichedWalletTransactionDomain:
    id: UUID
    amount: str | None = None
    is_credit: bool | None = None
    note: str | None = None
    payment_type: str | None = None
    transaction_id: str | None = None
    type: str | None = None
    user_id: UUID | None = None
    provider_id: UUID | None = None
    customer_id: UUID | None = None
    user_full_name: str | None = None
    user_email: str | None = None
    created_date: datetime | None = None


@dataclass
class CountryTaxDomain:
    id: int
    name: str | None
    country: str | None
    value: float
    type: str | None = "percentage"
    is_fix: bool = False
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChapaBalanceDomain:
    currency: str = "ETB"
    available_balance: float = 0.0
    ledger_balance: float = 0.0
