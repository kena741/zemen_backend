"""Pydantic schemas for Notifications."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class NotificationOut(MobileApiSchema):
    id: UUID
    title: str | None = None
    description: str | None = None
    type: str | None = "general"
    is_read: bool = Field(default=False, serialization_alias="isRead")
    recipient_role: str = Field(default="customer", serialization_alias="recipientRole")
    created_at: datetime = Field(serialization_alias="createdAt")
    read_at: datetime | None = Field(default=None, serialization_alias="readAt")
    booking_id: UUID | None = Field(default=None, serialization_alias="bookingId")
    action_url: str | None = Field(default=None, serialization_alias="actionUrl")


class UnreadCountOut(MobileApiSchema):
    unread_count: int = Field(serialization_alias="unreadCount")


class NotificationBulkResult(MobileApiSchema):
    count: int


class NotificationIdsBody(MobileApiSchema):
    ids: list[UUID] | None = None


class NotificationCreate(MobileApiSchema):
    id: UUID | None = None
    title: str | None = None
    description: str | None = None
    type: str | None = "general"
    recipient_role: str = Field(default="customer", alias="recipientRole")
    booking_id: UUID | None = Field(default=None, alias="bookingId")
    action_url: str | None = Field(default=None, alias="actionUrl")
    customer_id: UUID | None = Field(default=None, alias="customerId")
    provider_id: UUID | None = Field(default=None, alias="providerId")
    handyman_id: UUID | None = Field(default=None, alias="handymanId")


class PushNotificationSend(MobileApiSchema):
    token: str
    title: str
    body: str
    type: str | None = "general"
    payload: dict[str, str] | None = None
    notification_id: UUID | None = Field(default=None, alias="notificationId")
    booking_id: UUID | None = Field(default=None, alias="bookingId")
    customer_id: UUID | None = Field(default=None, alias="customerId")
    provider_id: UUID | None = Field(default=None, alias="providerId")
    handyman_id: UUID | None = Field(default=None, alias="handymanId")

