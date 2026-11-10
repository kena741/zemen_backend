"""CRM models: opportunities, stage history, and activities."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base
from app.persistence.sqlalchemy.enums import FUNNEL_STAGE


class Opportunity(Base):
    """A sales/CRM opportunity linked to a customer and provider."""

    __tablename__ = "opportunities"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    customer_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    company_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    provider_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(FUNNEL_STAGE, nullable=False)
    probability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OpportunityStageHistory(Base):
    """Audit trail of stage transitions for an opportunity."""

    __tablename__ = "opportunity_stage_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    # from_stage / to_stage use the funnel_stage enum.
    # Stored as the enum type; nullable on from_stage for the initial transition.
    from_stage: Mapped[str | None] = mapped_column(FUNNEL_STAGE, nullable=True)
    to_stage: Mapped[str] = mapped_column(FUNNEL_STAGE, nullable=False)
    changed_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Activity(Base):
    """A CRM activity (call, meeting, follow-up) linked to an opportunity."""

    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    opportunity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

