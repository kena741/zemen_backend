from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, SmallInteger, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base
from app.persistence.sqlalchemy.enums import FEEDBACK_TYPE


class ChatMessage(Base):
    __tablename__ = "chat"

    chat_id: Mapped[str] = mapped_column("chatID", Text, primary_key=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_id: Mapped[str] = mapped_column("senderId", Text, nullable=False, index=True)
    receiver_id: Mapped[str] = mapped_column("receiverId", Text, nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column("mediaUrl", Text, nullable=True)
    seen: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatInbox(Base):
    __tablename__ = "chat_inbox"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    last_message: Mapped[str | None] = mapped_column("lastMessage", Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column("mediaUrl", Text, nullable=True)
    sender_id: Mapped[str] = mapped_column("senderId", Text, nullable=False, index=True)
    receiver_id: Mapped[str] = mapped_column("receiverId", Text, nullable=False, index=True)
    seen: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    booking_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    handyman_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    provider_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    sender_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipient_role: Mapped[str] = mapped_column(Text, nullable=False)


class ReviewCustomer(Base):
    __tablename__ = "review_customer"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column("customerId", Uuid(as_uuid=True), nullable=True)
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rating: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_id: Mapped[UUID | None] = mapped_column("serviceId", Uuid(as_uuid=True), nullable=True, index=True)
    booking_id: Mapped[UUID | None] = mapped_column("bookingId", Uuid(as_uuid=True), nullable=True)


class Notifications(Base):
    """User notifications (plural) - legacy / mobile app notifications table."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    booking_id: Mapped[str | None] = mapped_column("bookingId", Text, nullable=True)
    customer_id: Mapped[UUID | None] = mapped_column("customerId", Uuid(as_uuid=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    handyman_id: Mapped[UUID | None] = mapped_column("handymanId", Uuid(as_uuid=True), nullable=True)
    provider_id: Mapped[UUID | None] = mapped_column("providerId", Uuid(as_uuid=True), nullable=True)
    sender_id: Mapped[UUID | None] = mapped_column("senderId", Uuid(as_uuid=True), nullable=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContactMessage(Base):
    """Contact form submissions."""

    __tablename__ = "contact_messages"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False, default="contact")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Feedback(Base):
    """User submitted feedback."""

    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    type: Mapped[str] = mapped_column(FEEDBACK_TYPE, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    screenshot_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

