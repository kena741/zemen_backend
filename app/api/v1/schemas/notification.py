from datetime import datetime
from uuid import UUID

from app.api.v1.schemas.common import APIModel


class NotificationOut(APIModel):
    id: UUID
    booking_id: UUID | None = None
    created_at: datetime | None = None
    customer_id: UUID | None = None
    provider_id: UUID | None = None
    handyman_id: UUID | None = None
    sender_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    type: str | None = None
    is_read: bool
    read_at: datetime | None = None
    action_url: str | None = None
    recipient_role: str


class NotificationIdsBody(APIModel):
    ids: list[UUID] | None = None


class NotificationBulkResult(APIModel):
    count: int
