"""Domain models for User and Push Notifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


@dataclass
class NotificationDomain:
    id: UUID
    title: str | None = None
    description: str | None = None
    type: str | None = "general"
    is_read: bool = False
    recipient_role: str = "customer"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read_at: datetime | None = None
    booking_id: UUID | None = None
    action_url: str | None = None
    sender_id: UUID | None = None
    customer_id: UUID | None = None
    provider_id: UUID | None = None
    handyman_id: UUID | None = None

