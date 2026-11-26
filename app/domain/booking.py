"""Domain models for Bookings, operational status transitions, and wallet ledgers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


@dataclass
class BookingDetailDomain:
    id: UUID
    provider_id: UUID
    customer_id: UUID | None = None
    service_id: UUID | None = None
    service_name: str | None = None
    customer_name: str = "Customer"
    customer_phone: str = ""
    customer_email: str | None = None
    provider_name: str = "Provider"
    provider_phone: str | None = None
    provider_email: str | None = None
    price: float = 0.0
    total_amount: float = 0.0
    quantity: int = 1
    booking_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payment_completed: bool = False
    payment_status: str = "pending_payment"
    payment_type: str | None = None
    status: str | None = "pending"
    description: str | None = None
    booking_address: dict[str, Any] | None = None
    admin_commission: float | None = None
    admin_note: str | None = None
    is_archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BookingTransitionResultDomain:
    ok: bool
    status: str
    unchanged: bool = False
    provider_payout: float | None = None
    provider_clawback: float | None = None
    customer_refund: float | None = None


@dataclass
class CommissionConfigDomain:
    default_commission_rate: float = 10.0
    min_commission_rate: float = 0.0
    max_commission_rate: float = 100.0


@dataclass
class BookingWalletLedgerItemDomain:
    id: UUID
    user_id: UUID | None = None
    amount: str | None = None
    is_credit: bool | None = None
    note: str | None = None
    type: str | None = None
    payment_type: str | None = None
    created_date: datetime | None = None


@dataclass
class BookingDomain:
    id: UUID
    provider_id: UUID
    first_name: str = ""
    last_name: str = ""
    phone_number: str = ""
    customer_id: UUID | None = None
    service_id: UUID | None = None
    handyman_id: UUID | None = None
    payment_id: UUID | None = None
    provider_user_id: UUID | None = None
    customer_user_id: UUID | None = None
    service_name: str | None = None
    email: str | None = None
    price: float | None = 0.0
    discount: str | None = None
    total_amount: float | None = 0.0
    sub_total: float | None = 0.0
    tax_list: list[Any] | dict[str, Any] = field(default_factory=list)
    quantity: int = 1
    booking_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payment_completed: bool = False
    payment_status: str = "pending_payment"
    payment_type: str | None = None
    status: str | None = "pending"
    reason: str | None = None
    country_code: str | None = None
    is_archived: bool = False
    pre_payment_extra_charge_payment: bool = False
    post_job_payment: bool = False
    provider_myself: bool = False
    description: str | None = None
    service_image: str | None = None
    booking_address: dict[str, Any] | None = None
    service_details: dict[str, Any] | list[Any] | None = None
    service_proof: dict[str, Any] | None = None
    service_proof_updated_at: datetime | None = None
    otp: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    hold_time: list[Any] | None = None
    extra_charge_amount: str | None = None
    extra_charge_gst: bool | None = None
    extra_charge_model: dict[str, Any] | None = None
    post_job: bool | None = False
    coupon: str | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    next_cycle_due: bool = False
    next_cycle_notified_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    customer_name: str | None = None
    provider_name: str | None = None
    handyman_name: str | None = None


@dataclass
class MonthlyEarningsDomain:
    year: int
    month: int
    month_name: str
    total_earnings: float
    completed_bookings_count: int
