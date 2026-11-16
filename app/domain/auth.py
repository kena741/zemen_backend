"""Internal domain models for Authentication, RBAC, and Mobile Sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class AdminRoleDomain:
    """Domain model representing an admin RBAC role."""

    id: UUID
    slug: str
    name: str
    description: str | None
    permissions: list[str]
    is_system: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AdminUserDomain:
    """Domain model representing an admin user account."""

    id: UUID
    user_id: UUID
    email: str | None
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class MobileUserCredentialsDomain:
    """Domain representation of authenticated user credentials."""

    id: UUID
    email: str | None = None
    phone: str | None = None
    hashed_password: str | None = None
    is_active: bool = True
    email_confirmed_at: datetime | None = None
    phone_confirmed_at: datetime | None = None


@dataclass
class AuthSessionDomain:
    """Domain representation of an active mobile user session with linked profiles."""

    user_id: UUID
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    roles: list[str] = field(default_factory=list)
    customer_id: UUID | None = None
    provider_id: UUID | None = None
    handyman_id: UUID | None = None
    user: dict[str, Any] = field(default_factory=dict)


@dataclass
class CustomerSignupDomain:
    """Domain model carrying incoming customer registration command."""

    email: str | None
    password: str
    first_name: str
    last_name: str
    phone: str
    user_name: str | None = None
    country_code: str | None = "+251"
    address: dict[str, Any] | None = None
    login_type: str = "app"
    fcm_token: str | None = None
    profile_pic: str | None = None
    wallet_amount: Decimal = Decimal("0.0")


@dataclass
class ProviderSignupDomain:
    """Domain model carrying incoming provider registration command."""

    email: str | None
    password: str
    first_name: str
    last_name: str
    phone: str
    user_name: str | None = None
    country_code: str | None = "+251"
    address: str | None = None
    category_id: str | None = None
    profession_id: str | None = None
    fcm_token: str | None = None
    profile_image: str | None = None


@dataclass
class OtpVerificationDomain:
    """Domain model for OTP session tracking."""

    phone: str
    verification_id: str
    code_hash: str
    expires_at: float
    verified: bool = False
