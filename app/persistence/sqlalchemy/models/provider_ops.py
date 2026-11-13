"""Provider operational models: availability, blocked dates, customer links, analytics."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base


class ProviderAvailabilityWeekly(Base):
    """Weekly availability schedule for a provider.

    The `user_id` column IS the primary key (one row per provider user).
    `paw_id` is a legacy nullable alias kept for backward compat.
    `weekly` is a JSONB blob keyed by day-of-week with time-slot arrays.
    """

    __tablename__ = "provider_availability_weekly"

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    weekly: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    paw_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class ProviderBlockedDate(Base):
    """Specific calendar dates a provider has marked as unavailable."""

    __tablename__ = "provider_blocked_dates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    blocked_on: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderCustomer(Base):
    """Junction table linking providers to their customers (booking history)."""

    __tablename__ = "provider_customer"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    last_booked_at: Mapped[datetime | None] = mapped_column(
        "lastBookedAt", DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), nullable=False)


class ProviderAnalytics(Base):
    """Analytics snapshot row per provider.

    The table schema only defines `id` and `created_at` — all other metrics
    are expected to be added as the analytics feature evolves.
    """

    __tablename__ = "provider_analytics"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

