"""Domain models for Content, Blog, Banners, and Marketing Tracker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


@dataclass
class BlogPostDomain:
    id: UUID
    title: str
    slug: str
    content_html: str
    excerpt: str | None = None
    cover_image: str | None = None
    author_name: str | None = None
    status: str = "draft"  # draft | published | archived
    published_at: datetime | None = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BlogCommentDomain:
    id: UUID
    post_id: UUID
    full_name: str
    phone: str
    body: str
    status: str = "pending"  # approved | pending | hidden
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BannerDomain:
    id: int
    banner_name: str | None
    image: str | None
    link: str | None = None
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MarketingSheetDomain:
    id: UUID
    name: str
    position: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MarketingColumnDomain:
    id: UUID
    key: str
    label: str
    column_type: str = "text"
    position: int = 0
    is_system: bool = False
    width_px: int | None = 150
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MarketingRowDomain:
    id: UUID
    sheet_id: UUID
    position: int
    values: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

