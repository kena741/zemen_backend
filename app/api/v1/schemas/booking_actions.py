from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class RejectBookingBody(APIModel):
    reason: str | None = None


class AssignHandymanBody(APIModel):
    handyman_id: UUID = Field(alias="handymanId")


class SetBookingStatusBody(APIModel):
    status: str


class CancelBookingBody(APIModel):
    reason: str | None = None
