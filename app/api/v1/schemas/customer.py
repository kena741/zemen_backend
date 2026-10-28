from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class CustomerOut(APIModel):
    id: UUID
    user_id: UUID | None = None
    first_name: str
    last_name: str
    phone: str
    email: str | None = None
    country_code: str | None = None
    user_name: str | None = None
    profile_pic: str | None = None
    wallet_amount: Decimal | None = None
    active: bool | None = None
    slug: str | None = None
    default_address: Any | None = None
    customer_addresses: Any | None = None
    created_at: datetime


class CustomerPatch(APIModel):
    """Allowlisted profile fields only — wallet/active/id are ignored server-side."""

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
    slug: str | None = None


class CustomerCreate(CustomerPatch):
    first_name: str
    last_name: str
    phone: str
