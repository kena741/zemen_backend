"""Schemas for Customer profiles, requests, and responses."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class CustomerOut(MobileApiSchema):
    id: UUID
    user_id: UUID | None = None
    first_name: str
    last_name: str
    phone: str
    email: str | None = None
    country_code: str | None = None
    user_name: str | None = None
    profile_pic: str | None = None
    fcm_token: str | None = Field(default=None, serialization_alias="fcmToken")
    login_type: str | None = "app"
    wallet_amount: Decimal | float | None = 0.0
    active: bool | None = True
    slug: str | None = None
    address: Any | None = None
    default_address: Any | None = None
    customer_addresses: Any | None = None
    created_at: datetime | None = None


class CustomerPatch(MobileApiSchema):
    """Allowlisted profile fields for update."""

    first_name: str | None = None
    last_name: str | None = None
    user_name: str | None = None
    email: str | None = None
    country_code: str | None = None
    phone: str | None = None
    profile_pic: str | None = None
    fcm_token: str | None = Field(default=None, alias="fcmToken")
    customer_addresses: Any | None = None
    default_address: Any | None = None
    address: Any | None = None
    slug: str | None = None


class CustomerCreate(CustomerPatch):
    first_name: str
    last_name: str
    phone: str


class CheckPhoneRegisteredResponse(MobileApiSchema):
    is_registered: bool = Field(serialization_alias="isRegistered")
    phone: str
