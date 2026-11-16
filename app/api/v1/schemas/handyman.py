from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.base import MobileApiSchema


class HandymanOut(MobileApiSchema):
    id: UUID
    provider_id: UUID | None = None
    user_id: UUID | None = None
    first_name: str | None = Field(default=None, serialization_alias="firstName")
    last_name: str | None = Field(default=None, serialization_alias="lastName")
    email: str | None = None
    phone_number: str | None = Field(default=None, serialization_alias="phoneNumber")
    user_name: str | None = Field(default=None, serialization_alias="userName")
    profile_image: str | None = Field(default=None, serialization_alias="profileImage")
    active: bool | None = None
    is_active: bool | None = Field(default=None, serialization_alias="isActive")
    address: str | None = None
    fcm_token: str | None = Field(default=None, serialization_alias="fcmToken")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")


class HandymanCreate(MobileApiSchema):
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    user_name: str | None = Field(default=None, alias="userName")
    email: str | None = None
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    profile_image: str | None = Field(default=None, alias="profileImage")
    address: str | None = None
    active: bool | None = True
    is_active: bool | None = Field(default=True, alias="isActive")
    category_id: UUID | None = Field(default=None, alias="categoryId")
    sub_category_id: UUID | None = Field(default=None, alias="subCategoryId")
    slug: str | None = None


class HandymanPatch(MobileApiSchema):
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    user_name: str | None = Field(default=None, alias="userName")
    email: str | None = None
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    profile_image: str | None = Field(default=None, alias="profileImage")
    address: str | None = None
    active: bool | None = None
    is_active: bool | None = Field(default=None, alias="isActive")
    category_id: UUID | None = Field(default=None, alias="categoryId")
    sub_category_id: UUID | None = Field(default=None, alias="subCategoryId")
    slug: str | None = None