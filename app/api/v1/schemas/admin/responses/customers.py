"""Response schemas for Admin Customers management."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    user_id: UUID | None = Field(default=None, serialization_alias="userId")
    first_name: str = Field(serialization_alias="firstName")
    last_name: str = Field(serialization_alias="lastName")
    phone: str
    email: str | None = None
    country_code: str | None = Field(default="+251", serialization_alias="countryCode")
    user_name: str | None = Field(default=None, serialization_alias="userName")
    profile_pic: str | None = Field(default=None, serialization_alias="profilePic")
    fcm_token: str | None = Field(default=None, serialization_alias="fcmToken")
    wallet_amount: float = Field(default=0.0, serialization_alias="walletAmount")
    active: bool | None = True
    slug: str | None = None
    admin_note: str | None = Field(default=None, serialization_alias="adminNote")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")
    updated_at: datetime | None = Field(default=None, serialization_alias="updatedAt")
    archived_at: datetime | None = Field(default=None, serialization_alias="archivedAt")


class CustomerStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    completed_bookings: int = Field(serialization_alias="completedBookings")
    active_bookings: int = Field(serialization_alias="activeBookings")
    total_spend: float = Field(serialization_alias="totalSpend")
    last_booking_date: datetime | None = Field(default=None, serialization_alias="lastBookingDate")


class CustomerDetailResponse(BaseModel):
    data: CustomerItemResponse
    stats: CustomerStatsResponse


class CustomerListResponse(BaseModel):
    data: list[CustomerItemResponse]


class CustomerCreateResponse(BaseModel):
    data: CustomerItemResponse
    temporary_password: str = Field(serialization_alias="temporaryPassword")
    sms: dict[str, Any]


class CustomerJobRequestItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    created_at: datetime = Field(serialization_alias="createdAt")
    title: str | None = None
    description: str | None = None
    price: str | None = None
    status: str | None = None
    accepted: bool | None = None
    is_paid: bool | None = Field(default=None, serialization_alias="isPaid")


class CustomerJobRequestListResponse(BaseModel):
    data: list[CustomerJobRequestItemResponse]

