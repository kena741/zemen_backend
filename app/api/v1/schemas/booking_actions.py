from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema
from app.api.v1.schemas.enums import BookingStatus


class RejectBookingBody(MobileApiSchema):
    reason: str | None = None


class AssignHandymanBody(MobileApiSchema):
    handyman_id: UUID = Field(alias="handymanId")


class SetBookingStatusBody(MobileApiSchema):
    status: BookingStatus
    reason: str | None = None
    otp: str | None = None


class CancelBookingBody(MobileApiSchema):
    reason: str | None = None
