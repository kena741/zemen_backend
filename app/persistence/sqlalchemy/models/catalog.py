from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, Integer, Numeric, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base
from app.persistence.sqlalchemy.enums import FEATURE_REQUEST_STATUS


class Category(Base):
    __tablename__ = "category"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    category_name: Mapped[str] = mapped_column("categoryName", Text, nullable=False)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class SubCategory(Base):
    __tablename__ = "sub_category"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    sub_category_name: Mapped[str] = mapped_column("subCategoryName", Text, nullable=False)
    category_id: Mapped[UUID] = mapped_column("categoryId", Uuid(as_uuid=True), nullable=False, index=True)
    is_free: Mapped[bool] = mapped_column("isFree", Boolean, nullable=False, default=False)


class Service(Base):
    __tablename__ = "service"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    service_name: Mapped[str] = mapped_column("serviceName", Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[UUID] = mapped_column("categoryId", Uuid(as_uuid=True), nullable=False)
    category_model: Mapped[dict] = mapped_column("categoryModel", JSONB, nullable=False)
    sub_category_id: Mapped[UUID] = mapped_column("subCategoryId", Uuid(as_uuid=True), nullable=False)
    sub_category_model: Mapped[dict] = mapped_column("subCategoryModel", JSONB, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    service_location_mode: Mapped[str] = mapped_column("serviceLocationMode", Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    discount: Mapped[str | None] = mapped_column(Text, nullable=True)
    pre_payment: Mapped[bool] = mapped_column("prePayment", Boolean, nullable=False, default=False)
    feature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_image: Mapped[list[str]] = mapped_column("serviceImage", ARRAY(Text), nullable=False)
    liked_user: Mapped[list[str] | None] = mapped_column("likedUser", ARRAY(Text), nullable=True)
    review_count: Mapped[int | None] = mapped_column("reviewCount", Integer, nullable=True)
    review_sum: Mapped[Decimal | None] = mapped_column("reviewSum", Numeric, nullable=True)
    location: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), nullable=False)
    is_archived: Mapped[bool | None] = mapped_column("isArchived", Boolean, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allows_custom_offer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pricing_type: Mapped[str] = mapped_column(Text, nullable=False)
    billing_interval: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_interval_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pre_payment_percent: Mapped[Decimal | None] = mapped_column("prePaymentPercent", Numeric, nullable=True)
    video: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feature_requested_status: Mapped[str | None] = mapped_column(
        FEATURE_REQUEST_STATUS,
        nullable=True,
        default="none",
    )
    position: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    liked_users: Mapped[list[UUID] | None] = mapped_column(ARRAY(Uuid(as_uuid=True)), nullable=True)


class CustomersService(Base):
    __tablename__ = "customers_service"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    customer_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomerServiceDetail(Base):
    __tablename__ = "customer_service_details"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    customer_service_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    service_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    service_images: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    category_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    category_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_model_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_category_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_category_model: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column("create_at", DateTime(timezone=True), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    discount: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    liked_user: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    location_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_geohash: Mapped[str | None] = mapped_column(Text, nullable=True)
    position_geopoint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pre_payment: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    provider_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_count: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_sum: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
