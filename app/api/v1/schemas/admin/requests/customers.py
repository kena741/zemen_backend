"""Request schemas for Admin Customers management."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CreateCustomerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    phone: str
    email: EmailStr | None = None
    country_code: str | None = Field(default="+251", alias="countryCode")
    password: str | None = None


class UpdateCustomerNoteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    admin_note: str | None = Field(default=None, alias="adminNote")


class ArchiveCustomerRequest(BaseModel):
    action: Literal["archive", "restore"]


class SendCustomerPushRequest(BaseModel):
    title: str
    body: str
    route: str | None = None
