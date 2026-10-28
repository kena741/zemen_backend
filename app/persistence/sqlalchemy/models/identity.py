from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, Numeric, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base
from app.persistence.sqlalchemy.enums import COMPANY_VERIFICATION_STATUS, PROVIDER_TYPE


class Customer(Base):
    __tablename__ = "customer"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_pic: Mapped[str | None] = mapped_column(Text, nullable=True)
    fcm_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    login_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    wallet_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    default_address: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    customer_addresses: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    signup_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Provider(Base):
    __tablename__ = "provider"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_name: Mapped[str | None] = mapped_column("firstName", Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column("lastName", Text, nullable=True)
    user_name: Mapped[str | None] = mapped_column("userName", Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column("phoneNumber", Text, nullable=True)
    profile_image: Mapped[str | None] = mapped_column("profileImage", Text, nullable=True)
    banner: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str | None] = mapped_column("countryCode", Text, nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_type: Mapped[str | None] = mapped_column("userType", Text, nullable=True)
    wallet_amount: Mapped[str | None] = mapped_column("walletAmount", Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fcm_token: Mapped[str | None] = mapped_column("fcmToken", Text, nullable=True)
    social_links: Mapped[dict] = mapped_column("socialLinks", JSONB, nullable=False, default=dict)
    activation_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activation_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activation_tx_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_type: Mapped[str | None] = mapped_column(PROVIDER_TYPE, nullable=True)
    company_verification_status: Mapped[str | None] = mapped_column(COMPANY_VERIFICATION_STATUS, nullable=True)
    service_tier_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    service_tier_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_subcategory_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(Uuid(as_uuid=True)), nullable=False, default=list
    )
    signup_source: Mapped[str | None] = mapped_column("signupSource", Text, nullable=True)
    profession_id: Mapped[str | None] = mapped_column("professionId", Text, nullable=True)
    category_id: Mapped[str | None] = mapped_column("categoryId", Text, nullable=True)
    company_license_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_tier_tx_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updateAt", DateTime(timezone=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # `password` and `admin_note` stay unmapped (legacy hash / staff-only).


class Handyman(Base):
    __tablename__ = "handyman"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    first_name: Mapped[str | None] = mapped_column("firstName", Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column("lastName", Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column("phoneNumber", Text, nullable=True)
    user_name: Mapped[str | None] = mapped_column("userName", Text, nullable=True)
    profile_image: Mapped[str | None] = mapped_column("profileImage", Text, nullable=True)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_active: Mapped[bool | None] = mapped_column("isActive", Boolean, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column("createdAt", DateTime(timezone=True), nullable=True)
    user_type: Mapped[str | None] = mapped_column("userType", Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_category: Mapped[str | None] = mapped_column("subCategory", Text, nullable=True)
    category_id: Mapped[UUID | None] = mapped_column("categoryId", Uuid(as_uuid=True), nullable=True)
    sub_category_id: Mapped[UUID | None] = mapped_column("subCategoryId", Uuid(as_uuid=True), nullable=True)
    country_code: Mapped[str | None] = mapped_column("countryCode", Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    fcm_token: Mapped[str | None] = mapped_column("fcmToken", Text, nullable=True)
    # `password` (legacy plaintext column) is intentionally not mapped.


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_size: Mapped[str | None] = mapped_column(Text, nullable=True)
    headquarters: Mapped[str | None] = mapped_column(Text, nullable=True)
    founded: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    banner_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
