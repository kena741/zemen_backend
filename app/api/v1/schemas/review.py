"""Pydantic schemas for Customer Reviews."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class ReviewOut(MobileApiSchema):
    id: UUID
    comment: str
    rating: float
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")
    service_id: UUID | None = Field(default=None, serialization_alias="serviceId")
    booking_id: UUID | None = Field(default=None, serialization_alias="bookingId")
    date: datetime
    customer_name: str | None = Field(default=None, serialization_alias="customerName")
    customer_image: str | None = Field(default=None, serialization_alias="customerImage")


class ReviewCreate(MobileApiSchema):
    service_id: UUID | None = Field(default=None, alias="serviceId")
    booking_id: UUID | None = Field(default=None, alias="bookingId")
    rating: float
    comment: str
