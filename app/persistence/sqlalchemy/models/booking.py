from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, Numeric, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base
from app.persistence.sqlalchemy.enums import BOOKING_STATUS, FEATURE_REQUEST_STATUS, PAYMENT_STATUS


class BookedService(Base):
    """Canonical booking row — table name `booked_service`."""

    __tablename__ = "booked_service"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    service_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    handyman_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    payment_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    provider_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    customer_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    service_name: Mapped[str | None] = mapped_column("serviceName", Text, nullable=True)
    first_name: Mapped[str] = mapped_column("firstName", Text, nullable=False)
    last_name: Mapped[str] = mapped_column("lastName", Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str] = mapped_column("phoneNumber", Text, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    discount: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column("totalAmount", Numeric, nullable=True)
    sub_total: Mapped[Decimal | None] = mapped_column("subTotal", Numeric, nullable=True)
    tax_list: Mapped[dict | list] = mapped_column("taxList", JSONB, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    booking_date: Mapped[datetime] = mapped_column("bookingDate", DateTime(timezone=True), nullable=False)
    payment_completed: Mapped[bool] = mapped_column("paymentCompleted", Boolean, nullable=False)
    pre_payment_extra_charge_payment: Mapped[bool] = mapped_column(
        "prePaymentExtraChargePayment", Boolean, nullable=False, default=False
    )
    post_job_payment: Mapped[bool] = mapped_column("postJobPayment", Boolean, nullable=False, default=False)
    provider_myself: Mapped[bool] = mapped_column("providerMySelf", Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_image: Mapped[str | None] = mapped_column("serviceImage", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), nullable=False)
    booking_address: Mapped[dict | None] = mapped_column("bookingAddress", JSONB, nullable=True)
    service_details: Mapped[dict | list | None] = mapped_column("serviceDetails", JSONB, nullable=True)
    payment_type: Mapped[str | None] = mapped_column("paymentType", Text, nullable=True)
    payment_status: Mapped[str] = mapped_column(PAYMENT_STATUS, nullable=False)
    status: Mapped[str | None] = mapped_column(BOOKING_STATUS, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str | None] = mapped_column("countryCode", Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_period_start: Mapped[datetime | None] = mapped_column(
        "currentPeriodStart", DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        "currentPeriodEnd", DateTime(timezone=True), nullable=True
    )
    next_cycle_due: Mapped[bool] = mapped_column("nextCycleDue", Boolean, nullable=False, default=False)
    service_proof: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    service_proof_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admin_commission: Mapped[Decimal | None] = mapped_column("adminCommission", Numeric, nullable=True)
    otp: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column("startTime", DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column("endTime", DateTime(timezone=True), nullable=True)
    hold_time: Mapped[list | None] = mapped_column("holdTime", ARRAY(JSONB), nullable=True)
    extra_charge_amount: Mapped[str | None] = mapped_column("extraChargeAmount", Text, nullable=True)
    extra_charge_gst: Mapped[bool | None] = mapped_column("extraChargeGst", Boolean, nullable=True)
    extra_charge_model: Mapped[dict | None] = mapped_column("extraChargeModel", JSONB, nullable=True)
    post_job: Mapped[bool | None] = mapped_column("postJob", Boolean, nullable=True)
    coupon: Mapped[str | None] = mapped_column(Text, nullable=True)
    archive_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_cycle_notified_at: Mapped[datetime | None] = mapped_column(
        "nextCycleNotifiedAt", DateTime(timezone=True), nullable=True
    )


class ServiceOffer(Base):
    __tablename__ = "service_offer"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    # Historical schema stores these as text (not uuid FKs).
    service_id: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False)
    offered_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    booking_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booking_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    booking_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    service_description: Mapped[str | None] = mapped_column(Text, nullable=True)


class JobRequest(Base):
    __tablename__ = "job_request"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), nullable=False)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bid_list: Mapped[list | None] = mapped_column("bidList", ARRAY(JSONB), nullable=True)
    bid_price: Mapped[str | None] = mapped_column("bidPrice", Text, nullable=True)
    customer_id: Mapped[UUID | None] = mapped_column("customerId", Uuid(as_uuid=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    handyman_id: Mapped[str | None] = mapped_column("handymanId", Text, nullable=True)
    price: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_id: Mapped[UUID | None] = mapped_column("providerId", Uuid(as_uuid=True), nullable=True)
    service_id: Mapped[UUID | None] = mapped_column("serviceId", Uuid(as_uuid=True), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(FEATURE_REQUEST_STATUS, nullable=True)
    is_paid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    service_model_list: Mapped[list | None] = mapped_column("serviceModelList", ARRAY(JSONB), nullable=True)
