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
    payment_status: str = "pending"
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
