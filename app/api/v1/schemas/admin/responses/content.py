"""Response schemas for Content, Blog, Banners, and Marketing Tracker."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BlogPostResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    title: str
    slug: str
    excerpt: str | None = None
    content_html: str = Field(serialization_alias="contentHtml")
    cover_image: str | None = Field(default=None, serialization_alias="coverImage")
    author_name: str | None = Field(default=None, serialization_alias="authorName")
    status: str
    published_at: datetime | None = Field(default=None, serialization_alias="publishedAt")
    view_count: int = Field(default=0, serialization_alias="viewCount")
    like_count: int = Field(default=0, serialization_alias="likeCount")
    comment_count: int = Field(default=0, serialization_alias="commentCount")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class BlogPostListResponse(BaseModel):
    data: list[BlogPostResponseItem]


class BlogPostSingleResponse(BaseModel):
    data: BlogPostResponseItem


class BlogCommentResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    post_id: UUID = Field(serialization_alias="postId")
    full_name: str = Field(serialization_alias="fullName")
    phone: str
    body: str
    status: str
    created_at: datetime = Field(serialization_alias="createdAt")


class BlogCommentListResponse(BaseModel):
    data: list[BlogCommentResponseItem]


class BannerResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    banner_name: str | None = Field(default=None, serialization_alias="bannerName")
    image: str | None = None
    link: str | None = None
    active: bool
    created_at: datetime = Field(serialization_alias="createdAt")


class BannerListResponse(BaseModel):
    data: list[BannerResponseItem]


class BannerSingleResponse(BaseModel):
    data: BannerResponseItem


class MarketingSheetResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str
    position: int
    created_at: datetime = Field(serialization_alias="createdAt")


class MarketingColumnResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    key: str
    label: str
    column_type: str = Field(serialization_alias="columnType")
    position: int
    is_system: bool = Field(serialization_alias="isSystem")
    width_px: int | None = Field(default=None, serialization_alias="widthPx")


class MarketingRowResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    sheet_id: UUID = Field(serialization_alias="sheetId")
    position: int
    values: dict[str, Any]
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class MarketingTrackerWorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    sheets: list[MarketingSheetResponseItem]
    active_sheet_id: UUID | None = Field(default=None, serialization_alias="activeSheetId")
    columns: list[MarketingColumnResponseItem]
    rows: list[MarketingRowResponseItem]

