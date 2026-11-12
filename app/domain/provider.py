"""Domain models for providers, companies, banking, and hire history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass
class ProviderDomain:
    id: UUID
    user_id: UUID
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    user_name: str | None = None
    phone_number: str | None = None
    profile_image: str | None = None
    banner: str | None = None
    address: str | None = None
    country: str | None = None
    country_code: str | None = None
    currency: str | None = None
    location: dict[str, Any] | None = None
    slug: str | None = None
    user_type: str | None = None
    wallet_amount: str | None = "0"
    active: bool = True
    fcm_token: str | None = None
    social_links: dict[str, Any] | list[Any] = field(default_factory=dict)
    activation_paid: bool = False
    activation_paid_at: datetime | None = None
    activation_tx_ref: str | None = None
    provider_type: str | None = "individual"
    company_verification_status: str | None = "not_submitted"
    service_tier_max: int = 0
    service_tier_paid_at: datetime | None = None
    verified_subcategory_ids: list[UUID] = field(default_factory=list)
    signup_source: str | None = "admin"
    profession_id: str | None = None
    category_id: str | None = None
    company_license_url: str | None = None
    company_rejection_reason: str | None = None
    service_tier_tx_ref: str | None = None
    admin_note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) if parts else (self.user_name or "Provider")


@dataclass
class CompanyDomain:
    id: UUID
    provider_id: UUID
    name: str
    website: str | None = None
    company_name: str | None = None
    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    founded: str | None = None
    profile_bio: str | None = None
    banner_image: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class BankMethodDomain:
    id: UUID
    provider_id: UUID
    method_type: str = "bank"
    method_code: str = "cbe"
    method_name: str = "Commercial Bank of Ethiopia"
    holder_name: str | None = None
    account_number: str | None = None
    swift_code: str | None = None
    bank_name: str | None = None
    branch_city: str | None = None
    branch_country: str | None = None
    is_active: bool = True
    is_default: bool = False
    currency: str = "ETB"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ProviderBookingHistoryItemDomain:
    id: UUID
    service_name: str | None
    status: str | None
    payment_status: str
    payment_completed: bool
    amount: Decimal | float
    created_at: datetime
    booking_date: datetime
    customer_id: UUID | None
    customer_name: str
    hired_before: bool = False
    prior_completed_count: int = 0
    is_past_hire: bool = False
    note: str | None = None
    follow_up: str | None = None


@dataclass
class ServiceHistoryStatsDomain:
    total_bookings: int = 0
    completed_bookings: int = 0
    total_earnings: float = 0.0
    repeat_customer_rate: float = 0.0


@dataclass
class RepeatCustomerDomain:
    customer_id: UUID
    customer_name: str
    hire_count: int


@dataclass
class ProviderWalletStatsDomain:
    count: int = 0
    ledger_net: float = 0.0
    stored_wallet_amount: float = 0.0
    ledger_matches_stored: bool = True
