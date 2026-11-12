"""Domain models for Catalog, Services, Categories, and Subcategories."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class CategoryDomain:
    id: UUID
    category_name: str
    image: str | None = None
    active: bool | None = True
    description: str | None = None


@dataclass
class SubCategoryDomain:
    id: UUID
    sub_category_name: str
    category_id: UUID
    category_name: str | None = None
    is_free: bool = False
    document_ids: list[UUID] = field(default_factory=list)


@dataclass
class ServiceDomain:
    id: UUID
    provider_id: UUID
    service_name: str
    category_id: UUID
    sub_category_id: UUID
    price: float
    type: str = "fixed"
    service_location_mode: str = "on_site"
    description: str | None = None
    address: str | None = None
    category_name: str | None = None
    sub_category_name: str | None = None
    discount: str | None = None
    pre_payment: bool = False
    feature: bool = False
    status: bool = True
    active: bool | None = True
    slug: str | None = None
    service_image: list[str] = field(default_factory=list)
    video: str | None = None
    duration: str | None = None
    is_archived: bool | None = False
    approved: bool = False
    feature_requested_status: str | None = "none"
    feature_requested_at: datetime | None = None
    provider_name: str | None = None
    provider_email: str | None = None
    created_at: datetime | None = None
