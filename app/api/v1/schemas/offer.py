from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class ServiceOfferOut(APIModel):
    id: UUID
    service_id: str
    customer_id: str
    provider_id: str
    offered_price: Decimal
    message: str | None = None
    status: str
    booking_id: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    booking_date: datetime | None = None
    booking_address: dict | None = None
    service_description: str | None = None


class OfferCreate(APIModel):
    service_id: UUID = Field(alias="serviceId")
    provider_id: UUID | None = Field(default=None, alias="providerId")
    offered_price: Decimal = Field(alias="offeredPrice")
    message: str | None = None
    booking_date: datetime | None = Field(default=None, alias="bookingDate")
    booking_address: dict[str, Any] | None = Field(default=None, alias="bookingAddress")
    service_description: str | None = Field(default=None, alias="serviceDescription")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")


class AttachBookingBody(APIModel):
    booking_id: str = Field(alias="bookingId")
