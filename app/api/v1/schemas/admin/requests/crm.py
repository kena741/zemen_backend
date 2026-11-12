"""Request schemas for CRM and Customer Job Requests."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UpdateJobRequestPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    action: Literal["accept", "reject", "pending"] | None = None
    title: str | None = None
    description: str | None = None
    price: str | None = None


class DeleteJobRequestPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    customer_id: UUID | None = Field(default=None, alias="customerId")
