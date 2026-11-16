"""Domain models for Custom Service Offers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


@dataclass
class ServiceOfferDomain:
    id: UUID
    service_id: str
    customer_id: str
    provider_id: str
    offered_price: float
    status: str = "pending"
    message: str | None = None
    booking_id: str | None = None
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    booking_date: datetime | None = None
    booking_address: dict[str, Any] | None = None
    service_description: str | None = None
    service_name: str | None = None
    customer_name: str | None = None
    provider_name: str | None = None

