"""Pydantic schemas for Custom Service Offers."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class ServiceOfferOut(MobileApiSchema):
    id: UUID
    service_id: str = Field(serialization_alias="serviceId")
    customer_id: str = Field(serialization_alias="customerId")
    provider_id: str = Field(serialization_alias="providerId")
    offered_price: float = Field(serialization_alias="offeredPrice")
    status: str
    message: str | None = None
    booking_id: str | None = Field(default=None, serialization_alias="bookingId")
    expires_at: datetime | None = Field(default=None, serialization_alias="expiresAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    booking_date: datetime | None = Field(default=None, serialization_alias="bookingDate")
    booking_address: dict[str, Any] | None = Field(default=None, serialization_alias="bookingAddress")
    service_description: str | None = Field(default=None, serialization_alias="serviceDescription")
    service_name: str | None = Field(default=None, serialization_alias="serviceName")
    customer_name: str | None = Field(default=None, serialization_alias="customerName")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")


class ServiceOfferCreate(MobileApiSchema):
    service_id: str = Field(alias="serviceId")
    provider_id: str = Field(alias="providerId")
    offered_price: float = Field(alias="offeredPrice")
    message: str | None = None
    booking_date: datetime | str | None = Field(default=None, alias="bookingDate")
    booking_address: dict[str, Any] = Field(alias="bookingAddress")
    service_description: str = Field(alias="serviceDescription")


OfferCreate = ServiceOfferCreate


class AttachOfferBookingBody(MobileApiSchema):
    booking_id: str = Field(alias="bookingId")


AttachBookingBody = AttachOfferBookingBody
