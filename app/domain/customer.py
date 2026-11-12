"""Domain models for customers, statistics, and customer job requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass
class CustomerDomain:
    id: UUID
    first_name: str
    last_name: str
    phone: str
    user_id: UUID | None = None
    email: str | None = None
    country_code: str | None = "+251"
    user_name: str | None = None
    profile_pic: str | None = None
    fcm_token: str | None = None
    login_type: str | None = None
    wallet_amount: Decimal | float | None = 0.0
    active: bool | None = True
    slug: str | None = None
    address: Any | None = None
    default_address: Any | None = None
    customer_addresses: Any | None = None
    signup_source: str | None = "admin"
    admin_note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) if parts else (self.user_name or "Customer")


@dataclass
class CustomerStatsDomain:
    completed_bookings: int = 0
    active_bookings: int = 0
    total_spend: float = 0.0
    last_booking_date: datetime | None = None


@dataclass
class CustomerJobRequestItemDomain:
    id: str
    created_at: datetime
    title: str | None = None
    description: str | None = None
    price: str | None = None
    status: str | None = None
    accepted: bool | None = None
    is_paid: bool | None = None

