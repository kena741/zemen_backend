from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class ReviewOut(APIModel):
    id: UUID
    comment: str
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")
    date: datetime | None = None
    rating: str | None = None
    service_id: UUID | None = Field(default=None, serialization_alias="serviceId")
    booking_id: UUID | None = Field(default=None, serialization_alias="bookingId")


class ReviewCreate(APIModel):
    comment: str
    rating: str | None = None
    service_id: UUID | None = Field(default=None, alias="serviceId")
    booking_id: UUID | None = Field(default=None, alias="bookingId")
