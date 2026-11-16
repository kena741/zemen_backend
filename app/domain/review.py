"""Domain models for Customer Reviews."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


@dataclass
class ReviewCustomerDomain:
    id: UUID
    comment: str
    rating: float
    customer_id: UUID | None = None
    service_id: UUID | None = None
    booking_id: UUID | None = None
    date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    customer_name: str | None = None
    customer_image: str | None = None

