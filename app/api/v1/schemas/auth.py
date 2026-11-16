"""Pydantic schemas for Mobile Authentication, OTP, and Session responses."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.schemas.base import MobileApiSchema


class CustomerSignupRequest(MobileApiSchema):
    email: str | None = None
    password: str = Field(min_length=6)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    phone: str = Field(min_length=6)
    country_code: str | None = "+251"
    user_name: str | None = None
    address: Any | None = None
    login_type: str = "app"
    fcm_token: str | None = None
    profile_pic: str | None = None


class ProviderSignupRequest(MobileApiSchema):
    email: str | None = None
    password: str = Field(min_length=6)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    phone: str = Field(min_length=6)
    country_code: str | None = "+251"
    user_name: str | None = None
    address: str | None = None
    category_id: str | None = None
    profession_id: str | None = None
    fcm_token: str | None = None
    profile_image: str | None = None


class LoginRequest(MobileApiSchema):
    identifier: str | None = None
    email: str | None = None
    phone: str | None = None
    password: str = Field(min_length=1)

    @model_validator(mode="after")
    def resolve_identifier(self) -> "LoginRequest":
        if not self.identifier:
            self.identifier = self.email or self.phone
        if not self.identifier:
            raise ValueError("Either 'identifier', 'email', or 'phone' must be provided.")
        return self


class SendOtpRequest(MobileApiSchema):
    recipient: str | None = None
    phone: str | None = None
    code_length: int = 6
    ttl: int = 300
    message_prefix: str = "Your verification code is"

    @model_validator(mode="after")
    def resolve_recipient(self) -> "SendOtpRequest":
        if not self.recipient:
            self.recipient = self.phone
        if not self.recipient:
            raise ValueError("Recipient phone number must be provided.")
        return self


class VerifyOtpRequest(MobileApiSchema):
    code: str
    recipient: str | None = None
    phone: str | None = None
    verification_id: str | None = None

    @model_validator(mode="after")
    def resolve_recipient(self) -> "VerifyOtpRequest":
        if not self.recipient:
            self.recipient = self.phone
        if not self.recipient:
            raise ValueError("Recipient phone number must be provided.")
        return self


class PlainSmsRequest(MobileApiSchema):
    recipient: str
    message: str


class PhoneResetPasswordRequest(MobileApiSchema):
    phone: str
    code: str
    new_password: str = Field(min_length=6)
    verification_id: str | None = None


class ChangePasswordRequest(MobileApiSchema):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class CheckPhoneRequest(MobileApiSchema):
    phone: str


# ======================== Response Models ========================


class AuthSessionResponse(MobileApiSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    roles: list[str]
    customer_id: UUID | None = None
    provider_id: UUID | None = None
    handyman_id: UUID | None = None
    user: dict[str, Any] = Field(default_factory=dict)


class AuthMeResponse(MobileApiSchema):
    user_id: UUID
    email: str | None = None
    roles: list[str] = Field(description="Linked roles for this auth user")
    customer_id: UUID | None = None
    provider_id: UUID | None = None
    handyman_id: UUID | None = None


class OtpSendResponse(MobileApiSchema):
    success: bool = True
    verification_id: str
    message: str = "Verification code dispatched successfully."


class OtpVerifyResponse(MobileApiSchema):
    success: bool = True
    message: str = "Verification successful."


class SuccessMessageResponse(MobileApiSchema):
    success: bool = True
    message: str
