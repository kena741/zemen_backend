"""Request schemas for Admin Settings, Languages, Mobile App Config, and Coupons."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LanguageSettingItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID | None = None
    code: str
    name: str
    active: bool = True


class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    app_settings: dict[str, Any] | None = Field(default=None, alias="appSettings")
    general_settings: dict[str, Any] | None = Field(default=None, alias="generalSettings")
    policy_settings: dict[str, Any] | None = Field(default=None, alias="policySettings")
    payment_settings: dict[str, Any] | None = Field(default=None, alias="paymentSettings")
    contact_us: dict[str, Any] | None = Field(default=None, alias="contactUs")
    admin_commission: dict[str, Any] | None = Field(default=None, alias="adminCommission")
    status_options: list[dict[str, Any]] | None = Field(default=None, alias="statusOptions")
    constants: dict[str, Any] | None = Field(default=None, alias="constants")
    language_settings: list[LanguageSettingItem] | None = Field(default=None, alias="languageSettings")
    language_deleted_ids: list[UUID] | None = Field(default=None, alias="languageDeletedIds")


class LanguageBulkMutateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    upserts: list[LanguageSettingItem] | None = None
    inserts: list[LanguageSettingItem] | None = None
    delete_ids: list[UUID] | None = Field(default=None, alias="deleteIds")


class MobileAppConfigPatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    app_key: str = Field(alias="appKey")
    maintenance_mode: bool | None = Field(default=None, alias="maintenanceMode")
    maintenance_message: str | None = Field(default=None, alias="maintenanceMessage")
    maintenance_affected_versions: list[dict[str, Any]] | dict[str, Any] | None = Field(
        default=None, alias="maintenanceAffectedVersions"
    )
    update_needed: bool | None = Field(default=None, alias="updateNeeded")
    update_message: str | None = Field(default=None, alias="updateMessage")
    update_affected_versions: list[dict[str, Any]] | dict[str, Any] | None = Field(
        default=None, alias="updateAffectedVersions"
    )


class CouponCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    code: str
    amount: Decimal
    min_amount: Decimal | None = Field(default=None, alias="minAmount")
    active: bool = True
    is_private: bool = Field(default=False, alias="isPrivate")
    is_fix: bool = Field(default=True, alias="isFix")
    expired_at: datetime | None = Field(default=None, alias="expiredAt")


class CouponUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    title: str | None = None
    code: str | None = None
    amount: Decimal | None = None
    min_amount: Decimal | None = Field(default=None, alias="minAmount")
    active: bool | None = None
    is_private: bool | None = Field(default=None, alias="isPrivate")
    is_fix: bool | None = Field(default=None, alias="isFix")
    expired_at: datetime | None = Field(default=None, alias="expiredAt")

