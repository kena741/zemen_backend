"""Response schemas for Admin Settings, Languages, Mobile App Config, Coupons, and Nav Action Counts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LanguageResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    code: str | None = None
    name: str | None = None
    active: bool = True


class SettingsDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    app_settings: dict[str, Any] = Field(default_factory=dict, serialization_alias="appSettings")
    general_settings: dict[str, Any] = Field(default_factory=dict, serialization_alias="generalSettings")
    policy_settings: dict[str, Any] = Field(default_factory=dict, serialization_alias="policySettings")
    payment_settings: dict[str, Any] = Field(default_factory=dict, serialization_alias="paymentSettings")
    contact_us: dict[str, Any] = Field(default_factory=dict, serialization_alias="contactUs")
    admin_commission: dict[str, Any] = Field(default_factory=dict, serialization_alias="adminCommission")
    status_options: list[dict[str, Any]] = Field(default_factory=list, serialization_alias="statusOptions")
    constants: dict[str, Any] = Field(default_factory=dict, serialization_alias="constants")
    language_settings: list[LanguageResponseItem] = Field(
        default_factory=list, serialization_alias="languageSettings"
    )
    languages: list[LanguageResponseItem] = Field(default_factory=list)


class SettingsUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    data: dict[str, Any]


class MobileAppConfigResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    app_key: str = Field(serialization_alias="appKey")
    maintenance_mode: bool = Field(serialization_alias="maintenanceMode")
    maintenance_message: str | None = Field(default=None, serialization_alias="maintenanceMessage")
    maintenance_affected_versions: list[dict[str, Any]] | dict[str, Any] = Field(
        default_factory=list, serialization_alias="maintenanceAffectedVersions"
    )
    update_needed: bool = Field(serialization_alias="updateNeeded")
    update_message: str | None = Field(default=None, serialization_alias="updateMessage")
    update_affected_versions: list[dict[str, Any]] | dict[str, Any] = Field(
        default_factory=list, serialization_alias="updateAffectedVersions"
    )
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class MobileAppConfigListResponse(BaseModel):
    data: list[MobileAppConfigResponseItem]


class MobileAppConfigSingleResponse(BaseModel):
    data: MobileAppConfigResponseItem


class NavActionCountsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    counts: dict[str, int]


class CouponResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    title: str | None = None
    code: str | None = None
    amount: Decimal | None = None
    min_amount: Decimal | None = Field(default=None, serialization_alias="minAmount")
    active: bool = True
    is_private: bool = Field(default=False, serialization_alias="isPrivate")
    is_fix: bool = Field(default=True, serialization_alias="isFix")
    expired_at: datetime | None = Field(default=None, serialization_alias="expiredAt")
    created_at: datetime = Field(serialization_alias="createdAt")


class CouponListResponse(BaseModel):
    data: list[CouponResponseItem]


class CouponSingleResponse(BaseModel):
    data: CouponResponseItem

