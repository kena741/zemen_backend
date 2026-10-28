from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class BannerOut(APIModel):
    id: int
    banner_name: str | None = Field(default=None, serialization_alias="bannerName")
    image: str | None = None
    link: str | None = None
    active: bool


class CountryTaxOut(APIModel):
    id: int
    active: bool | None = None
    country: str | None = None
    is_fix: bool | None = Field(default=None, serialization_alias="isFix")
    name: str | None = None
    value: Decimal | None = None
    type: str | None = None


class CouponOut(APIModel):
    id: int
    active: bool | None = None
    amount: Decimal | None = None
    code: str | None = None
    expired_at: datetime | None = Field(default=None, serialization_alias="expiredAt")
    is_private: bool | None = Field(default=None, serialization_alias="isPrivate")
    is_fix: bool | None = Field(default=None, serialization_alias="isFix")
    title: str | None = None
    min_amount: Decimal | None = Field(default=None, serialization_alias="minAmount")


class CurrencyOut(APIModel):
    id: int
    active: bool
    name: str | None = None
    symbol: str | None = None
    decimal_digits: str | None = Field(default=None, serialization_alias="decimalDigits")
    symbol_at_right: bool | None = Field(default=None, serialization_alias="symbolAtRight")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")


class LanguageOut(APIModel):
    id: UUID
    active: bool | None = None
    code: str | None = None
    name: str | None = None


class AppSettingOut(APIModel):
    id: str
    data: dict
    updated_at: datetime | None = None


class MobileAppConfigOut(APIModel):
    app_key: str
    maintenance_mode: bool
    maintenance_message: str | None = None
    maintenance_affected_versions: list | dict
    update_needed: bool
    update_message: str | None = None
    update_affected_versions: list | dict
