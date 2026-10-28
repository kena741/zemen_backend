from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class JobRequestOut(APIModel):
    id: str
    created_at: datetime = Field(serialization_alias="createdAt")
    accepted: bool | None = None
    bid_price: str | None = Field(default=None, serialization_alias="bidPrice")
    bid_list: list | None = Field(default=None, serialization_alias="bidList")
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")
    description: str | None = None
    handyman_id: str | None = Field(default=None, serialization_alias="handymanId")
    price: str | None = None
    provider_id: UUID | None = Field(default=None, serialization_alias="providerId")
    service_id: UUID | None = Field(default=None, serialization_alias="serviceId")
    service_model_list: list | None = Field(default=None, serialization_alias="serviceModelList")
    title: str | None = None
    status: str | None = None
    is_paid: bool | None = None


class JobCreate(APIModel):
    id: str | None = None
    title: str | None = None
    description: str | None = None
    price: str | None = None
    service_id: UUID | None = Field(default=None, alias="serviceId")
    service_model_list: list[Any] | None = Field(default=None, alias="serviceModelList")


class JobPatch(APIModel):
    title: str | None = None
    description: str | None = None
    price: str | None = None
    service_id: UUID | None = Field(default=None, alias="serviceId")
    service_model_list: list[Any] | None = Field(default=None, alias="serviceModelList")
    handyman_id: str | None = Field(default=None, alias="handymanId")


class JobBidBody(APIModel):
    bid_price: str = Field(alias="bidPrice")
    note: str | None = None
