"""Pydantic schemas for Custom Job Requests and Provider Bidding."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class JobRequestOut(MobileApiSchema):
    id: str
    created_at: datetime = Field(serialization_alias="createdAt")
    accepted: bool | None = None
    status: str | None = None
    is_paid: bool | None = Field(default=None, serialization_alias="isPaid")
    bid_list: list[Any] = Field(default_factory=list, serialization_alias="bidList")
    bid_price: str | None = Field(default=None, serialization_alias="bidPrice")
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")
    provider_id: UUID | None = Field(default=None, serialization_alias="providerId")
    description: str | None = None
    handyman_id: str | None = Field(default=None, serialization_alias="handymanId")
    price: str | None = None
    service_id: UUID | None = Field(default=None, serialization_alias="serviceId")
    title: str | None = None
    service_model_list: list[Any] = Field(default_factory=list, serialization_alias="serviceModelList")
    customer_display_name: str | None = Field(default=None, serialization_alias="customerDisplayName")
    customer_display_phone: str | None = Field(default=None, serialization_alias="customerDisplayPhone")


class JobRequestCreate(MobileApiSchema):
    id: str | None = None
    created_at: datetime | str | None = Field(default=None, alias="createdAt")
    accepted: bool | None = False
    status: str | None = "accepted"
    is_paid: bool | None = Field(default=False, alias="isPaid")
    bid_list: list[Any] = Field(default_factory=list, alias="bidList")
    bid_price: str | None = Field(default="0", alias="bidPrice")
    customer_id: UUID | None = Field(default=None, alias="customerId")
    provider_id: UUID | None = Field(default=None, alias="providerId")
    description: str | None = None
    handyman_id: str | None = Field(default=None, alias="handymanId")
    price: str | None = None
    service_id: UUID | None = Field(default=None, alias="serviceId")
    title: str | None = None
    service_model_list: list[Any] = Field(default_factory=list, alias="serviceModelList")


# Backward compatibility aliases
JobCreate = JobRequestCreate


class JobPatch(MobileApiSchema):
    title: str | None = None
    description: str | None = None
    price: str | None = None


class JobBidCreate(MobileApiSchema):
    bid_price: str = Field(alias="bidPrice")
    message: str | None = None
    note: str | None = None


JobBidBody = JobBidCreate
