from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class ChapaVerifyBody(APIModel):
    tx_ref: str = Field(alias="txRef")
    purpose: str
    booking_id: UUID | None = Field(default=None, alias="bookingId")


class PaymentWriteResult(APIModel):
    purpose: str | None = None
    tx_ref: str | None = Field(default=None, serialization_alias="txRef")
    booking_id: str | None = Field(default=None, serialization_alias="bookingId")
    amount: str | None = None
    created: bool | None = None
    status: str | None = None
    id: str | None = None
    reason: str | None = None
    provider_id: str | None = Field(default=None, serialization_alias="providerId")


class WithdrawalCreateBody(APIModel):
    amount: Decimal
    payment_method_id: UUID | None = Field(default=None, alias="paymentMethodId")
    note: str | None = None
