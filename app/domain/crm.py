"""Domain models for CRM and Customer Job Requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


@dataclass
class JobRequestDomain:
    id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    title: str | None = None
    description: str | None = None
    price: str | None = None
    status: str | None = "pending"
    accepted: bool | None = False
    is_paid: bool | None = False
    customer_id: UUID | None = None
    provider_id: UUID | None = None
    customer_display_name: str | None = None
    customer_display_phone: str | None = None
