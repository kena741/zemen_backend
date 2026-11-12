"""Response schemas for CRM and Customer Job Requests."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobRequestResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    created_at: datetime = Field(serialization_alias="createdAt")
    title: str | None = None
    description: str | None = None
    price: str | None = None
    status: str | None = None
    accepted: bool | None = None
    is_paid: bool | None = Field(default=None, serialization_alias="isPaid")
    customer_id: UUID | None = Field(default=None, serialization_alias="customerId")
    provider_id: UUID | None = Field(default=None, serialization_alias="providerId")
    customer_display_name: str | None = Field(default=None, serialization_alias="customerDisplayName")
    customer_display_phone: str | None = Field(default=None, serialization_alias="customerDisplayPhone")


class JobRequestListResponse(BaseModel):
    data: list[JobRequestResponseItem]


class DeleteJobRequestResponse(BaseModel):
    ok: bool = True
    deleted: int = 1
